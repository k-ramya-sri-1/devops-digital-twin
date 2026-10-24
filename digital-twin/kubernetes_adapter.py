"""Safe Kubernetes Deployment operations for infrastructure experiments."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
import time
from typing import Any

from kubernetes import client, config


class KubernetesExperimentError(RuntimeError):
    """Raised when a Kubernetes experiment operation fails."""


@dataclass(frozen=True)
class KubernetesDeploymentState:
    """The replica state reported by a Kubernetes Deployment."""

    name: str
    namespace: str
    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int


@dataclass(frozen=True)
class KubernetesContainerResourceLimits:
    """Live CPU and memory limits for one Deployment container."""

    cpu_cores: float
    memory_bytes: float


class KubernetesExperimentAdapter:
    """Read and safely scale one existing Kubernetes Deployment."""

    def __init__(
        self,
        deployment_name: str,
        namespace: str = "default",
        apps_api_client: Any | None = None,
        rollout_timeout_seconds: float = 120,
        poll_interval_seconds: float = 2,
    ) -> None:
        self.deployment_name = deployment_name
        self.namespace = namespace
        self.apps_api_client = apps_api_client or self._load_apps_api_client()
        self.rollout_timeout_seconds = rollout_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds

    @staticmethod
    def _load_apps_api_client() -> client.AppsV1Api:
        config.load_kube_config()
        return client.AppsV1Api()

    def get_deployment_state(self) -> KubernetesDeploymentState:
        """Read the current replica state from the configured Deployment."""
        try:
            deployment = self.apps_api_client.read_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace,
            )
        except Exception as error:
            raise KubernetesExperimentError(
                f"could not read Deployment '{self.deployment_name}'"
            ) from error

        spec = deployment.spec
        status = deployment.status
        return KubernetesDeploymentState(
            name=deployment.metadata.name,
            namespace=deployment.metadata.namespace,
            desired_replicas=spec.replicas or 0,
            ready_replicas=status.ready_replicas or 0,
            available_replicas=status.available_replicas or 0,
            updated_replicas=status.updated_replicas or 0,
        )

    def get_container_resource_limits(
        self,
        container_name: str,
    ) -> KubernetesContainerResourceLimits:
        """Read CPU and memory limits from the live Deployment template."""
        deployment = self._read_deployment()
        try:
            container = next(
                item
                for item in deployment.spec.template.spec.containers
                if item.name == container_name
            )
            limits = container.resources.limits
            cpu = self._parse_quantity(limits["cpu"], "cpu", self._CPU_UNITS)
            memory = self._parse_quantity(
                limits["memory"], "memory", self._MEMORY_UNITS
            )
        except (
            AttributeError,
            KeyError,
            StopIteration,
            TypeError,
            ValueError,
        ) as error:
            raise KubernetesExperimentError(
                f"could not read resource limits for container '{container_name}'"
            ) from error
        return KubernetesContainerResourceLimits(cpu_cores=cpu, memory_bytes=memory)

    _CPU_UNITS = {
        "n": Decimal("1e-9"),
        "u": Decimal("1e-6"),
        "m": Decimal("1e-3"),
        "": Decimal("1"),
    }
    _MEMORY_UNITS = {
        "Ki": Decimal(1024),
        "Mi": Decimal(1024**2),
        "Gi": Decimal(1024**3),
        "Ti": Decimal(1024**4),
        "Pi": Decimal(1024**5),
        "Ei": Decimal(1024**6),
        "k": Decimal(1000),
        "M": Decimal(1000**2),
        "G": Decimal(1000**3),
        "T": Decimal(1000**4),
        "P": Decimal(1000**5),
        "E": Decimal(1000**6),
        "": Decimal(1),
    }

    def _read_deployment(self) -> Any:
        try:
            return self.apps_api_client.read_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace,
            )
        except Exception as error:
            raise KubernetesExperimentError(
                f"could not read Deployment '{self.deployment_name}'"
            ) from error

    @staticmethod
    def _parse_quantity(
        value: str,
        resource_name: str,
        units: dict[str, Decimal],
    ) -> float:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{resource_name} limit is missing")
        text = value.strip()
        suffix = next(
            (
                candidate
                for candidate in sorted(units, key=len, reverse=True)
                if text.endswith(candidate)
            ),
            None,
        )
        if suffix is None:
            raise ValueError(f"unsupported {resource_name} quantity")
        try:
            amount = Decimal(text[: -len(suffix)] if suffix else text)
        except InvalidOperation as error:
            raise ValueError(f"invalid {resource_name} quantity") from error
        result = amount * units[suffix]
        numeric_result = float(result)
        if not isfinite(numeric_result) or numeric_result <= 0:
            raise ValueError(f"{resource_name} limit must be positive")
        return numeric_result

    def scale_replicas(self, target_replicas: int) -> None:
        """Patch only the Deployment scale subresource replica count."""
        self._validate_replica_count(target_replicas, "target_replicas")
        try:
            self.apps_api_client.patch_namespaced_deployment_scale(
                name=self.deployment_name,
                namespace=self.namespace,
                body={"spec": {"replicas": target_replicas}},
            )
        except Exception as error:
            raise KubernetesExperimentError(
                f"could not scale Deployment '{self.deployment_name}'"
            ) from error

    def wait_for_rollout(self, target_replicas: int) -> KubernetesDeploymentState:
        """Wait until all relevant Deployment replica counts reach the target."""
        self._validate_replica_count(target_replicas, "target_replicas")
        deadline = time.monotonic() + self.rollout_timeout_seconds

        while True:
            state = self.get_deployment_state()
            if (
                state.desired_replicas == target_replicas
                and state.ready_replicas == target_replicas
                and state.available_replicas == target_replicas
            ):
                return state
            if time.monotonic() >= deadline:
                raise KubernetesExperimentError(
                    f"Deployment '{self.deployment_name}' rollout timed out"
                )
            time.sleep(self.poll_interval_seconds)

    def scale_and_wait(self, target_replicas: int) -> KubernetesDeploymentState:
        """Scale the Deployment and wait for the target replica count."""
        self.scale_replicas(target_replicas)
        return self.wait_for_rollout(target_replicas)

    def restore_replicas(self, original_replicas: int) -> KubernetesDeploymentState:
        """Restore the Deployment to its original replica count."""
        self._validate_replica_count(original_replicas, "original_replicas")
        return self.scale_and_wait(original_replicas)

    @staticmethod
    def _validate_replica_count(value: int, field_name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{field_name} must be an integer greater than or equal to 1")