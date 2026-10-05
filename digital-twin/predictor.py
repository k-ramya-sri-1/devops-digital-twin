"""Explainable, non-ML resource-demand projections for Digital Twin state."""

from dataclasses import dataclass
from enum import Enum
from typing import Union

from .models import Infrastructure, InstanceStatus, Service
from .simulator import InstanceFailureResult, ScaleOutResult, TrafficSurgeResult


class PredictionError(ValueError):
    """Raised when resource-demand prediction input is invalid."""


class ResourceStatus(str, Enum):
    """Outcome of comparing projected demand with healthy capacity."""

    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


SimulationResult = Union[TrafficSurgeResult, InstanceFailureResult, ScaleOutResult]


@dataclass(frozen=True)
class ResourcePredictionResult:
    """Structured explainable resource-demand projection for one service."""

    service_name: str
    original_request_rate: float
    simulated_request_rate: float | None
    workload_multiplier: float | None
    healthy_instance_count: int
    total_instance_count: int
    cpu_capacity: float
    memory_capacity: float
    healthy_cpu_capacity: float
    healthy_memory_capacity: float
    projected_cpu_demand: float | None
    projected_memory_demand: float | None
    cpu_status: ResourceStatus
    memory_status: ResourceStatus
    insufficient_data: tuple[str, ...]

    @property
    def has_sufficient_data(self) -> bool:
        """Return whether both resource projections were calculated."""
        return not self.insufficient_data


class ResourceDemandPredictor:
    """Project resource demand using state values and a simulation multiplier."""

    def predict(
        self,
        infrastructure: Infrastructure,
        service_name: str,
        simulation: SimulationResult | None = None,
    ) -> ResourcePredictionResult:
        """Create a deterministic projection without mutating either input."""
        service = self._get_service(infrastructure, service_name)
        simulated_service = None
        if simulation is not None:
            if simulation.service_name != service_name:
                raise PredictionError(
                    "simulation service does not match the selected service"
                )
            simulated_service = self._get_service(
                simulation.infrastructure, service_name
            )

        healthy_instances = [
            instance
            for instance in service.instances.values()
            if instance.status is InstanceStatus.HEALTHY
        ]
        original_request_rate = self._request_rate(service)
        simulated_request_rate = (
            self._request_rate(simulated_service)
            if simulated_service is not None
            else None
        )
        workload_multiplier = self._workload_multiplier(
            original_request_rate, simulated_request_rate
        )
        insufficient_data: list[str] = []
        if simulated_service is None:
            insufficient_data.append("simulated_request_rate")
        elif workload_multiplier is None:
            insufficient_data.append("workload_multiplier")

        projected_cpu_demand = self._project_resource(
            healthy_instances,
            resource="cpu",
            multiplier=workload_multiplier,
            insufficient_data=insufficient_data,
        )
        projected_memory_demand = self._project_resource(
            healthy_instances,
            resource="memory",
            multiplier=workload_multiplier,
            insufficient_data=insufficient_data,
        )
        cpu_status = self._resource_status(
            projected_cpu_demand, sum(i.cpu_capacity for i in healthy_instances)
        )
        memory_status = self._resource_status(
            projected_memory_demand,
            sum(i.memory_capacity for i in healthy_instances),
        )
        if not healthy_instances:
            insufficient_data.append("healthy_instances")
            cpu_status = ResourceStatus.INSUFFICIENT_DATA
            memory_status = ResourceStatus.INSUFFICIENT_DATA

        return ResourcePredictionResult(
            service_name=service_name,
            original_request_rate=original_request_rate,
            simulated_request_rate=simulated_request_rate,
            workload_multiplier=workload_multiplier,
            healthy_instance_count=len(healthy_instances),
            total_instance_count=len(service.instances),
            cpu_capacity=service.total_cpu_capacity,
            memory_capacity=service.total_memory_capacity,
            healthy_cpu_capacity=sum(i.cpu_capacity for i in healthy_instances),
            healthy_memory_capacity=sum(
                i.memory_capacity for i in healthy_instances
            ),
            projected_cpu_demand=projected_cpu_demand,
            projected_memory_demand=projected_memory_demand,
            cpu_status=cpu_status,
            memory_status=memory_status,
            insufficient_data=tuple(dict.fromkeys(insufficient_data)),
        )

    @staticmethod
    def _get_service(
        infrastructure: Infrastructure, service_name: str
    ) -> Service:
        if not service_name or not service_name.strip():
            raise PredictionError("service name must not be empty")
        try:
            return infrastructure.get_service(service_name)
        except KeyError as error:
            raise PredictionError(f"unknown service '{service_name}'") from error

    @staticmethod
    def _request_rate(service: Service) -> float:
        return sum(instance.request_rate for instance in service.instances.values())

    @staticmethod
    def _workload_multiplier(
        original_request_rate: float,
        simulated_request_rate: float | None,
    ) -> float | None:
        if simulated_request_rate is None or original_request_rate <= 0:
            return None
        return simulated_request_rate / original_request_rate

    @staticmethod
    def _project_resource(
        healthy_instances: list,
        resource: str,
        multiplier: float | None,
        insufficient_data: list[str],
    ) -> float | None:
        if multiplier is None:
            return None
        utilization_values = [
            getattr(instance, f"{resource}_utilization")
            for instance in healthy_instances
        ]
        if not any(value > 0 for value in utilization_values):
            insufficient_data.append(f"{resource}_utilization")
            return None
        baseline_demand = sum(
            getattr(instance, f"{resource}_capacity") * utilization / 100
            for instance, utilization in zip(healthy_instances, utilization_values)
        )
        return baseline_demand * multiplier

    @staticmethod
    def _resource_status(
        projected_demand: float | None,
        healthy_capacity: float,
    ) -> ResourceStatus:
        if projected_demand is None:
            return ResourceStatus.INSUFFICIENT_DATA
        if projected_demand <= healthy_capacity:
            return ResourceStatus.SUFFICIENT
        return ResourceStatus.INSUFFICIENT