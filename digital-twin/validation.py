"""Complete executed experiments by validating them against actual results."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .actual_result import ActualKubernetesResult
from .experiment import Experiment, ExperimentStatus
from .prediction_comparison import PredictionVsActualResult


class ValidationError(ValueError):
    """Raised when an executed experiment cannot be validated."""


@dataclass(frozen=True)
class ValidationResult:
    """Immutable actual result and comparison produced by validation."""

    experiment_id: str
    actual_result: ActualKubernetesResult
    prediction_comparison: PredictionVsActualResult


class ExperimentValidationService:
    """Validate an executed experiment through injected domain dependencies."""

    def __init__(
        self,
        experiment_repository: Any,
        experiment_result_repository: Any,
        actual_result_collector: Any,
        metric_mapper: Callable[[Any, ActualKubernetesResult], tuple[
            Mapping[str, object], Mapping[str, object]
        ]],
        prediction_vs_actual_analyzer: Any,
    ) -> None:
        self.experiment_repository = experiment_repository
        self.experiment_result_repository = experiment_result_repository
        self.actual_result_collector = actual_result_collector
        self.metric_mapper = metric_mapper
        self.prediction_vs_actual_analyzer = prediction_vs_actual_analyzer

    def validate(self, experiment_id: str) -> ValidationResult:
        """Validate one EXECUTED experiment and mark it VALIDATED on success."""
        experiment = self._load_experiment(experiment_id)
        if experiment.status is not ExperimentStatus.EXECUTED:
            raise ValidationError(
                "experiment must be in EXECUTED status before validation"
            )

        execution_result = self.experiment_result_repository.get_by_experiment_id(
            experiment_id
        )
        if execution_result is None:
            raise ValidationError(
                f"persisted execution result not found: {experiment_id}"
            )

        actual_result = self._collect_actual_result(experiment_id)
        expected_metrics, actual_metrics = self._map_metrics(
            execution_result, actual_result
        )
        prediction_comparison = self._compare(
            experiment_id, expected_metrics, actual_metrics
        )

        try:
            self.experiment_result_repository.update_actual_comparison(
                experiment_id, actual_result, prediction_comparison
            )
        except Exception as error:
            raise ValidationError(
                "actual result and prediction comparison could not be persisted"
            ) from error

        try:
            experiment.transition_to(ExperimentStatus.VALIDATED)
        except Exception as error:
            raise ValidationError(
                "experiment could not transition to VALIDATED"
            ) from error

        try:
            self.experiment_repository.update_status(
                experiment_id, ExperimentStatus.VALIDATED
            )
        except Exception as error:
            raise ValidationError(
                "experiment VALIDATED status could not be persisted"
            ) from error

        return ValidationResult(
            experiment_id=experiment_id,
            actual_result=actual_result,
            prediction_comparison=prediction_comparison,
        )

    def _load_experiment(self, experiment_id: str) -> Experiment:
        try:
            experiment = self.experiment_repository.get_by_id(experiment_id)
        except Exception as error:
            raise ValidationError("experiment could not be loaded") from error
        if experiment is None:
            raise ValidationError(f"experiment not found: {experiment_id}")
        if not isinstance(experiment, Experiment):
            raise ValidationError("experiment repository returned an invalid experiment")
        return experiment

    def _collect_actual_result(self, experiment_id: str) -> ActualKubernetesResult:
        try:
            actual_result = self.actual_result_collector.collect(experiment_id)
        except Exception as error:
            raise ValidationError("actual Kubernetes result could not be collected") from error
        if not isinstance(actual_result, ActualKubernetesResult):
            raise ValidationError("actual result collector returned an invalid result")
        if actual_result.experiment_id != experiment_id:
            raise ValidationError("actual result experiment ID does not match")
        return actual_result

    def _map_metrics(
        self,
        execution_result: Any,
        actual_result: ActualKubernetesResult,
    ) -> tuple[Mapping[str, object], Mapping[str, object]]:
        try:
            return self.metric_mapper(execution_result, actual_result)
        except Exception as error:
            raise ValidationError("prediction metrics could not be mapped") from error

    def _compare(
        self,
        experiment_id: str,
        expected_metrics: Mapping[str, object],
        actual_metrics: Mapping[str, object],
    ) -> PredictionVsActualResult:
        try:
            comparison = self.prediction_vs_actual_analyzer.compare(
                experiment_id, expected_metrics, actual_metrics
            )
        except Exception as error:
            raise ValidationError("prediction and actual values could not be compared") from error
        if not isinstance(comparison, PredictionVsActualResult):
            raise ValidationError("comparison analyzer returned an invalid result")
        return comparison