"""Map supported prediction and actual values into comparison metrics."""

from typing import Any

from .actual_result import ActualKubernetesResult
from .experiment import ScenarioType
from .executor import ExecutionResult


class MetricMappingError(ValueError):
    """Raised when supported prediction and actual metrics cannot be mapped."""


def map_scale_out_replica_metrics(
    execution_result: ExecutionResult | None,
    actual_result: ActualKubernetesResult | None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Map the supported scale-out replica count into validator inputs."""
    if execution_result is None:
        raise MetricMappingError("execution_result must be supplied")
    if actual_result is None:
        raise MetricMappingError("actual_result must be supplied")
    if not isinstance(execution_result, ExecutionResult):
        raise MetricMappingError("execution_result must be an ExecutionResult")
    if not isinstance(actual_result, ActualKubernetesResult):
        raise MetricMappingError(
            "actual_result must be an ActualKubernetesResult"
        )
    if execution_result.scenario_type is not ScenarioType.SCALE_OUT:
        raise MetricMappingError(
            "scale-out replica metrics require a SCALE_OUT execution result"
        )
    if execution_result.experiment_id != actual_result.experiment_id:
        raise MetricMappingError(
            "execution_result and actual_result experiment IDs must match"
        )

    try:
        predicted_value = execution_result.impact.simulated_instance_count
    except AttributeError as error:
        raise MetricMappingError(
            "execution_result is missing simulated_instance_count"
        ) from error
    actual_value = actual_result.desired_replicas
    _validate_replica_value(predicted_value, "predicted replica count")
    _validate_replica_value(actual_value, "actual replica count")

    return (
        {"replica_count": predicted_value},
        {"replica_count": actual_value},
    )


def _validate_replica_value(value: Any, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MetricMappingError(
            f"{field_name} must be an integer greater than or equal to 0"
        )