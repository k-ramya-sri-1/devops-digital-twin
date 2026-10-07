"""Typed, in-memory infrastructure state for the DevOps Digital Twin."""

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Iterable


class InstanceStatus(str, Enum):
    """Lifecycle and health states supported by an infrastructure instance."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPED = "stopped"


def _validate_non_negative(value: float, field_name: str) -> None:
    if not isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative finite number")


def _validate_utilization(value: float, field_name: str) -> None:
    if not isfinite(value) or not 0 <= value <= 100:
        raise ValueError(f"{field_name} must be between 0 and 100")


def _validate_name(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


@dataclass
class Instance:
    """Represent one application instance or pod and its current state."""

    name: str
    cpu_capacity: float
    memory_capacity: float
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    request_rate: float = 0.0
    status: InstanceStatus = InstanceStatus.STARTING
    request_count: float = 0.0
    request_latency_count: float = 0.0

    def __post_init__(self) -> None:
        _validate_name(self.name, "name")
        _validate_non_negative(self.cpu_capacity, "cpu_capacity")
        _validate_non_negative(self.memory_capacity, "memory_capacity")
        _validate_utilization(self.cpu_utilization, "cpu_utilization")
        _validate_utilization(self.memory_utilization, "memory_utilization")
        _validate_non_negative(self.request_rate, "request_rate")
        _validate_non_negative(self.request_count, "request_count")
        _validate_non_negative(
            self.request_latency_count, "request_latency_count"
        )
        if isinstance(self.status, str):
            try:
                self.status = InstanceStatus(self.status)
            except ValueError as error:
                raise ValueError(f"unsupported instance status: {self.status}") from error
        elif not isinstance(self.status, InstanceStatus):
            raise ValueError("status must be an InstanceStatus")


@dataclass
class Service:
    """Represent an application service, its instances, and dependencies."""

    name: str
    dependencies: set[str] = field(default_factory=set)
    instances: dict[str, Instance] = field(default_factory=dict)
    replica_count: int | None = None

    def __post_init__(self) -> None:
        _validate_name(self.name, "name")
        self.dependencies = set(self.dependencies)
        for dependency in self.dependencies:
            _validate_name(dependency, "dependency")
        for instance_name, instance in self.instances.items():
            if instance_name != instance.name:
                raise ValueError("instance dictionary keys must match instance names")
        self._validate_replica_count(self.replica_count)

    @property
    def effective_instance_count(self) -> int:
        """Return the observed replica count when one is available."""
        return (
            self.replica_count
            if self.replica_count is not None
            else len(self.instances)
        )

    def set_replica_count(self, replica_count: int) -> None:
        """Set the observed deployment replica count without adding instances."""
        self._validate_replica_count(replica_count)
        self.replica_count = replica_count

    @staticmethod
    def _validate_replica_count(replica_count: int | None) -> None:
        if replica_count is not None and (
            isinstance(replica_count, bool)
            or not isinstance(replica_count, int)
            or replica_count < 0
        ):
            raise ValueError(
                "replica_count must be a non-negative integer or None"
            )

    def add_dependency(self, dependency: str) -> None:
        """Add a named dependency to the service."""
        _validate_name(dependency, "dependency")
        self.dependencies.add(dependency)

    def remove_dependency(self, dependency: str) -> None:
        """Remove a dependency if it is present."""
        self.dependencies.discard(dependency)

    def add_instance(self, instance: Instance) -> None:
        """Add an instance, rejecting duplicate instance names."""
        if instance.name in self.instances:
            raise ValueError(f"instance already exists: {instance.name}")
        self.instances[instance.name] = instance

    def remove_instance(self, instance_name: str) -> Instance:
        """Remove and return an instance by name."""
        try:
            return self.instances.pop(instance_name)
        except KeyError as error:
            raise KeyError(f"instance not found: {instance_name}") from error

    def get_instance(self, instance_name: str) -> Instance:
        """Return an instance by name."""
        try:
            return self.instances[instance_name]
        except KeyError as error:
            raise KeyError(f"instance not found: {instance_name}") from error

    @property
    def total_cpu_capacity(self) -> float:
        """Return the aggregate CPU capacity across all instances."""
        return sum(instance.cpu_capacity for instance in self.instances.values())

    @property
    def total_memory_capacity(self) -> float:
        """Return the aggregate memory capacity across all instances."""
        return sum(instance.memory_capacity for instance in self.instances.values())

    @property
    def average_cpu_utilization(self) -> float:
        """Return the arithmetic mean CPU utilization across instances."""
        if not self.instances:
            return 0.0
        return sum(
            instance.cpu_utilization for instance in self.instances.values()
        ) / len(self.instances)

    @property
    def average_memory_utilization(self) -> float:
        """Return the arithmetic mean memory utilization across instances."""
        if not self.instances:
            return 0.0
        return sum(
            instance.memory_utilization for instance in self.instances.values()
        ) / len(self.instances)

    @property
    def unhealthy_instances(self) -> list[Instance]:
        """Return instances that are not currently healthy."""
        return [
            instance
            for instance in self.instances.values()
            if instance.status is not InstanceStatus.HEALTHY
        ]


@dataclass
class Infrastructure:
    """Contain the services that make up a Digital Twin infrastructure state."""

    services: dict[str, Service] = field(default_factory=dict)

    def add_service(self, service: Service) -> None:
        """Add a service, rejecting duplicate service names."""
        if service.name in self.services:
            raise ValueError(f"service already exists: {service.name}")
        self.services[service.name] = service

    def remove_service(self, service_name: str) -> Service:
        """Remove and return a service by name."""
        try:
            return self.services.pop(service_name)
        except KeyError as error:
            raise KeyError(f"service not found: {service_name}") from error

    def get_service(self, service_name: str) -> Service:
        """Return a service by name."""
        try:
            return self.services[service_name]
        except KeyError as error:
            raise KeyError(f"service not found: {service_name}") from error

    @property
    def total_cpu_capacity(self) -> float:
        """Return aggregate CPU capacity across all services."""
        return sum(service.total_cpu_capacity for service in self.services.values())

    @property
    def total_memory_capacity(self) -> float:
        """Return aggregate memory capacity across all services."""
        return sum(
            service.total_memory_capacity for service in self.services.values()
        )

    @property
    def average_cpu_utilization(self) -> float:
        """Return the arithmetic mean CPU utilization across all instances."""
        instances = self._instances()
        if not instances:
            return 0.0
        return sum(instance.cpu_utilization for instance in instances) / len(instances)

    @property
    def average_memory_utilization(self) -> float:
        """Return the arithmetic mean memory utilization across all instances."""
        instances = self._instances()
        if not instances:
            return 0.0
        return sum(instance.memory_utilization for instance in instances) / len(instances)

    @property
    def unhealthy_instances(self) -> list[Instance]:
        """Return all instances that are not currently healthy."""
        return [
            instance
            for service in self.services.values()
            for instance in service.unhealthy_instances
        ]

    def _instances(self) -> list[Instance]:
        return [
            instance
            for service in self.services.values()
            for instance in service.instances.values()
        ]


def service_from_instances(
    name: str,
    instances: Iterable[Instance],
    dependencies: Iterable[str] = (),
) -> Service:
    """Build a service from an iterable of instances and dependency names."""
    service = Service(name=name, dependencies=set(dependencies))
    for instance in instances:
        service.add_instance(instance)
    return service