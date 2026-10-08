"""Aggregate typed experiment results into a deployment impact assessment."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .actual_result import ActualKubernetesResult
from .analyzer import (
    InstanceFailureImpactResult,
    ScaleOutImpactResult,
    TrafficImpactResult,
)
from .bottleneck import BottleneckResult, BottleneckStatus
from .experiment import ScenarioType
from .executor import ExecutionResult, ImpactResult
from .prediction_comparison import PredictionVsActualResult
from .predictor import ResourcePredictionResult, ResourceStatus


class DeploymentImpactError(ValueError):
    """Raised when typed experiment results cannot form a report."""


class ImpactSeverity(str, Enum):
    """Conservative overall deployment impact classification."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class DeploymentImpactReport:
    """Immutable aggregation of one experiment's impact evidence."""

    experiment_id: str
    scenario_type: ScenarioType
    service_name: str
    simulated_impact: ImpactResult
    predicted_demand: ResourcePredictionResult
    bottleneck: BottleneckResult
    actual_result: ActualKubernetesResult | None
    prediction_accuracy: PredictionVsActualResult | None
    overall_severity: ImpactSeverity
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of the report."""
        return {
            "experiment_id": self.experiment_id,
            "scenario_type": self.scenario_type.value,
            "service_name": self.service_name,
            "simulated_impact": _serialize(self.simulated_impact),
            "predicted_demand": _serialize(self.predicted_demand),
            "bottleneck": _serialize(self.bottleneck),
            "actual_result": _serialize(self.actual_result),
            "prediction_accuracy": _serialize(self.prediction_accuracy),
            "overall_severity": self.overall_severity.value,
            "limitations": list(self.limitations),
        }


class DeploymentImpactReportBuilder:
    """Aggregate existing typed results without performing analysis."""

    def build(
        self,
        execution_result: ExecutionResult,
        actual_result: ActualKubernetesResult | None = None,
        prediction_comparison: PredictionVsActualResult | None = None,
    ) -> DeploymentImpactReport:
        """Build a report from already-calculated execution and validation results."""
        self._validate_execution_result(execution_result)
        self._validate_optional_result_ids(
            execution_result, actual_result, prediction_comparison
        )
        self._validate_component_consistency(execution_result)

        return DeploymentImpactReport(
            experiment_id=execution_result.experiment_id,
            scenario_type=execution_result.scenario_type,
            service_name=execution_result.service_name,
            simulated_impact=execution_result.impact,
            predicted_demand=execution_result.prediction,
            bottleneck=execution_result.bottleneck,
            actual_result=actual_result,
            prediction_accuracy=prediction_comparison,
            overall_severity=self._severity(execution_result),
            limitations=self._limitations(
                actual_result,
                prediction_comparison,
            ),
        )

    @staticmethod
    def _validate_execution_result(execution_result: ExecutionResult) -> None:
        if not isinstance(execution_result, ExecutionResult):
            raise DeploymentImpactError(
                "execution_result must be an ExecutionResult"
            )
        if not isinstance(execution_result.experiment_id, str) or not execution_result.experiment_id.strip():
            raise DeploymentImpactError("experiment_id must be a non-empty string")
        if not isinstance(execution_result.service_name, str) or not execution_result.service_name.strip():
            raise DeploymentImpactError("service_name must be a non-empty string")

    @staticmethod
    def _validate_optional_result_ids(
        execution_result: ExecutionResult,
        actual_result: ActualKubernetesResult | None,
        prediction_comparison: PredictionVsActualResult | None,
    ) -> None:
        if actual_result is not None:
            if not isinstance(actual_result, ActualKubernetesResult):
                raise DeploymentImpactError(
                    "actual_result must be an ActualKubernetesResult"
                )
            if actual_result.experiment_id != execution_result.experiment_id:
                raise DeploymentImpactError(
                    "actual_result experiment ID does not match execution result"
                )
        if prediction_comparison is not None:
            if not isinstance(prediction_comparison, PredictionVsActualResult):
                raise DeploymentImpactError(
                    "prediction_comparison must be a PredictionVsActualResult"
                )
            if prediction_comparison.experiment_id != execution_result.experiment_id:
                raise DeploymentImpactError(
                    "prediction_comparison experiment ID does not match execution result"
                )
        if (
            actual_result is not None
            and prediction_comparison is not None
            and actual_result.experiment_id != prediction_comparison.experiment_id
        ):
            raise DeploymentImpactError(
                "actual_result and prediction_comparison experiment IDs must match"
            )

    @staticmethod
    def _validate_component_consistency(execution_result: ExecutionResult) -> None:
        expected_impact_types = {
            ScenarioType.TRAFFIC_SURGE: TrafficImpactResult,
            ScenarioType.INSTANCE_FAILURE: InstanceFailureImpactResult,
            ScenarioType.SCALE_OUT: ScaleOutImpactResult,
        }
        if not isinstance(
            execution_result.impact,
            expected_impact_types[execution_result.scenario_type],
        ):
            raise DeploymentImpactError(
                "impact type does not match execution scenario type"
            )
        if not isinstance(execution_result.prediction, ResourcePredictionResult):
            raise DeploymentImpactError("prediction must be a ResourcePredictionResult")
        if not isinstance(execution_result.bottleneck, BottleneckResult):
            raise DeploymentImpactError("bottleneck must be a BottleneckResult")
        for result in (
            execution_result.impact,
            execution_result.prediction,
            execution_result.bottleneck,
        ):
            if result.service_name != execution_result.service_name:
                raise DeploymentImpactError(
                    "execution result components must reference the same service"
                )

    @staticmethod
    def _severity(execution_result: ExecutionResult) -> ImpactSeverity:
        bottleneck_status = execution_result.bottleneck.overall_status
        prediction_statuses = (
            execution_result.prediction.cpu_status,
            execution_result.prediction.memory_status,
        )
        if (
            bottleneck_status is BottleneckStatus.BOTTLENECK
            or ResourceStatus.INSUFFICIENT in prediction_statuses
        ):
            return ImpactSeverity.HIGH
        if bottleneck_status is BottleneckStatus.WARNING:
            return ImpactSeverity.MEDIUM
        if (
            bottleneck_status is BottleneckStatus.NO_BOTTLENECK
            and all(status is ResourceStatus.SUFFICIENT for status in prediction_statuses)
        ):
            return ImpactSeverity.LOW
        return ImpactSeverity.INSUFFICIENT_DATA

    @staticmethod
    def _limitations(
        actual_result: ActualKubernetesResult | None,
        prediction_comparison: PredictionVsActualResult | None,
    ) -> tuple[str, ...]:
        limitations: list[str] = []
        if actual_result is None:
            limitations.append("actual validation is pending or unavailable")
        if prediction_comparison is None:
            limitations.append("prediction comparison is not available")
        return tuple(limitations)


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _serialize(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if isinstance(value, dict):
        return {_serialize(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_serialize(item) for item in value]
    return value
