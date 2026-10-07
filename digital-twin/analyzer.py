"""Deterministic impact analysis for Digital Twin simulation results."""

from dataclasses import dataclass

from .models import Infrastructure, InstanceStatus, Service
from .simulator import (
    InstanceFailureResult,
    ScaleOutResult,
    TrafficSurgeResult,
)


class AnalysisError(ValueError):
    """Raised when a simulation result cannot be analyzed against a state."""


@dataclass(frozen=True)
class CapacitySnapshot:
    """CPU and memory capacity represented by a service state."""

    cpu: float
    memory: float


@dataclass(frozen=True)
class TrafficImpactResult:
    """Structured request-rate impact for a traffic simulation."""

    service_name: str
    original_request_rate: float
    simulated_request_rate: float
    absolute_change: float
    percentage_change: float


@dataclass(frozen=True)
class InstanceFailureImpactResult:
    """Structured health and capacity impact for an instance failure."""

    service_name: str
    original_instance_count: int
    simulated_instance_count: int
    original_healthy_instance_count: int
    simulated_healthy_instance_count: int
    original_capacity: CapacitySnapshot
    simulated_capacity: CapacitySnapshot
    capacity_change: CapacitySnapshot
    healthy_instance_change: int

    @property
    def original_total_capacity(self) -> CapacitySnapshot:
        """Return the original CPU and memory capacity snapshot."""
        return self.original_capacity

    @property
    def simulated_total_capacity(self) -> CapacitySnapshot:
        """Return the simulated CPU and memory capacity snapshot."""
        return self.simulated_capacity


@dataclass(frozen=True)
class ScaleOutImpactResult:
    """Structured instance-count and capacity impact for scale out."""

    service_name: str
    original_instance_count: int
    simulated_instance_count: int
    instance_count_change: int
    original_capacity: CapacitySnapshot
    simulated_capacity: CapacitySnapshot
    capacity_change: CapacitySnapshot

    @property
    def original_total_capacity(self) -> CapacitySnapshot:
        """Return the original CPU and memory capacity snapshot."""
        return self.original_capacity

    @property
    def simulated_total_capacity(self) -> CapacitySnapshot:
        """Return the simulated CPU and memory capacity snapshot."""
        return self.simulated_capacity


class ScenarioImpactAnalyzer:
    """Compare immutable snapshots of original and simulated infrastructure."""

    def analyze_traffic(
        self,
        original: Infrastructure,
        simulation: TrafficSurgeResult,
    ) -> TrafficImpactResult:
        """Analyze request-rate changes from a traffic surge result."""
        original_service, simulated_service = self._services(
            original, simulation.infrastructure, simulation.service_name
        )
        original_rate = self._request_rate(original_service)
        simulated_rate = self._request_rate(simulated_service)
        absolute_change = simulated_rate - original_rate
        percentage_change = (
            absolute_change / original_rate * 100 if original_rate else 0.0
        )
        return TrafficImpactResult(
            service_name=simulation.service_name,
            original_request_rate=original_rate,
            simulated_request_rate=simulated_rate,
            absolute_change=absolute_change,
            percentage_change=percentage_change,
        )

    def analyze_instance_failure(
        self,
        original: Infrastructure,
        simulation: InstanceFailureResult,
    ) -> InstanceFailureImpactResult:
        """Analyze health and remaining capacity after an instance failure."""
        original_service, simulated_service = self._services(
            original, simulation.infrastructure, simulation.service_name
        )
        original_capacity = self._capacity(original_service)
        simulated_capacity = CapacitySnapshot(
            cpu=simulation.remaining_cpu_capacity,
            memory=simulation.remaining_memory_capacity,
        )
        original_healthy_count = self._healthy_count(original_service)
        simulated_healthy_count = self._healthy_count(simulated_service)
        return InstanceFailureImpactResult(
            service_name=simulation.service_name,
            original_instance_count=len(original_service.instances),
            simulated_instance_count=len(simulated_service.instances),
            original_healthy_instance_count=original_healthy_count,
            simulated_healthy_instance_count=simulated_healthy_count,
            original_capacity=original_capacity,
            simulated_capacity=simulated_capacity,
            capacity_change=CapacitySnapshot(
                cpu=simulated_capacity.cpu - original_capacity.cpu,
                memory=simulated_capacity.memory - original_capacity.memory,
            ),
            healthy_instance_change=simulated_healthy_count - original_healthy_count,
        )

    def analyze_scale_out(
        self,
        original: Infrastructure,
        simulation: ScaleOutResult,
    ) -> ScaleOutImpactResult:
        """Analyze instance-count and capacity changes from scale out."""
        original_service, simulated_service = self._services(
            original, simulation.infrastructure, simulation.service_name
        )
        original_capacity = self._capacity(original_service)
        simulated_capacity = self._capacity(simulated_service)
        return ScaleOutImpactResult(
            service_name=simulation.service_name,
            original_instance_count=original_service.effective_instance_count,
            simulated_instance_count=(
                original_service.effective_instance_count
                + simulation.additional_instances
            ),
            instance_count_change=simulation.additional_instances,
            original_capacity=original_capacity,
            simulated_capacity=simulated_capacity,
            capacity_change=CapacitySnapshot(
                cpu=simulated_capacity.cpu - original_capacity.cpu,
                memory=simulated_capacity.memory - original_capacity.memory,
            ),
        )

    @staticmethod
    def _services(
        original: Infrastructure,
        simulated: Infrastructure,
        service_name: str,
    ) -> tuple[Service, Service]:
        try:
            original_service = original.get_service(service_name)
            simulated_service = simulated.get_service(service_name)
        except KeyError as error:
            raise AnalysisError(
                f"service '{service_name}' must exist in both infrastructure states"
            ) from error
        return original_service, simulated_service

    @staticmethod
    def _request_rate(service: Service) -> float:
        return sum(instance.request_rate for instance in service.instances.values())

    @staticmethod
    def _healthy_count(service: Service) -> int:
        return sum(
            instance.status is InstanceStatus.HEALTHY
            for instance in service.instances.values()
        )

    @staticmethod
    def _capacity(service: Service) -> CapacitySnapshot:
        return CapacitySnapshot(
            cpu=service.total_cpu_capacity,
            memory=service.total_memory_capacity,
        )