import importlib

import pytest


models = importlib.import_module("digital-twin.models")
simulator_module = importlib.import_module("digital-twin.simulator")
Infrastructure = models.Infrastructure
Instance = models.Instance
InstanceStatus = models.InstanceStatus
Service = models.Service
DigitalTwinSimulator = simulator_module.DigitalTwinSimulator
SimulationError = simulator_module.SimulationError


def make_infrastructure() -> Infrastructure:
    service = Service(name="devops-digital-twin")
    service.add_instance(
        Instance(
            name="instance-1",
            cpu_capacity=2.0,
            memory_capacity=1024.0,
            request_rate=100.0,
            status=InstanceStatus.HEALTHY,
        )
    )
    service.add_instance(
        Instance(
            name="instance-2",
            cpu_capacity=2.0,
            memory_capacity=1024.0,
            request_rate=50.0,
            status=InstanceStatus.HEALTHY,
        )
    )
    infrastructure = Infrastructure()
    infrastructure.add_service(service)
    return infrastructure


def test_traffic_surge_calculates_simulated_request_rate() -> None:
    infrastructure = make_infrastructure()

    result = DigitalTwinSimulator().traffic_surge(
        infrastructure, "devops-digital-twin", 2
    )

    assert result.original_request_rate == 150.0
    assert result.simulated_request_rate == 300.0
    assert result.infrastructure.get_service("devops-digital-twin").get_instance(
        "instance-1"
    ).request_rate == 200.0


def test_instance_failure_reports_health_and_remaining_capacity() -> None:
    infrastructure = make_infrastructure()

    result = DigitalTwinSimulator().instance_failure(
        infrastructure, "devops-digital-twin", "instance-1"
    )

    assert result.healthy_instance_count == 1
    assert result.unhealthy_instance_count == 1
    assert result.remaining_cpu_capacity == 2.0
    assert result.remaining_memory_capacity == 1024.0
    assert (
        result.infrastructure.get_service("devops-digital-twin")
        .get_instance("instance-1")
        .status
        is InstanceStatus.UNHEALTHY
    )


def test_scale_out_reports_instance_count_and_total_capacity() -> None:
    infrastructure = make_infrastructure()

    result = DigitalTwinSimulator().scale_out(
        infrastructure, "devops-digital-twin", 2
    )

    assert result.simulated_instance_count == 4
    assert result.total_cpu_capacity == 8.0
    assert result.total_memory_capacity == 4096.0


def test_unknown_service_is_rejected() -> None:
    with pytest.raises(SimulationError, match="unknown service"):
        DigitalTwinSimulator().traffic_surge(make_infrastructure(), "missing", 2)


def test_unknown_instance_is_rejected() -> None:
    with pytest.raises(SimulationError, match="unknown instance"):
        DigitalTwinSimulator().instance_failure(
            make_infrastructure(), "devops-digital-twin", "missing"
        )


@pytest.mark.parametrize("multiplier", [0, -1, float("inf"), "2"])
def test_invalid_multiplier_is_rejected(multiplier: object) -> None:
    with pytest.raises(SimulationError, match="traffic multiplier"):
        DigitalTwinSimulator().traffic_surge(
            make_infrastructure(), "devops-digital-twin", multiplier
        )


@pytest.mark.parametrize("count", [0, -1, 1.5, True])
def test_invalid_scale_count_is_rejected(count: object) -> None:
    with pytest.raises(SimulationError, match="additional instances"):
        DigitalTwinSimulator().scale_out(
            make_infrastructure(), "devops-digital-twin", count
        )


def test_simulations_leave_original_infrastructure_unchanged() -> None:
    infrastructure = make_infrastructure()
    original_service = infrastructure.get_service("devops-digital-twin")

    surge = DigitalTwinSimulator().traffic_surge(
        infrastructure, "devops-digital-twin", 2
    )
    failure = DigitalTwinSimulator().instance_failure(
        infrastructure, "devops-digital-twin", "instance-1"
    )
    scale = DigitalTwinSimulator().scale_out(
        infrastructure, "devops-digital-twin", 1
    )

    assert original_service.get_instance("instance-1").request_rate == 100.0
    assert (
        original_service.get_instance("instance-1").status
        is InstanceStatus.HEALTHY
    )
    assert len(original_service.instances) == 2
    assert surge.infrastructure is not infrastructure
    assert failure.infrastructure is not infrastructure
    assert scale.infrastructure is not infrastructure