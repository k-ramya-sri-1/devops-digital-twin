import importlib
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.src.main import app
from app.src.routes.experiments import get_validation_service


actual_result_module = importlib.import_module("digital-twin.actual_result")
comparison_module = importlib.import_module("digital-twin.prediction_comparison")
validation_module = importlib.import_module("digital-twin.validation")

ActualKubernetesResult = actual_result_module.ActualKubernetesResult
PredictionMetricComparison = comparison_module.PredictionMetricComparison
PredictionVsActualResult = comparison_module.PredictionVsActualResult
ValidationError = validation_module.ValidationError
ValidationResult = validation_module.ValidationResult


def make_validation_result() -> ValidationResult:
    actual_result = ActualKubernetesResult(
        experiment_id="EXP-API",
        deployment_name="devops-digital-twin",
        namespace="default",
        desired_replicas=4,
        ready_replicas=4,
        available_replicas=4,
        updated_replicas=4,
    )
    comparison = PredictionVsActualResult(
        experiment_id="EXP-API",
        comparisons=(
            PredictionMetricComparison(
                metric_name="replica_count",
                expected=4,
                actual=4,
                absolute_error=0.0,
                percentage_error=0.0,
                status="MATCH",
            ),
        ),
        overall_status="MATCH",
    )
    return ValidationResult("EXP-API", actual_result, comparison)


@pytest.fixture
def validation_setup():
    service = MagicMock()
    service.validate.return_value = make_validation_result()
    app.dependency_overrides[get_validation_service] = lambda: service
    with TestClient(app) as client:
        yield client, service
    app.dependency_overrides.clear()


def test_successful_validation_response_and_service_delegation(validation_setup):
    client, service = validation_setup

    response = client.post("/experiments/EXP-API/validate")

    assert response.status_code == 200
    assert response.json() == {
        "experiment_id": "EXP-API",
        "actual_result": {
            "experiment_id": "EXP-API",
            "deployment_name": "devops-digital-twin",
            "namespace": "default",
            "desired_replicas": 4,
            "ready_replicas": 4,
            "available_replicas": 4,
            "updated_replicas": 4,
        },
        "prediction_comparison": {
            "experiment_id": "EXP-API",
            "comparisons": [
                {
                    "metric_name": "replica_count",
                    "expected": 4,
                    "actual": 4,
                    "absolute_error": 0.0,
                    "percentage_error": 0.0,
                    "status": "MATCH",
                }
            ],
            "overall_status": "MATCH",
        },
    }
    service.validate.assert_called_once_with("EXP-API")


@pytest.mark.parametrize(
    ("message", "expected_status"),
    [
        ("experiment not found: EXP-API", 404),
        ("persisted execution result not found: EXP-API", 404),
        ("experiment must be in EXECUTED status before validation", 409),
        ("actual Kubernetes result could not be collected", 503),
        ("actual result and prediction comparison could not be persisted", 503),
        ("prediction metrics could not be mapped", 422),
    ],
)
def test_validation_errors_use_controlled_http_statuses(
    validation_setup, message, expected_status
):
    client, service = validation_setup
    service.validate.side_effect = ValidationError(message)

    response = client.post("/experiments/EXP-API/validate")

    assert response.status_code == expected_status
    assert response.json() == {"detail": message}


def test_validation_response_serializes_actual_result(validation_setup):
    client, _ = validation_setup

    actual_result = client.post("/experiments/EXP-API/validate").json()["actual_result"]

    assert actual_result["desired_replicas"] == 4
    assert actual_result["ready_replicas"] == 4
    assert actual_result["available_replicas"] == 4
    assert actual_result["updated_replicas"] == 4


def test_validation_response_serializes_prediction_comparison(validation_setup):
    client, _ = validation_setup

    comparison = client.post("/experiments/EXP-API/validate").json()[
        "prediction_comparison"
    ]

    assert comparison["overall_status"] == "MATCH"
    assert comparison["comparisons"][0]["metric_name"] == "replica_count"
    assert comparison["comparisons"][0]["status"] == "MATCH"