"""Orchestrate Digital Twin experiment execution."""

from dataclasses import dataclass
from typing import Any

from .analyzer import (
    InstanceFailureImpactResult,
    ScaleOutImpactResult,
    ScenarioImpactAnalyzer,
    TrafficImpactResult,
)
from .bottleneck import BottleneckDetector, BottleneckResult
from .experiment import Experiment, ExperimentStatus, ScenarioType
from .models import Infrastructure
from .predictor import ResourceDemandPredictor, ResourcePredictionResult
from .simulator import (
    DigitalTwinSimulator,
    InstanceFailureResult,
    ScaleOutResult,
    TrafficSurgeResult,
)


class ExperimentExecutionError(ValueError):
    """Raised when an experiment cannot be executed or completed."""


SimulationResult = TrafficSurgeResult | InstanceFailureResult | ScaleOutResult
ImpactResult = (
    TrafficImpactResult | InstanceFailureImpactResult | ScaleOutImpactResult
)


@dataclass(frozen=True)
class ExecutionResult:
    """Typed outputs produced by one completed experiment execution."""

    experiment_id: str
    scenario_type: ScenarioType
    service_name: str
    simulation: SimulationResult
    impact: ImpactResult
    prediction: ResourcePredictionResult
    bottleneck: BottleneckResult


class ExperimentExecutor:
    """Coordinate existing simulation, analysis, prediction, and persistence APIs."""

    def __init__(
        self,
        repository: Any | None = None,
        result_repository: Any | None = None,
        simulator: DigitalTwinSimulator | None = None,
        analyzer: ScenarioImpactAnalyzer | None = None,
        predictor: ResourceDemandPredictor | None = None,
        bottleneck_detector: BottleneckDetector | None = None,
    ) -> None:
        self.repository = repository
        self.result_repository = result_repository
        self.simulator = simulator or DigitalTwinSimulator()
        self.analyzer = analyzer or ScenarioImpactAnalyzer()
        self.predictor = predictor or ResourceDemandPredictor()
        self.bottleneck_detector = bottleneck_detector or BottleneckDetector()

    def execute(
        self,
        experiment: Experiment,
        baseline: Infrastructure,
        service_name: str,
    ) -> ExecutionResult:
        """Execute one CREATED experiment against an explicit baseline."""
        self._validate_request(experiment, baseline, service_name)

        try:
            simulation = self._simulate(experiment, baseline, service_name)
        except Exception as error:
            raise ExperimentExecutionError("experiment simulation failed") from error

        try:
            experiment.transition_to(ExperimentStatus.SIMULATED)
        except Exception as error:
            raise ExperimentExecutionError(
                "experiment could not transition to SIMULATED"
            ) from error

        try:
            impact = self._analyze(
                experiment.scenario_type,
                baseline,
                simulation,
            )
            prediction = self.predictor.predict(
                baseline,
                service_name,
                simulation,
            )
            bottleneck = self.bottleneck_detector.analyze(
                simulation.infrastructure,
                service_name,
            )
        except Exception as error:
            raise ExperimentExecutionError(
                "experiment post-simulation analysis failed"
            ) from error

        execution_result = ExecutionResult(
            experiment_id=experiment.experiment_id,
            scenario_type=experiment.scenario_type,
            service_name=service_name,
            simulation=simulation,
            impact=impact,
            prediction=prediction,
            bottleneck=bottleneck,
        )

        if self.result_repository is not None:
            try:
                self.result_repository.create(execution_result)
            except Exception as error:
                raise ExperimentExecutionError(
                    "experiment execution result could not be persisted"
                ) from error

        try:
            experiment.transition_to(ExperimentStatus.EXECUTED)
        except Exception as error:
            raise ExperimentExecutionError(
                "experiment could not transition to EXECUTED"
            ) from error

        if self.repository is not None:
            try:
                self.repository.update_status(
                    experiment.experiment_id,
                    ExperimentStatus.EXECUTED,
                )
            except Exception as error:
                raise ExperimentExecutionError(
                    "experiment EXECUTED status could not be persisted"
                ) from error

        return execution_result

    @staticmethod
    def _validate_request(
        experiment: Experiment,
        baseline: Infrastructure,
        service_name: str,
    ) -> None:
        if not isinstance(experiment, Experiment):
            raise ExperimentExecutionError("experiment must be an Experiment")
        if experiment.status is not ExperimentStatus.CREATED:
            raise ExperimentExecutionError(
                "experiment must be in CREATED status before execution"
            )
        if not isinstance(baseline, Infrastructure):
            raise ExperimentExecutionError(
                "baseline must be an Infrastructure instance"
            )
        if not isinstance(service_name, str) or not service_name.strip():
            raise ExperimentExecutionError("service name must not be empty")

    def _simulate(
        self,
        experiment: Experiment,
        baseline: Infrastructure,
        service_name: str,
    ) -> SimulationResult:
        if experiment.scenario_type is ScenarioType.TRAFFIC_SURGE:
            return self.simulator.traffic_surge(
                baseline,
                service_name,
                experiment.parameters.multiplier,
            )
        if experiment.scenario_type is ScenarioType.INSTANCE_FAILURE:
            return self.simulator.instance_failure(
                baseline,
                service_name,
                experiment.parameters.instance_name,
            )
        if experiment.scenario_type is ScenarioType.SCALE_OUT:
            return self.simulator.scale_out(
                baseline,
                service_name,
                experiment.parameters.additional_instances,
            )
        raise ExperimentExecutionError(
            f"unsupported experiment scenario: {experiment.scenario_type}"
        )

    def _analyze(
        self,
        scenario_type: ScenarioType,
        baseline: Infrastructure,
        simulation: SimulationResult,
    ) -> ImpactResult:
        if scenario_type is ScenarioType.TRAFFIC_SURGE:
            return self.analyzer.analyze_traffic(baseline, simulation)
        if scenario_type is ScenarioType.INSTANCE_FAILURE:
            return self.analyzer.analyze_instance_failure(baseline, simulation)
        if scenario_type is ScenarioType.SCALE_OUT:
            return self.analyzer.analyze_scale_out(baseline, simulation)
        raise ExperimentExecutionError(f"unsupported experiment scenario: {scenario_type}")