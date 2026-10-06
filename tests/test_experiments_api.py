import importlib

import pytest
from fastapi.testclient import TestClient

from app.src.main import app
from app.src.routes.experiments import get_experiment_repository
from database.connection import DatabaseError


experiment_module = importlib.import_module("digital-twin.experiment")
Experiment = experiment_module.Experiment
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType


class FakeRepository:
    def __init__(self, experiments=None, error=None):
        self.experiments = {
            experiment.experiment_id: experiment
            for experiment in (experiments or [])
        }
        self.error = error
        self.created = []
        self.list_calls = 0
        self.get_ids = []

    def create(self, experiment):
        if self.error:
            raise self.error
        self.created.append(experiment)
        self.experiments[experiment.experiment_id] = experiment

    def list_all(self):
        self.list_calls += 1
        if self.error:
            raise self.error
        return list(self.experiments.values())

    def get_by_id(self, experiment_id):
        self.get_ids.append(experiment_id)
        if self.error:
            raise self.error
        return self.experiments.get(experiment_id)


def make_experiment(
    experiment_id="EXP-001",
    scenario_type=ScenarioType.TRAFFIC_SURGE,
    parameters=None,
):
    if parameters is None:
        parameters = {
            ScenarioType.TRAFFIC_SURGE: ScenarioParameters.traffic_surge(2.0),
            ScenarioType.INSTANCE_FAILURE: ScenarioParameters.instance_failure(
                "instance-1"
            ),
            ScenarioType.SCALE_OUT: ScenarioParameters.scale_out(2),
        }[scenario_type]
    return Experiment(
        experiment_id,
        "Traffic Surge Test",
        scenario_type,
        parameters,
    )


@pytest.fixture
def repository():
    fake = FakeRepository()
    app.dependency_overrides[get_experiment_repository] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def request_payload(scenario_type, parameters):
    return {
        "experiment_id": "EXP-NEW",
        "name": "New Experiment",
        "scenario_type": (
            scenario_type.value
            if isinstance(scenario_type, ScenarioType)
            else scenario_type
        ),
        "scenario_parameters": parameters,
    }


@pytest.mark.parametrize(
    ("scenario_type", "parameters"),
    [
        (ScenarioType.TRAFFIC_SURGE, {"multiplier": 2.0}),
        (ScenarioType.INSTANCE_FAILURE, {"instance_name": "instance-1"}),
        (ScenarioType.SCALE_OUT, {"additional_instances": 2}),
    ],
)
def test_create_experiment_supports_all_scenarios(
    client, repository, scenario_type, parameters
):
    response = client.post(
        "/experiments",
        json=request_payload(scenario_type, parameters),
    )

    assert response.status_code == 201
    assert response.json()["scenario_type"] == scenario_type.value
    assert response.json()["status"] == ExperimentStatus.CREATED.value
    assert len(repository.created) == 1
    assert repository.created[0].scenario_type is scenario_type


def test_create_passes_correct_experiment_to_repository(client, repository):
    response = client.post(
        "/experiments",
        json=request_payload(ScenarioType.TRAFFIC_SURGE, {"multiplier": 3.0}),
    )

    assert response.status_code == 201
    created = repository.created[0]
    assert created.experiment_id == "EXP-NEW"
    assert created.name == "New Experiment"
    assert created.parameters.multiplier == 3.0
    assert created.status is ExperimentStatus.CREATED


def test_create_rejects_invalid_scenario_parameters(client, repository):
    response = client.post(
        "/experiments",
        json=request_payload(ScenarioType.TRAFFIC_SURGE, {"multiplier": 0}),
    )

    assert response.status_code == 422
    assert repository.created == []


def test_create_rejects_invalid_scenario_type(client, repository):
    response = client.post(
        "/experiments",
        json=request_payload("UNKNOWN", {"multiplier": 2.0}),
    )

    assert response.status_code == 422
    assert repository.created == []


def test_create_maps_database_error_to_service_unavailable(client):
    repository = FakeRepository(error=DatabaseError("database failed"))
    app.dependency_overrides[get_experiment_repository] = lambda: repository

    response = client.post(
        "/experiments",
        json=request_payload(ScenarioType.TRAFFIC_SURGE, {"multiplier": 2.0}),
    )

    app.dependency_overrides.clear()
    assert response.status_code == 503


def test_list_experiments_calls_repository_and_maps_results(client, repository):
    repository.experiments["EXP-001"] = make_experiment()

    response = client.get("/experiments")

    assert response.status_code == 200
    assert repository.list_calls == 1
    assert response.json()[0]["experiment_id"] == "EXP-001"
    assert response.json()[0]["scenario_parameters"]["multiplier"] == 2.0


def test_list_experiments_returns_empty_list(client, repository):
    response = client.get("/experiments")

    assert response.status_code == 200
    assert response.json() == []
    assert repository.list_calls == 1


def test_list_experiments_maps_database_error(client):
    repository = FakeRepository(error=DatabaseError("database failed"))
    app.dependency_overrides[get_experiment_repository] = lambda: repository

    response = client.get("/experiments")

    app.dependency_overrides.clear()
    assert response.status_code == 503


def test_get_experiment_returns_existing_experiment(client, repository):
    repository.experiments["EXP-001"] = make_experiment()

    response = client.get("/experiments/EXP-001")

    assert response.status_code == 200
    assert response.json()["experiment_id"] == "EXP-001"
    assert repository.get_ids == ["EXP-001"]


def test_get_experiment_returns_not_found(client, repository):
    response = client.get("/experiments/missing")

    assert response.status_code == 404
    assert repository.get_ids == ["missing"]


def test_get_experiment_maps_database_error(client):
    repository = FakeRepository(error=DatabaseError("database failed"))
    app.dependency_overrides[get_experiment_repository] = lambda: repository

    response = client.get("/experiments/EXP-001")

    app.dependency_overrides.clear()
    assert response.status_code == 503