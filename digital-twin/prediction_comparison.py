"""Compare Digital Twin predictions with observed experiment results."""

from collections.abc import Mapping
from dataclasses import dataclass

from .validator import PredictionValidator, ValidationError


class PredictionComparisonError(ValueError):
    """Raised when prediction comparison input or validation is invalid."""


@dataclass(frozen=True)
class PredictionMetricComparison:
    """Immutable comparison of one predicted and observed metric."""

    metric_name: str
    expected: object | None
    actual: object | None
    absolute_error: float | None
    percentage_error: float | None
    status: str


@dataclass(frozen=True)
class PredictionVsActualResult:
    """Immutable comparison result for one experiment."""

    experiment_id: str
    comparisons: tuple[PredictionMetricComparison, ...]
    overall_status: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation of the comparison."""
        return {
            "experiment_id": self.experiment_id,
            "comparisons": [
                {
                    "metric_name": comparison.metric_name,
                    "expected": comparison.expected,
                    "actual": comparison.actual,
                    "absolute_error": comparison.absolute_error,
                    "percentage_error": comparison.percentage_error,
                    "status": comparison.status,
                }
                for comparison in self.comparisons
            ],
            "overall_status": self.overall_status,
        }


class PredictionVsActualAnalyzer:
    """Adapt validator results to the prediction-versus-actual domain."""

    def __init__(self, validator: PredictionValidator | None = None) -> None:
        self.validator = validator or PredictionValidator()

    def compare(
        self,
        experiment_id: str,
        expected_metrics: Mapping[str, object],
        actual_metrics: Mapping[str, object],
    ) -> PredictionVsActualResult:
        """Compare every metric supplied by either side of an experiment."""
        if not isinstance(experiment_id, str) or not experiment_id.strip():
            raise PredictionComparisonError(
                "experiment_id must be a non-empty string"
            )
        if not isinstance(expected_metrics, Mapping) or not isinstance(
            actual_metrics, Mapping
        ):
            raise PredictionComparisonError(
                "expected_metrics and actual_metrics must be mappings"
            )

        try:
            validation_result = self.validator.validate(
                experiment_id, expected_metrics, actual_metrics
            )
        except ValidationError as error:
            raise PredictionComparisonError(str(error)) from error

        comparisons = tuple(
            PredictionMetricComparison(
                metric_name=comparison.name,
                expected=comparison.expected,
                actual=comparison.actual,
                absolute_error=comparison.absolute_error,
                percentage_error=comparison.percentage_error,
                status=comparison.status.value,
            )
            for comparison in validation_result.comparisons
        )
        return PredictionVsActualResult(
            experiment_id=experiment_id,
            comparisons=comparisons,
            overall_status=validation_result.overall_status.value,
        )