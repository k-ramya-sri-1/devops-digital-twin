"""Provide the current Digital Twin state from Prometheus."""

from .collector import PrometheusCollector
from .models import Infrastructure


class CurrentStateService:
    """Coordinate access to the existing Prometheus collector."""

    def __init__(self, collector: PrometheusCollector) -> None:
        self._collector = collector

    def get_current_state(self) -> Infrastructure:
        """Return the current infrastructure collected from Prometheus."""
        return self._collector.collect()