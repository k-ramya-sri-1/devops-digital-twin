import importlib

import pytest
from fastapi.testclient import TestClient

from app.src.main import app
from app.src.routes.experiments import (
    get_experiment_repository,
    get_experiment_result_repository,
)
from tests.test_deployment_impact import (
    make_actual,
    make_comparison,
    make_execution_result,
)


experiment_module = importlib.import_module("digital-twin.experiment")

Experiment = experiment_module.Experiment
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType

EXPERIMENT_ID = "EXP-027A"


class FakeExperimentRepository:
    def __init__(self, experiment=None):
        self.experiment = experiment
        self.get_calls = []
        self.write_calls = []

    def get_by_id(self, experiment_id):
        self.get_calls.append(experiment_id)
        return self.experiment


class FakeExperimentResultRepository:
    def __init__(self, result=None, actual=None, comparison=None):
        self.result = result
        self.actual = actual
        self.comparison = comparison
        self.get_calls = []
        self.actual_comparison_calls = []
        self.write_calls = []

    def get_by_experiment_id(self, experiment_id):
        self.get_calls.append(experiment_id)
        return self.result

    def get_actual_comparison(self, experiment_id):
        self.actual_comparison_calls.append(experiment_id)
        return self.actual, self.comparison


def make_experiment():
    return Experiment(
        experiment_id=EXPERIMENT_ID,
        name="impact API test",
        scenario_type=ScenarioType.SCALE_OUT,
        scenario_parameters=ScenarioParameters.scale_out(1),
        status=ExperimentStatus.EXECUTED,
    )


@pytest.fixture
def api_setup():
    experiment_repository = FakeExperimentRepository(make_experiment())
    result_repository = FakeExperimentResultRepository(make_execution_result())
    app.dependency_overrides[get_experiment_repository] = (
        lambda: experiment_repository
    )
    app.dependency_overrides[get_experiment_result_repository] = (
        lambda: result_repository
    )
    with TestClient(app) as client:
        yield client, experiment_repository, result_repository
    app.dependency_overrides.clear()


def test_returns_report_with_execution_result_only(api_setup):
    client, _, result_repository = api_setup

    response = client.get(f"/experiments/{EXPERIMENT_ID}/impact")

    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == EXPERIMENT_ID
    assert body["scenario_type"] == "SCALE_OUT"
    assert body["service_name"] == "devops-digital-twin"
    assert set(body) == {
        "experiment_id",
        "scenario_type",
        "service_name",
        "simulated_impact",
        "predicted_demand",
        "bottleneck",
        "actual_result",
        "prediction_accuracy",
        "overall_severity",
        "limitations",
    }
    assert body["actual_result"] is None
    assert body["prediction_accuracy"] is None
    assert body["overall_severity"] == "LOW"
    assert "actual validation is pending or unavailable" in body["limitations"]
    assert result_repository.actual_comparison_calls == [EXPERIMENT_ID]


def test_returns_optional_actual_and_comparison(api_setup):
    client, _, result_repository = api_setup
    result_repository.actual = make_actual()
    result_repository.comparison = make_comparison()

    response = client.get(f"/experiments/{EXPERIMENT_ID}/impact")

    assert response.status_code == 200
    body = response.json()
    assert body["actual_result"]["desired_replicas"] == 3
    assert body["prediction_accuracy"]["overall_status"] == "MATCH"
    assert body["limitations"] == []


def test_missing_experiment_returns_not_found(api_setup):
    client, experiment_repository, result_repository = api_setup
    experiment_repository.experiment = None

    response = client.get("/experiments/missing/impact")

    assert response.status_code == 404
    assert response.json() == {"detail": "experiment not found"}
    assert result_repository.get_calls == []


def test_missing_execution_result_returns_conflict(api_setup):
    client, _, result_repository = api_setup
    result_repository.result = None

    response = client.get(f"/experiments/{EXPERIMENT_ID}/impact")

    assert response.status_code == 409
    assert response.json() == {"detail": "execution result not found"}
    assert result_repository.actual_comparison_calls == []


def test_endpoint_is_read_only_and_does_not_change_experiment(api_setup):
    client, experiment_repository, result_repository = api_setup
    original_status = experiment_repository.experiment.status

    response = client.get(f"/experiments/{EXPERIMENT_ID}/impact")

    assert response.status_code == 200
    assert experiment_repository.experiment.status is original_status
    assert experiment_repository.write_calls == []
    assert result_repository.write_calls == []
    assert experiment_repository.get_calls == [EXPERIMENT_ID]
    assert result_repository.get_calls == [EXPERIMENT_ID]


def test_domain_validation_error_returns_controlled_response(api_setup):
    client, _, result_repository = api_setup
    result_repository.actual = make_actual("OTHER-EXPERIMENT")

    response = client.get(f"/experiments/{EXPERIMENT_ID}/impact")

    assert response.status_code == 422
    assert "actual_result experiment ID" in response.json()["detail"]
