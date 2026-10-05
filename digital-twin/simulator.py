"""Deterministic what-if simulations for Digital Twin infrastructure state."""

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite

from .models import Infrastructure, Instance, InstanceStatus, Service


class SimulationError(ValueError):
    """Raised when a simulation request cannot be applied to the state."""


@dataclass(frozen=True)
class TrafficSurgeResult:
    """Result of increasing a service's simulated request rate."""

    infrastructure: Infrastructure
    service_name: str
    multiplier: float
    original_request_rate: float
    simulated_request_rate: float


@dataclass(frozen=True)
class InstanceFailureResult:
    """Result of marking one simulated service instance unhealthy."""

    infrastructure: Infrastructure
    service_name: str
    instance_name: str
    healthy_instance_count: int
    unhealthy_instance_count: int
    remaining_cpu_capacity: float
    remaining_memory_capacity: float


@dataclass(frozen=True)
class ScaleOutResult:
    """Result of adding simulated instances to a service."""

    infrastructure: Infrastructure
    service_name: str
    additional_instances: int
    simulated_instance_count: int
    total_cpu_capacity: float
    total_memory_capacity: float


class DigitalTwinSimulator:
    """Run deterministic what-if scenarios without changing source state."""

    def traffic_surge(
        self,
        infrastructure: Infrastructure,
        service_name: str,
        multiplier: float,
    ) -> TrafficSurgeResult:
        """Simulate a traffic multiplier for every instance in a service."""
        self._validate_multiplier(multiplier)
        service = self._get_service(infrastructure, service_name)
        simulated = deepcopy(infrastructure)
        simulated_service = simulated.get_service(service.name)
        original_rate = sum(
            instance.request_rate for instance in service.instances.values()
        )
        for instance in simulated_service.instances.values():
            instance.request_rate *= multiplier

        return TrafficSurgeResult(
            infrastructure=simulated,
            service_name=service_name,
            multiplier=multiplier,
            original_request_rate=original_rate,
            simulated_request_rate=sum(
                instance.request_rate
                for instance in simulated_service.instances.values()
            ),
        )

    def instance_failure(
        self,
        infrastructure: Infrastructure,
        service_name: str,
        instance_name: str,
    ) -> InstanceFailureResult:
        """Simulate one instance becoming unhealthy and report capacity left."""
        service = self._get_service(infrastructure, service_name)
        if instance_name not in service.instances:
            raise SimulationError(
                f"unknown instance '{instance_name}' in service '{service_name}'"
            )

        simulated = deepcopy(infrastructure)
        simulated_service = simulated.get_service(service.name)
        simulated_service.get_instance(instance_name).status = InstanceStatus.UNHEALTHY
        healthy_instances = [
            instance
            for instance in simulated_service.instances.values()
            if instance.status is InstanceStatus.HEALTHY
        ]
        unhealthy_instances = simulated_service.unhealthy_instances

        return InstanceFailureResult(
            infrastructure=simulated,
            service_name=service_name,
            instance_name=instance_name,
            healthy_instance_count=len(healthy_instances),
            unhealthy_instance_count=len(unhealthy_instances),
            remaining_cpu_capacity=sum(
                instance.cpu_capacity for instance in healthy_instances
            ),
            remaining_memory_capacity=sum(
                instance.memory_capacity for instance in healthy_instances
            ),
        )

    def scale_out(
        self,
        infrastructure: Infrastructure,
        service_name: str,
        additional_instances: int,
    ) -> ScaleOutResult:
        """Simulate adding instances using existing service capacity as a template."""
        self._validate_scale_count(additional_instances)
        service = self._get_service(infrastructure, service_name)
        if not service.instances:
            raise SimulationError(
                f"service '{service_name}' has no instance capacity to replicate"
            )

        simulated = deepcopy(infrastructure)
        simulated_service = simulated.get_service(service.name)
        template = simulated_service.instances[sorted(simulated_service.instances)[0]]
        for index in range(1, additional_instances + 1):
            instance_name = self._next_instance_name(
                simulated_service, index
            )
            simulated_service.add_instance(
                Instance(
                    name=instance_name,
                    cpu_capacity=template.cpu_capacity,
                    memory_capacity=template.memory_capacity,
                    status=InstanceStatus.STARTING,
                )
            )

        return ScaleOutResult(
            infrastructure=simulated,
            service_name=service_name,
            additional_instances=additional_instances,
            simulated_instance_count=len(simulated_service.instances),
            total_cpu_capacity=simulated_service.total_cpu_capacity,
            total_memory_capacity=simulated_service.total_memory_capacity,
        )

    @staticmethod
    def _get_service(infrastructure: Infrastructure, service_name: str) -> Service:
        try:
            return infrastructure.get_service(service_name)
        except KeyError as error:
            raise SimulationError(f"unknown service '{service_name}'") from error

    @staticmethod
    def _validate_multiplier(multiplier: float) -> None:
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
            raise SimulationError("traffic multiplier must be a positive number")
        if not isfinite(multiplier) or multiplier <= 0:
            raise SimulationError("traffic multiplier must be a positive number")

    @staticmethod
    def _validate_scale_count(additional_instances: int) -> None:
        if isinstance(additional_instances, bool) or not isinstance(
            additional_instances, int
        ):
            raise SimulationError("additional instances must be a positive integer")
        if additional_instances <= 0:
            raise SimulationError("additional instances must be a positive integer")

    @staticmethod
    def _next_instance_name(service: Service, index: int) -> str:
        base_name = f"simulated-instance-{index}"
        if base_name not in service.instances:
            return base_name
        suffix = 1
        while f"{base_name}-{suffix}" in service.instances:
            suffix += 1
        return f"{base_name}-{suffix}"