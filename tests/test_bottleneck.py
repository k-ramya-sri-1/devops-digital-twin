import importlib

import pytest


models = importlib.import_module("digital-twin.models")
bottleneck = importlib.import_module("digital-twin.bottleneck")
Infrastructure = models.Infrastructure
Instance = models.Instance
InstanceStatus = models.InstanceStatus
Service = models.Service
BottleneckDetector = bottleneck.BottleneckDetector
BottleneckError = bottleneck.BottleneckError
BottleneckStatus = bottleneck.BottleneckStatus
BottleneckThresholds = bottleneck.BottleneckThresholds


def make_infrastructure(
    *, cpu: float = 50.0, memory: float = 40.0, unhealthy: int = 0
) -> Infrastructure:
    service = Service(name="devops-digital-twin")
    for index in range(3):
        status = InstanceStatus.UNHEALTHY if index < unhealthy else InstanceStatus.HEALTHY
        service.add_instance(
            Instance(
                name=f"instance-{index + 1}",
                cpu_capacity=2.0,
                memory_capacity=1024.0,
                cpu_utilization=cpu,
                memory_utilization=memory,
                status=status,
            )
        )
    infrastructure = Infrastructure()
    infrastructure.add_service(service)
    return infrastructure


def test_normal_cpu_utilization() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(cpu=50.0), "devops-digital-twin"
    )

    assert result.cpu_utilization == 50.0
    assert result.cpu_status is BottleneckStatus.NORMAL


def test_warning_cpu_utilization() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(cpu=70.0), "devops-digital-twin"
    )

    assert result.cpu_status is BottleneckStatus.WARNING


def test_cpu_bottleneck() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(cpu=85.0), "devops-digital-twin"
    )

    assert result.cpu_status is BottleneckStatus.BOTTLENECK
    assert result.overall_status is BottleneckStatus.BOTTLENECK


def test_normal_memory_utilization() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(memory=40.0), "devops-digital-twin"
    )

    assert result.memory_utilization == 40.0
    assert result.memory_status is BottleneckStatus.NORMAL


def test_memory_bottleneck() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(memory=90.0), "devops-digital-twin"
    )

    assert result.memory_status is BottleneckStatus.BOTTLENECK
    assert result.overall_status is BottleneckStatus.BOTTLENECK


def test_unhealthy_instances_are_reported() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(unhealthy=1), "devops-digital-twin"
    )

    assert result.total_instance_count == 3
    assert result.healthy_instance_count == 2
    assert result.unhealthy_instance_count == 1
    assert result.overall_status is BottleneckStatus.WARNING
    assert any("unhealthy" in reason for reason in result.reasons)


def test_zero_healthy_instances_are_a_bottleneck() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(unhealthy=3), "devops-digital-twin"
    )

    assert result.healthy_instance_count == 0
    assert result.overall_status is BottleneckStatus.BOTTLENECK
    assert "no healthy instances are available" in result.reasons


def test_overall_warning_state() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(cpu=75.0, memory=50.0), "devops-digital-twin"
    )

    assert result.cpu_status is BottleneckStatus.WARNING
    assert result.memory_status is BottleneckStatus.NORMAL
    assert result.overall_status is BottleneckStatus.WARNING


def test_insufficient_utilization_data() -> None:
    result = BottleneckDetector().analyze(
        make_infrastructure(cpu=0.0, memory=0.0), "devops-digital-twin"
    )

    assert result.cpu_utilization is None
    assert result.memory_utilization is None
    assert result.cpu_status is BottleneckStatus.INSUFFICIENT_DATA
    assert result.memory_status is BottleneckStatus.INSUFFICIENT_DATA
    assert result.overall_status is BottleneckStatus.INSUFFICIENT_DATA


def test_custom_thresholds() -> None:
    thresholds = BottleneckThresholds(warning=60.0, bottleneck=80.0)
    result = BottleneckDetector(thresholds).analyze(
        make_infrastructure(cpu=60.0), "devops-digital-twin"
    )

    assert result.cpu_status is BottleneckStatus.WARNING


def test_invalid_thresholds_are_rejected() -> None:
    with pytest.raises(BottleneckError):
        BottleneckThresholds(warning=85.0, bottleneck=70.0)
    with pytest.raises(BottleneckError):
        BottleneckThresholds(warning=-1.0, bottleneck=85.0)
    with pytest.raises(BottleneckError):
        BottleneckThresholds(warning=70.0, bottleneck=101.0)


def test_unknown_service_is_rejected() -> None:
    with pytest.raises(BottleneckError, match="unknown service"):
        BottleneckDetector().analyze(make_infrastructure(), "missing")


def test_original_infrastructure_remains_unchanged() -> None:
    infrastructure = make_infrastructure(cpu=75.0, unhealthy=1)
    before = [
        (instance.status, instance.cpu_utilization, instance.memory_utilization)
        for instance in infrastructure.get_service("devops-digital-twin").instances.values()
    ]

    BottleneckDetector().analyze(infrastructure, "devops-digital-twin")

    after = [
        (instance.status, instance.cpu_utilization, instance.memory_utilization)
        for instance in infrastructure.get_service("devops-digital-twin").instances.values()
    ]
    assert after == before