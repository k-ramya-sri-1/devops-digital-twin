"""Collect and validate actual Kubernetes experiment results."""

from dataclasses import dataclass

from .kubernetes_adapter import KubernetesDeploymentState, KubernetesExperimentAdapter


class ActualResultError(ValueError):
    """Raised when an actual Kubernetes result cannot be collected or validated."""


@dataclass(frozen=True)
class ActualKubernetesResult:
    """Immutable, serializable replica state observed after an experiment."""

    experiment_id: str
    deployment_name: str
    namespace: str
    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int

    def __post_init__(self) -> None:
        self._validate_name(self.experiment_id, "experiment_id")
        self._validate_name(self.deployment_name, "deployment_name")
        self._validate_name(self.namespace, "namespace")
        for field_name in (
            "desired_replicas",
            "ready_replicas",
            "available_replicas",
            "updated_replicas",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ActualResultError(
                    f"{field_name} must be an integer greater than or equal to 0"
                )
            if field_name != "desired_replicas" and value > self.desired_replicas:
                raise ActualResultError(
                    f"{field_name} must not be greater than desired_replicas"
                )

    @staticmethod
    def _validate_name(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ActualResultError(f"{field_name} must be a non-empty string")

    def to_dict(self) -> dict[str, object]:
        """Return only JSON-compatible actual-result fields."""
        return {
            "experiment_id": self.experiment_id,
            "deployment_name": self.deployment_name,
            "namespace": self.namespace,
            "desired_replicas": self.desired_replicas,
            "ready_replicas": self.ready_replicas,
            "available_replicas": self.available_replicas,
            "updated_replicas": self.updated_replicas,
        }


class ActualResultCollector:
    """Collect an actual result through an injected Kubernetes adapter."""

    def __init__(self, adapter: KubernetesExperimentAdapter) -> None:
        self.adapter = adapter

    def collect(self, experiment_id: str) -> ActualKubernetesResult:
        """Read the adapter state and convert it to an actual result."""
        self._validate_experiment_id(experiment_id)
        try:
            state = self.adapter.get_deployment_state()
        except Exception as error:
            raise ActualResultError(
                f"could not collect actual result for experiment '{experiment_id}': {error}"
            ) from error

        try:
            return ActualKubernetesResult(
                experiment_id=experiment_id,
                deployment_name=state.name,
                namespace=state.namespace,
                desired_replicas=state.desired_replicas,
                ready_replicas=state.ready_replicas,
                available_replicas=state.available_replicas,
                updated_replicas=state.updated_replicas,
            )
        except ActualResultError:
            raise
        except Exception as error:
            raise ActualResultError(
                f"could not convert actual result for experiment '{experiment_id}'"
            ) from error

    @staticmethod
    def _validate_experiment_id(experiment_id: str) -> None:
        if not isinstance(experiment_id, str) or not experiment_id.strip():
            raise ActualResultError("experiment_id must be a non-empty string")