import importlib

import pytest


models = importlib.import_module("digital-twin.models")
current_state = importlib.import_module("digital-twin.current_state")
Infrastructure = models.Infrastructure
CurrentStateService = current_state.CurrentStateService


class FakeCollector:
    def __init__(self, state=None, error=None):
        self.state = state
        self.error = error
        self.collect_calls = 0

    def collect(self):
        self.collect_calls += 1
        if self.error is not None:
            raise self.error
        return self.state


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