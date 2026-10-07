"""Provide the current Digital Twin state from Prometheus."""

from collections.abc import Callable

from .collector import PrometheusCollector
from .models import Infrastructure


class CurrentStateService:
    """Coordinate access to the existing Prometheus collector."""

    def __init__(
        self,
        collector: PrometheusCollector,
        replica_count_provider: Callable[[], int] | None = None,
    ) -> None:
        self._collector = collector
        self._replica_count_provider = replica_count_provider

    def get_current_state(self) -> Infrastructure:
        """Return the current infrastructure collected from Prometheus."""
        state = self._collector.collect()
        if self._replica_count_provider is not None:
            replica_count = self._replica_count_provider()
            service = state.get_service(self._collector.SERVICE_NAME)
            service.set_replica_count(replica_count)
        return state