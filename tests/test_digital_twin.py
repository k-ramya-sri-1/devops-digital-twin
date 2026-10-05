import importlib

import pytest


models = importlib.import_module("digital-twin.models")
Infrastructure = models.Infrastructure
Instance = models.Instance
InstanceStatus = models.InstanceStatus
Service = models.Service


def make_instance(
    name: str = "instance-1",
    status: InstanceStatus = InstanceStatus.HEALTHY,
) -> Instance:
    return Instance(
        name=name,
        cpu_capacity=2.0,
        memory_capacity=1024.0,
        cpu_utilization=25.0,
        memory_utilization=40.0,
        request_rate=10.0,
        status=status,
    )


def test_instance_creation() -> None:
    instance = make_instance()

    assert instance.name == "instance-1"
    assert instance.cpu_capacity == 2.0
    assert instance.memory_capacity == 1024.0
    assert instance.status is InstanceStatus.HEALTHY


def test_service_adds_instances_and_dependencies() -> None:
    service = Service(name="devops-digital-twin", dependencies={"database"})
    instance = make_instance()

    service.add_instance(instance)
    service.add_dependency("cache")

    assert service.get_instance("instance-1") is instance
    assert service.dependencies == {"database", "cache"}


def test_infrastructure_adds_and_gets_service() -> None:
    infrastructure = Infrastructure()
    service = Service(name="devops-digital-twin")

    infrastructure.add_service(service)

    assert infrastructure.get_service("devops-digital-twin") is service


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("cpu_capacity", -1.0),
        ("memory_capacity", -1.0),
        ("request_rate", -1.0),
    ],
)
def test_non_negative_values_are_validated(field_name: str, value: float) -> None:
    values = {"cpu_capacity": 2.0, "memory_capacity": 1024.0}
    values[field_name] = value

    with pytest.raises(ValueError):
        Instance(name="instance-1", **values)


@pytest.mark.parametrize("field_name", ["cpu_utilization", "memory_utilization"])
@pytest.mark.parametrize("value", [-0.1, 100.1])
def test_utilization_is_validated(field_name: str, value: float) -> None:
    values = {
        "cpu_capacity": 2.0,
        "memory_capacity": 1024.0,
        "cpu_utilization": 0.0,
        "memory_utilization": 0.0,
    }
    values[field_name] = value

    with pytest.raises(ValueError):
        Instance(name="instance-1", **values)


def test_unhealthy_instances_are_detected() -> None:
    service = Service(name="devops-digital-twin")
    service.add_instance(make_instance("instance-1"))
    service.add_instance(make_instance("instance-2", InstanceStatus.UNHEALTHY))
    service.add_instance(make_instance("instance-3", InstanceStatus.STOPPED))

    assert [instance.name for instance in service.unhealthy_instances] == [
        "instance-2",
        "instance-3",
    ]


def test_capacity_and_average_utilization_calculations() -> None:
    service = Service(name="devops-digital-twin")
    service.add_instance(make_instance("instance-1"))
    service.add_instance(
        Instance(
            name="instance-2",
            cpu_capacity=4.0,
            memory_capacity=2048.0,
            cpu_utilization=75.0,
            memory_utilization=60.0,
            request_rate=20.0,
            status=InstanceStatus.HEALTHY,
        )
    )
    infrastructure = Infrastructure()
    infrastructure.add_service(service)

    assert service.total_cpu_capacity == 6.0
    assert service.total_memory_capacity == 3072.0
    assert service.average_cpu_utilization == 50.0
    assert service.average_memory_utilization == 50.0
    assert infrastructure.total_cpu_capacity == 6.0
    assert infrastructure.total_memory_capacity == 3072.0
    assert infrastructure.average_cpu_utilization == 50.0
    assert infrastructure.average_memory_utilization == 50.0