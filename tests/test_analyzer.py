import importlib
from dataclasses import replace

import pytest


models = importlib.import_module("digital-twin.models")
simulator = importlib.import_module("digital-twin.simulator")
analyzer = importlib.import_module("digital-twin.analyzer")
Infrastructure = models.Infrastructure
Instance = models.Instance
InstanceStatus = models.InstanceStatus
Service = models.Service
DigitalTwinSimulator = simulator.DigitalTwinSimulator
AnalysisError = analyzer.AnalysisError
ScenarioImpactAnalyzer = analyzer.ScenarioImpactAnalyzer


def make_infrastructure(request_rate: float = 100.0) -> Infrastructure:
    service = Service(name="devops-digital-twin")
    for name in ("instance-1", "instance-2"):
        service.add_instance(
            Instance(
                name=name,
                cpu_capacity=2.0,
                memory_capacity=1024.0,
                request_rate=request_rate / 2,
                status=InstanceStatus.HEALTHY,
            )
        )
    infrastructure = Infrastructure()
    infrastructure.add_service(service)
    return infrastructure


def test_traffic_impact_calculation_and_percentage_change() -> None:
    infrastructure = make_infrastructure()
    simulation = DigitalTwinSimulator().traffic_surge(
        infrastructure, "devops-digital-twin", 2
    )

    result = ScenarioImpactAnalyzer().analyze_traffic(infrastructure, simulation)

    assert result.service_name == "devops-digital-twin"
    assert result.original_request_rate == 100.0
    assert result.simulated_request_rate == 200.0
    assert result.absolute_change == 100.0
    assert result.percentage_change == 100.0


def test_zero_original_request_rate_is_safe() -> None:
    infrastructure = make_infrastructure(request_rate=0.0)
    simulation = DigitalTwinSimulator().traffic_surge(
        infrastructure, "devops-digital-twin", 2
    )

    result = ScenarioImpactAnalyzer().analyze_traffic(infrastructure, simulation)

    assert result.original_request_rate == 0.0
    assert result.simulated_request_rate == 0.0
    assert result.percentage_change == 0.0


def test_instance_failure_impact_reports_health_and_capacity_changes() -> None:
    infrastructure = make_infrastructure()
    simulation = DigitalTwinSimulator().instance_failure(
        infrastructure, "devops-digital-twin", "instance-1"
    )

    result = ScenarioImpactAnalyzer().analyze_instance_failure(
        infrastructure, simulation
    )

    assert result.original_instance_count == 2
    assert result.simulated_instance_count == 2
    assert result.original_healthy_instance_count == 2
    assert result.simulated_healthy_instance_count == 1
    assert result.healthy_instance_change == -1
    assert result.original_total_capacity.cpu == 4.0
    assert result.simulated_total_capacity.cpu == 2.0
    assert result.capacity_change.cpu == -2.0
    assert result.capacity_change.memory == -1024.0


def test_scale_out_impact_reports_instance_and_capacity_changes() -> None:
    infrastructure = make_infrastructure()
    simulation = DigitalTwinSimulator().scale_out(
        infrastructure, "devops-digital-twin", 2
    )

    result = ScenarioImpactAnalyzer().analyze_scale_out(infrastructure, simulation)

    assert result.original_instance_count == 2
    assert result.simulated_instance_count == 4
    assert result.instance_count_change == 2
    assert result.original_total_capacity.cpu == 4.0
    assert result.simulated_total_capacity.cpu == 8.0
    assert result.capacity_change.cpu == 4.0
    assert result.capacity_change.memory == 2048.0


def test_scale_out_impact_uses_explicit_baseline_replica_count() -> None:
    infrastructure = make_infrastructure()
    infrastructure.get_service("devops-digital-twin").set_replica_count(3)
    simulation = DigitalTwinSimulator().scale_out(
        infrastructure, "devops-digital-twin", 2
    )

    result = ScenarioImpactAnalyzer().analyze_scale_out(infrastructure, simulation)

    assert result.original_instance_count == 3
    assert result.simulated_instance_count == 5
    assert result.instance_count_change == 2


def test_invalid_service_is_rejected() -> None:
    infrastructure = make_infrastructure()
    simulation = DigitalTwinSimulator().traffic_surge(
        infrastructure, "devops-digital-twin", 2
    )
    simulation = replace(simulation, service_name="missing")

    with pytest.raises(AnalysisError, match="must exist in both"):
        ScenarioImpactAnalyzer().analyze_traffic(infrastructure, simulation)


def test_original_infrastructure_remains_unchanged() -> None:
    infrastructure = make_infrastructure()
    original_rates = [
        instance.request_rate
        for instance in infrastructure.get_service("devops-digital-twin").instances.values()
    ]
    simulation = DigitalTwinSimulator().scale_out(
        infrastructure, "devops-digital-twin", 1
    )

    ScenarioImpactAnalyzer().analyze_scale_out(infrastructure, simulation)

    service = infrastructure.get_service("devops-digital-twin")
    assert len(service.instances) == 2
    assert [instance.request_rate for instance in service.instances.values()] == original_rates
    assert all(
        instance.status is InstanceStatus.HEALTHY
        for instance in service.instances.values()
    )