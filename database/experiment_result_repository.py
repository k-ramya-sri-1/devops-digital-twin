"""Data access for persisted Digital Twin execution results."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
import json
from typing import Any

from .config import DatabaseConfig
from .connection import DatabaseError, connect


models_module = importlib.import_module("digital-twin.models")
simulator_module = importlib.import_module("digital-twin.simulator")
analyzer_module = importlib.import_module("digital-twin.analyzer")
predictor_module = importlib.import_module("digital-twin.predictor")
bottleneck_module = importlib.import_module("digital-twin.bottleneck")
experiment_module = importlib.import_module("digital-twin.experiment")
executor_module = importlib.import_module("digital-twin.executor")
actual_result_module = importlib.import_module("digital-twin.actual_result")
prediction_comparison_module = importlib.import_module(
    "digital-twin.prediction_comparison"
)

Infrastructure = models_module.Infrastructure
Service = models_module.Service
Instance = models_module.Instance
InstanceStatus = models_module.InstanceStatus
ScenarioType = experiment_module.ScenarioType
TrafficSurgeResult = simulator_module.TrafficSurgeResult
InstanceFailureResult = simulator_module.InstanceFailureResult
ScaleOutResult = simulator_module.ScaleOutResult
TrafficImpactResult = analyzer_module.TrafficImpactResult
InstanceFailureImpactResult = analyzer_module.InstanceFailureImpactResult
ScaleOutImpactResult = analyzer_module.ScaleOutImpactResult
CapacitySnapshot = analyzer_module.CapacitySnapshot
ResourcePredictionResult = predictor_module.ResourcePredictionResult
ResourceStatus = predictor_module.ResourceStatus
BottleneckResult = bottleneck_module.BottleneckResult
BottleneckStatus = bottleneck_module.BottleneckStatus
ExecutionResult = executor_module.ExecutionResult
ActualKubernetesResult = actual_result_module.ActualKubernetesResult
PredictionMetricComparison = prediction_comparison_module.PredictionMetricComparison
PredictionVsActualResult = prediction_comparison_module.PredictionVsActualResult


class ExperimentResultRepository:
    """Persist and reconstruct typed execution results."""

    _SELECT_COLUMNS = (
        "experiment_id, scenario_type, service_name, simulation, "
        "impact, prediction, bottleneck"
    )

    def __init__(
        self,
        config: DatabaseConfig | None = None,
        connection_factory: Callable[[DatabaseConfig | None], Any] | None = None,
    ) -> None:
        self._config = config
        self._connection_factory = connection_factory or connect

    def create(self, result: ExecutionResult) -> None:
        query = (
            "INSERT INTO experiment_results "
            "(experiment_id, scenario_type, service_name, simulation, impact, "
            "prediction, bottleneck, actual_result, prediction_comparison) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL)"
        )
        values = (
            result.experiment_id,
            result.scenario_type.value,
            result.service_name,
            json.dumps(self._serialize(result.simulation)),
            json.dumps(self._serialize(result.impact)),
            json.dumps(self._serialize(result.prediction)),
            json.dumps(self._serialize(result.bottleneck)),
        )
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query, values)
            connection.commit()
        except Exception as error:
            self._rollback(connection)
            self._raise_operation_error(error, "create experiment result")
        finally:
            self._close(cursor, connection)

    def get_by_experiment_id(self, experiment_id: str) -> ExecutionResult | None:
        query = (
            f"SELECT {self._SELECT_COLUMNS} FROM experiment_results "
            "WHERE experiment_id = %s"
        )
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query, (experiment_id,))
            row = cursor.fetchone()
            return None if row is None else self._from_row(row)
        except Exception as error:
            self._raise_operation_error(error, "retrieve experiment result")
        finally:
            self._close(cursor, connection)

    def list_all(self) -> list[ExecutionResult]:
        query = (
            f"SELECT {self._SELECT_COLUMNS} FROM experiment_results "
            "ORDER BY experiment_id"
        )
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            return [self._from_row(row) for row in cursor.fetchall()]
        except Exception as error:
            self._raise_operation_error(error, "list experiment results")
        finally:
            self._close(cursor, connection)

    def update_actual_comparison(
        self,
        experiment_id: str,
        actual_result: ActualKubernetesResult,
        prediction_comparison: PredictionVsActualResult,
    ) -> None:
        """Persist actual Kubernetes data and its prediction comparison."""
        self._validate_experiment_id(experiment_id)
        if not isinstance(actual_result, ActualKubernetesResult):
            raise DatabaseError("actual_result must be an ActualKubernetesResult")
        if not isinstance(prediction_comparison, PredictionVsActualResult):
            raise DatabaseError(
                "prediction_comparison must be a PredictionVsActualResult"
            )
        query = (
            "UPDATE experiment_results SET actual_result = %s, "
            "prediction_comparison = %s WHERE experiment_id = %s"
        )
        values = (
            json.dumps(self._serialize(actual_result)),
            json.dumps(self._serialize(prediction_comparison)),
            experiment_id,
        )
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query, values)
            if cursor.rowcount == 0:
                raise DatabaseError(f"experiment result not found: {experiment_id}")
            connection.commit()
        except DatabaseError:
            self._rollback(connection)
            raise
        except Exception as error:
            self._rollback(connection)
            self._raise_operation_error(error, "update actual experiment comparison")
        finally:
            self._close(cursor, connection)

    def get_actual_comparison(
        self, experiment_id: str
    ) -> tuple[ActualKubernetesResult | None, PredictionVsActualResult | None]:
        """Retrieve the optional actual result and prediction comparison."""
        self._validate_experiment_id(experiment_id)
        query = (
            "SELECT actual_result, prediction_comparison FROM experiment_results "
            "WHERE experiment_id = %s"
        )
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query, (experiment_id,))
            row = cursor.fetchone()
            if row is None:
                return (None, None)
            actual_data = self._optional_json_mapping(row[0])
            comparison_data = self._optional_json_mapping(row[1])
            actual_result = (
                None
                if actual_data is None
                else self._deserialize_actual_result(actual_data)
            )
            prediction_comparison = (
                None
                if comparison_data is None
                else self._deserialize_prediction_comparison(comparison_data)
            )
            return actual_result, prediction_comparison
        except DatabaseError:
            raise
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise DatabaseError(
                "invalid experiment result data returned by database"
            ) from error
        finally:
            self._close(cursor, connection)

    def _open(self) -> Any:
        try:
            return self._connection_factory(self._config)
        except DatabaseError:
            raise
        except Exception as error:
            raise DatabaseError("database connection failed") from error

    @classmethod
    def _from_row(cls, row: Sequence[Any]) -> ExecutionResult:
        try:
            scenario_type = ScenarioType(row[1])
            simulation_data = cls._json_mapping(row[3])
            impact_data = cls._json_mapping(row[4])
            prediction_data = cls._json_mapping(row[5])
            bottleneck_data = cls._json_mapping(row[6])
            simulation = cls._deserialize_simulation(scenario_type, simulation_data)
            impact = cls._deserialize_impact(scenario_type, impact_data)
            prediction = cls._deserialize_prediction(prediction_data)
            bottleneck = cls._deserialize_bottleneck(bottleneck_data)
            return ExecutionResult(
                experiment_id=row[0],
                scenario_type=scenario_type,
                service_name=row[2],
                simulation=simulation,
                impact=impact,
                prediction=prediction,
                bottleneck=bottleneck,
            )
        except DatabaseError:
            raise
        except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise DatabaseError("invalid experiment result data returned by database") from error

    @staticmethod
    def _json_mapping(value: Any) -> Mapping[str, Any]:
        parsed = json.loads(value) if isinstance(value, str) else value
        if not isinstance(parsed, Mapping):
            raise TypeError("result JSON must contain an object")
        return parsed

    @staticmethod
    def _optional_json_mapping(value: Any) -> Mapping[str, Any] | None:
        if value is None:
            return None
        return ExperimentResultRepository._json_mapping(value)

    @staticmethod
    def _validate_experiment_id(experiment_id: str) -> None:
        if not isinstance(experiment_id, str) or not experiment_id.strip():
            raise DatabaseError("experiment_id must be a non-empty string")

    @staticmethod
    def _deserialize_actual_result(
        data: Mapping[str, Any],
    ) -> ActualKubernetesResult:
        return ActualKubernetesResult(
            experiment_id=data["experiment_id"],
            deployment_name=data["deployment_name"],
            namespace=data["namespace"],
            desired_replicas=data["desired_replicas"],
            ready_replicas=data["ready_replicas"],
            available_replicas=data["available_replicas"],
            updated_replicas=data["updated_replicas"],
        )

    @classmethod
    def _deserialize_prediction_comparison(
        cls,
        data: Mapping[str, Any],
    ) -> PredictionVsActualResult:
        comparisons_data = data["comparisons"]
        if not isinstance(comparisons_data, list):
            raise TypeError("comparisons must be a list")
        comparisons = tuple(
            cls._deserialize_metric_comparison(comparison)
            for comparison in comparisons_data
        )
        return PredictionVsActualResult(
            experiment_id=data["experiment_id"],
            comparisons=comparisons,
            overall_status=data["overall_status"],
        )

    @staticmethod
    def _deserialize_metric_comparison(
        data: Mapping[str, Any],
    ) -> PredictionMetricComparison:
        if not isinstance(data, Mapping):
            raise TypeError("comparison must be an object")
        return PredictionMetricComparison(
            metric_name=data["metric_name"],
            expected=data["expected"],
            actual=data["actual"],
            absolute_error=data["absolute_error"],
            percentage_error=data["percentage_error"],
            status=data["status"],
        )

    @staticmethod
    def _deserialize_infrastructure(data: Mapping[str, Any]) -> Infrastructure:
        services = {
            name: ExperimentResultRepository._deserialize_service(service)
            for name, service in data["services"].items()
        }
        return Infrastructure(services=services)

    @staticmethod
    def _deserialize_service(data: Mapping[str, Any]) -> Service:
        instances = {
            name: ExperimentResultRepository._deserialize_instance(instance)
            for name, instance in data["instances"].items()
        }
        return Service(
            name=data["name"],
            dependencies=set(data["dependencies"]),
            instances=instances,
        )

    @staticmethod
    def _deserialize_instance(data: Mapping[str, Any]) -> Instance:
        return Instance(
            name=data["name"],
            cpu_capacity=data["cpu_capacity"],
            memory_capacity=data["memory_capacity"],
            cpu_utilization=data["cpu_utilization"],
            memory_utilization=data["memory_utilization"],
            request_rate=data["request_rate"],
            status=InstanceStatus(data["status"]),
            request_count=data["request_count"],
            request_latency_count=data["request_latency_count"],
        )

    @classmethod
    def _deserialize_simulation(
        cls,
        scenario_type: ScenarioType,
        data: Mapping[str, Any],
    ) -> Any:
        infrastructure = cls._deserialize_infrastructure(data["infrastructure"])
        common = {
            "infrastructure": infrastructure,
            "service_name": data["service_name"],
        }
        if scenario_type is ScenarioType.TRAFFIC_SURGE:
            return TrafficSurgeResult(
                **common,
                multiplier=data["multiplier"],
                original_request_rate=data["original_request_rate"],
                simulated_request_rate=data["simulated_request_rate"],
            )
        if scenario_type is ScenarioType.INSTANCE_FAILURE:
            return InstanceFailureResult(
                **common,
                instance_name=data["instance_name"],
                healthy_instance_count=data["healthy_instance_count"],
                unhealthy_instance_count=data["unhealthy_instance_count"],
                remaining_cpu_capacity=data["remaining_cpu_capacity"],
                remaining_memory_capacity=data["remaining_memory_capacity"],
            )
        return ScaleOutResult(
            **common,
            additional_instances=data["additional_instances"],
            simulated_instance_count=data["simulated_instance_count"],
            total_cpu_capacity=data["total_cpu_capacity"],
            total_memory_capacity=data["total_memory_capacity"],
        )

    @classmethod
    def _deserialize_impact(
        cls,
        scenario_type: ScenarioType,
        data: Mapping[str, Any],
    ) -> Any:
        if scenario_type is ScenarioType.TRAFFIC_SURGE:
            return TrafficImpactResult(**data)
        if scenario_type is ScenarioType.INSTANCE_FAILURE:
            return InstanceFailureImpactResult(
                service_name=data["service_name"],
                original_instance_count=data["original_instance_count"],
                simulated_instance_count=data["simulated_instance_count"],
                original_healthy_instance_count=data["original_healthy_instance_count"],
                simulated_healthy_instance_count=data["simulated_healthy_instance_count"],
                original_capacity=CapacitySnapshot(**data["original_capacity"]),
                simulated_capacity=CapacitySnapshot(**data["simulated_capacity"]),
                capacity_change=CapacitySnapshot(**data["capacity_change"]),
                healthy_instance_change=data["healthy_instance_change"],
            )
        return ScaleOutImpactResult(
            service_name=data["service_name"],
            original_instance_count=data["original_instance_count"],
            simulated_instance_count=data["simulated_instance_count"],
            instance_count_change=data["instance_count_change"],
            original_capacity=CapacitySnapshot(**data["original_capacity"]),
            simulated_capacity=CapacitySnapshot(**data["simulated_capacity"]),
            capacity_change=CapacitySnapshot(**data["capacity_change"]),
        )

    @staticmethod
    def _deserialize_prediction(data: Mapping[str, Any]) -> ResourcePredictionResult:
        return ResourcePredictionResult(
            service_name=data["service_name"],
            original_request_rate=data["original_request_rate"],
            simulated_request_rate=data["simulated_request_rate"],
            workload_multiplier=data["workload_multiplier"],
            healthy_instance_count=data["healthy_instance_count"],
            total_instance_count=data["total_instance_count"],
            cpu_capacity=data["cpu_capacity"],
            memory_capacity=data["memory_capacity"],
            healthy_cpu_capacity=data["healthy_cpu_capacity"],
            healthy_memory_capacity=data["healthy_memory_capacity"],
            projected_cpu_demand=data["projected_cpu_demand"],
            projected_memory_demand=data["projected_memory_demand"],
            cpu_status=ResourceStatus(data["cpu_status"]),
            memory_status=ResourceStatus(data["memory_status"]),
            insufficient_data=tuple(data["insufficient_data"]),
        )

    @staticmethod
    def _deserialize_bottleneck(data: Mapping[str, Any]) -> BottleneckResult:
        return BottleneckResult(
            service_name=data["service_name"],
            cpu_utilization=data["cpu_utilization"],
            memory_utilization=data["memory_utilization"],
            cpu_status=BottleneckStatus(data["cpu_status"]),
            memory_status=BottleneckStatus(data["memory_status"]),
            total_instance_count=data["total_instance_count"],
            healthy_instance_count=data["healthy_instance_count"],
            unhealthy_instance_count=data["unhealthy_instance_count"],
            total_cpu_capacity=data["total_cpu_capacity"],
            total_memory_capacity=data["total_memory_capacity"],
            healthy_cpu_capacity=data["healthy_cpu_capacity"],
            healthy_memory_capacity=data["healthy_memory_capacity"],
            overall_status=BottleneckStatus(data["overall_status"]),
            reasons=tuple(data["reasons"]),
        )

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, Enum):
            return ExperimentResultRepository._serialize(value.value)
        if is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: ExperimentResultRepository._serialize(
                    getattr(value, field.name)
                )
                for field in fields(value)
            }
        if isinstance(value, dict):
            return {
                ExperimentResultRepository._serialize(key): ExperimentResultRepository._serialize(
                    item
                )
                for key, item in value.items()
            }
        if isinstance(value, (tuple, set, list)):
            return [ExperimentResultRepository._serialize(item) for item in value]
        return value

    @staticmethod
    def _raise_operation_error(error: Exception, operation: str) -> None:
        if isinstance(error, DatabaseError):
            raise error
        if getattr(error, "errno", None) == 1062:
            raise DatabaseError("duplicate experiment result ID") from error
        raise DatabaseError(f"database error while attempting to {operation}") from error

    @staticmethod
    def _rollback(connection: Any) -> None:
        try:
            connection.rollback()
        except Exception:
            pass

    @staticmethod
    def _close(cursor: Any, connection: Any) -> None:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()