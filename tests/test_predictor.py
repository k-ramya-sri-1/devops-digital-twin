import importlib

import pytest


models = importlib.import_module("digital-twin.models")
simulator = importlib.import_module("digital-twin.simulator")
predictor = importlib.import_module("digital-twin.predictor")
Infrastructure = models.Infrastructure
Instance = models.Instance
InstanceStatus = models.InstanceStatus
Service = models.Service
DigitalTwinSimulator = simulator.DigitalTwinSimulator
PredictionError = predictor.PredictionError
ResourceDemandPredictor = predictor.ResourceDemandPredictor
ResourceStatus = predictor.ResourceStatus


def make_infrastructure(
    *,
    request_rate: float = 100.0,
    cpu_utilization: float = 50.0,
    memory_utilization: float = 25.0,
    healthy: bool = True,
) -> Infrastructure:
    service = Service(name="devops-digital-twin")
    status = InstanceStatus.HEALTHY if healthy else InstanceStatus.UNHEALTHY
    for name in ("instance-1", "instance-2"):
        service.add_instance(
            Instance(
                name=name,
                cpu_capacity=2.0,
                memory_capacity=1024.0,
                cpu_utilization=cpu_utilization,
                memory_utilization=memory_utilization,
                request_rate=request_rate / 2,
                status=status,
            )
        )
    infrastructure = Infrastructure()
    infrastructure.add_service(service)
    return infrastructure


def traffic_simulation(infrastructure: Infrastructure, multiplier: float = 2.0):
    return DigitalTwinSimulator().traffic_surge(
        infrastructure, "devops-digital-twin", multiplier
    )


def test_resource_capacity_calculation() -> None:
    infrastructure = make_infrastructure()

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.cpu_capacity == 4.0
    assert result.memory_capacity == 2048.0
    assert result.healthy_instance_count == 2
    assert result.total_instance_count == 2


def test_workload_multiplier_calculation() -> None:
    infrastructure = make_infrastructure()

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure, 3)
    )

    assert result.original_request_rate == 100.0
    assert result.simulated_request_rate == 300.0
    assert result.workload_multiplier == 3.0


def test_traffic_surge_projects_resources_when_baseline_data_exists() -> None:
    infrastructure = make_infrastructure()

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.projected_cpu_demand == 4.0
    assert result.projected_memory_demand == 1024.0
    assert result.cpu_status is ResourceStatus.SUFFICIENT
    assert result.memory_status is ResourceStatus.SUFFICIENT
    assert result.has_sufficient_data


def test_zero_baseline_request_rate_is_not_projectable() -> None:
    infrastructure = make_infrastructure(request_rate=0.0)

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.workload_multiplier is None
    assert result.projected_cpu_demand is None
    assert result.projected_memory_demand is None
    assert "workload_multiplier" in result.insufficient_data


def test_insufficient_cpu_data() -> None:
    infrastructure = make_infrastructure(cpu_utilization=0.0)

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.projected_cpu_demand is None
    assert result.cpu_status is ResourceStatus.INSUFFICIENT_DATA
    assert result.projected_memory_demand is not None


def test_insufficient_memory_data() -> None:
    infrastructure = make_infrastructure(memory_utilization=0.0)

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.projected_memory_demand is None
    assert result.memory_status is ResourceStatus.INSUFFICIENT_DATA
    assert result.projected_cpu_demand is not None


def test_healthy_capacity_is_sufficient() -> None:
    infrastructure = make_infrastructure()

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.healthy_cpu_capacity == 4.0
    assert result.healthy_memory_capacity == 2048.0
    assert result.cpu_status is ResourceStatus.SUFFICIENT


def test_insufficient_healthy_capacity() -> None:
    infrastructure = make_infrastructure(cpu_utilization=100.0)

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.projected_cpu_demand == 8.0
    assert result.healthy_cpu_capacity == 4.0
    assert result.cpu_status is ResourceStatus.INSUFFICIENT


def test_zero_healthy_instances_is_safe() -> None:
    infrastructure = make_infrastructure(healthy=False)

    result = ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", traffic_simulation(infrastructure)
    )

    assert result.healthy_instance_count == 0
    assert result.cpu_status is ResourceStatus.INSUFFICIENT_DATA
    assert result.memory_status is ResourceStatus.INSUFFICIENT_DATA
    assert "healthy_instances" in result.insufficient_data


def test_unknown_service_is_rejected() -> None:
    infrastructure = make_infrastructure()

    with pytest.raises(PredictionError, match="unknown service"):
        ResourceDemandPredictor().predict(infrastructure, "missing")


def test_invalid_input_is_rejected() -> None:
    infrastructure = make_infrastructure()

    with pytest.raises(PredictionError, match="service name"):
        ResourceDemandPredictor().predict(infrastructure, "")


def test_original_state_and_simulation_result_remain_unchanged() -> None:
    infrastructure = make_infrastructure()
    simulation = traffic_simulation(infrastructure)
    original_rates = [
        instance.request_rate
        for instance in infrastructure.get_service("devops-digital-twin").instances.values()
    ]
    simulated_rates = [
        instance.request_rate
        for instance in simulation.infrastructure.get_service(
            "devops-digital-twin"
        ).instances.values()
    ]

    ResourceDemandPredictor().predict(
        infrastructure, "devops-digital-twin", simulation
    )

    assert [
        instance.request_rate
        for instance in infrastructure.get_service("devops-digital-twin").instances.values()
    ] == original_rates
    assert [
        instance.request_rate
        for instance in simulation.infrastructure.get_service(
            "devops-digital-twin"
        ).instances.values()
    ] == simulated_rates