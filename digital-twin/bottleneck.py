"""Deterministic bottleneck detection for Digital Twin infrastructure state."""

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .models import Infrastructure, InstanceStatus, Service


class BottleneckError(ValueError):
    """Raised when bottleneck analysis input is invalid."""


class BottleneckStatus(str, Enum):
    """Classification values used for resources and overall service state."""

    NORMAL = "NORMAL"
    WARNING = "WARNING"
    BOTTLENECK = "BOTTLENECK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NO_BOTTLENECK = "NO_BOTTLENECK"


@dataclass(frozen=True)
class BottleneckThresholds:
    """Configurable utilization thresholds expressed as percentages."""

    warning: float = 70.0
    bottleneck: float = 85.0

    def __post_init__(self) -> None:
        if (
            not isfinite(self.warning)
            or not isfinite(self.bottleneck)
            or self.warning < 0
            or self.bottleneck > 100
            or self.warning >= self.bottleneck
        ):
            raise BottleneckError(
                "thresholds must satisfy 0 <= warning < bottleneck <= 100"
            )


@dataclass(frozen=True)
class BottleneckResult:
    """Structured bottleneck classifications for one selected service."""

    service_name: str
    cpu_utilization: float | None
    memory_utilization: float | None
    cpu_status: BottleneckStatus
    memory_status: BottleneckStatus
    total_instance_count: int
    healthy_instance_count: int
    unhealthy_instance_count: int
    total_cpu_capacity: float
    total_memory_capacity: float
    healthy_cpu_capacity: float
    healthy_memory_capacity: float
    overall_status: BottleneckStatus
    reasons: tuple[str, ...]


class BottleneckDetector:
    """Identify deterministic resource and health bottlenecks in a service."""

    def __init__(self, thresholds: BottleneckThresholds | None = None) -> None:
        """Create a detector with default or validated custom thresholds."""
        self.thresholds = thresholds or BottleneckThresholds()

    def analyze(
        self,
        infrastructure: Infrastructure,
        service_name: str,
    ) -> BottleneckResult:
        """Analyze one service without modifying the supplied infrastructure."""
        service = self._get_service(infrastructure, service_name)
        healthy_instances = [
            instance
            for instance in service.instances.values()
            if instance.status is InstanceStatus.HEALTHY
        ]
        total_instance_count = len(service.instances)
        healthy_instance_count = len(healthy_instances)
        unhealthy_instance_count = total_instance_count - healthy_instance_count
        cpu_utilization = self._average_utilization(
            healthy_instances, "cpu_utilization", service.total_cpu_capacity
        )
        memory_utilization = self._average_utilization(
            healthy_instances, "memory_utilization", service.total_memory_capacity
        )
        cpu_status = self._classify(cpu_utilization)
        memory_status = self._classify(memory_utilization)
        reasons = self._reasons(
            cpu_utilization,
            memory_utilization,
            cpu_status,
            memory_status,
            healthy_instance_count,
            unhealthy_instance_count,
        )
        overall_status = self._overall_status(
            cpu_status,
            memory_status,
            healthy_instance_count,
            unhealthy_instance_count,
        )
        return BottleneckResult(
            service_name=service_name,
            cpu_utilization=cpu_utilization,
            memory_utilization=memory_utilization,
            cpu_status=cpu_status,
            memory_status=memory_status,
            total_instance_count=total_instance_count,
            healthy_instance_count=healthy_instance_count,
            unhealthy_instance_count=unhealthy_instance_count,
            total_cpu_capacity=service.total_cpu_capacity,
            total_memory_capacity=service.total_memory_capacity,
            healthy_cpu_capacity=sum(
                instance.cpu_capacity for instance in healthy_instances
            ),
            healthy_memory_capacity=sum(
                instance.memory_capacity for instance in healthy_instances
            ),
            overall_status=overall_status,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _get_service(
        infrastructure: Infrastructure, service_name: str
    ) -> Service:
        if not service_name or not service_name.strip():
            raise BottleneckError("service name must not be empty")
        try:
            return infrastructure.get_service(service_name)
        except KeyError as error:
            raise BottleneckError(f"unknown service '{service_name}'") from error

    @staticmethod
    def _average_utilization(
        instances: list,
        field_name: str,
        total_capacity: float,
    ) -> float | None:
        if not instances or total_capacity <= 0:
            return None
        values = [getattr(instance, field_name) for instance in instances]
        if any(value <= 0 for value in values):
            return None
        return sum(values) / len(values)

    def _classify(self, utilization: float | None) -> BottleneckStatus:
        if utilization is None:
            return BottleneckStatus.INSUFFICIENT_DATA
        if utilization >= self.thresholds.bottleneck:
            return BottleneckStatus.BOTTLENECK
        if utilization >= self.thresholds.warning:
            return BottleneckStatus.WARNING
        return BottleneckStatus.NORMAL

    @staticmethod
    def _overall_status(
        cpu_status: BottleneckStatus,
        memory_status: BottleneckStatus,
        healthy_instance_count: int,
        unhealthy_instance_count: int,
    ) -> BottleneckStatus:
        statuses = (cpu_status, memory_status)
        if healthy_instance_count == 0:
            return BottleneckStatus.BOTTLENECK
        if BottleneckStatus.BOTTLENECK in statuses:
            return BottleneckStatus.BOTTLENECK
        if BottleneckStatus.WARNING in statuses or unhealthy_instance_count > 0:
            return BottleneckStatus.WARNING
        if BottleneckStatus.INSUFFICIENT_DATA in statuses:
            return BottleneckStatus.INSUFFICIENT_DATA
        return BottleneckStatus.NO_BOTTLENECK

    @staticmethod
    def _reasons(
        cpu_utilization: float | None,
        memory_utilization: float | None,
        cpu_status: BottleneckStatus,
        memory_status: BottleneckStatus,
        healthy_instance_count: int,
        unhealthy_instance_count: int,
    ) -> list[str]:
        reasons: list[str] = []
        if cpu_status is BottleneckStatus.INSUFFICIENT_DATA:
            reasons.append("CPU utilization or capacity data is insufficient")
        if memory_status is BottleneckStatus.INSUFFICIENT_DATA:
            reasons.append("memory utilization or capacity data is insufficient")
        if cpu_status is BottleneckStatus.BOTTLENECK:
            reasons.append(f"CPU utilization is critically high: {cpu_utilization:.1f}%")
        elif cpu_status is BottleneckStatus.WARNING:
            reasons.append(f"CPU utilization is elevated: {cpu_utilization:.1f}%")
        if memory_status is BottleneckStatus.BOTTLENECK:
            reasons.append(
                f"memory utilization is critically high: {memory_utilization:.1f}%"
            )
        elif memory_status is BottleneckStatus.WARNING:
            reasons.append(
                f"memory utilization is elevated: {memory_utilization:.1f}%"
            )
        if unhealthy_instance_count:
            reasons.append(
                f"{unhealthy_instance_count} of {healthy_instance_count + unhealthy_instance_count} instances are unhealthy"
            )
        if healthy_instance_count == 0:
            reasons.append("no healthy instances are available")
        if not reasons:
            reasons.append("no measured resource or health bottleneck detected")
        return reasons