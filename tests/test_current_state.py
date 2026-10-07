import importlib

import pytest


models = importlib.import_module("digital-twin.models")
current_state = importlib.import_module("digital-twin.current_state")
Infrastructure = models.Infrastructure
CurrentStateService = current_state.CurrentStateService


class FakeCollector:
    SERVICE_NAME = "devops-digital-twin"

    def __init__(self, state=None, error=None):
        self.state = state
        self.error = error
        self.collect_calls = 0

    def collect(self):
        self.collect_calls += 1
        if self.error is not None:
            raise self.error
        return self.state


def make_state() -> Infrastructure:
    service = models.Service(name=FakeCollector.SERVICE_NAME)
    service.add_instance(
        models.Instance(
            name="devops-digital-twin-service",
            cpu_capacity=0.0,
            memory_capacity=0.0,
        )
    )
    state = Infrastructure()
    state.add_service(service)
    return state


def test_get_current_state_returns_collected_infrastructure() -> None:
    infrastructure = Infrastructure()
    collector = FakeCollector(infrastructure)

    result = CurrentStateService(collector).get_current_state()

    assert result is infrastructure
    assert collector.collect_calls == 1


def test_collector_errors_propagate() -> None:
    error = RuntimeError("collector failed")
    collector = FakeCollector(error=error)

    with pytest.raises(RuntimeError, match="collector failed"):
        CurrentStateService(collector).get_current_state()

    assert collector.collect_calls == 1


def test_replica_count_provider_is_combined_with_prometheus_state() -> None:
    state = make_state()
    collector = FakeCollector(state)
    provider_calls = []

    def provider() -> int:
        provider_calls.append(True)
        return 3

    result = CurrentStateService(collector, provider).get_current_state()

    service = result.get_service(FakeCollector.SERVICE_NAME)
    assert service.replica_count == 3
    assert service.effective_instance_count == 3
    assert len(service.instances) == 1
    assert provider_calls == [True]


def test_replica_count_provider_errors_propagate() -> None:
    collector = FakeCollector(make_state())

    with pytest.raises(RuntimeError, match="deployment unavailable"):
        CurrentStateService(
            collector,
            lambda: (_ for _ in ()).throw(RuntimeError("deployment unavailable")),
        ).get_current_state()