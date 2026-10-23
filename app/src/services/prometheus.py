"""Dependency providers for Prometheus-backed services."""

import importlib
import os


collector_module = importlib.import_module("digital-twin.collector")
PrometheusCollector = collector_module.PrometheusCollector


def get_prometheus_collector() -> PrometheusCollector:
    """Provide a Prometheus collector using the configured API base URL."""
    return PrometheusCollector(
        os.getenv("PROMETHEUS_URL", "http://localhost:9090")
    )
