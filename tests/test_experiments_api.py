import importlib
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.src.main import app
from app.src.routes.experiments import (
    get_current_state_service,
    get_experiment_executor,
    get_experiment_repository,
    get_experiment_result_repository,
)
from database.connection import DatabaseError


experiment_module = importlib.import_module("digital-twin.experiment")
Experiment = experiment_module.Experiment
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType
models_module = importlib.import_module("digital-twin.models")
executor_module = importlib.import_module("digital-twin.executor")
collector_module = importlib.import_module("digital-twin.collector")
Infrastructure = models_module.Infrastructure
Instance = models_module.Instance
InstanceStatus = models_module.InstanceStatus
Service = models_module.Service
ExecutionResult = executor_module.ExecutionResult
ExperimentExecutionError = executor_module.ExperimentExecutionError
PrometheusCollectorError = collector_module.PrometheusCollectorError

SERVICE_NAME = "devops-digital-twin"


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
        self.update_status_calls = []

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

    def update_status(self, experiment_id, status):
        self.update_status_calls.append((experiment_id, status))


class FakeCurrentStateService:
    def __init__(self, state=None, error=None):
        self.state = state
        self.error = error
        self.calls = 0

    def get_current_state(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.state


class FakeExecutor:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def execute(self, experiment, baseline, service_name):
        self.calls.append((experiment, baseline, service_name))
        if self.error is not None:
            raise self.error
        return self.result


class FakeResultRepository:
    def __init__(self, results=None, error=None):
        self.results = {
            result.experiment_id: result for result in (results or [])
        }
        self.error = error
        self.create_calls = []
        self.get_ids = []

    def create(self, result):
        self.create_calls.append(result)

    def get_by_experiment_id(self, experiment_id):
        self.get_ids.append(experiment_id)
        if self.error is not None:
            raise self.error
        return self.results.get(experiment_id)


def make_experiment(
    experiment_id="EXP-001",
    scenario_type=ScenarioType.TRAFFIC_SURGE,
    parameters=None,
    status=ExperimentStatus.CREATED,
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
        status=status,
    )


def make_infrastructure():
    service = Service(name=SERVICE_NAME)
    service.add_instance(
        Instance(
            name="instance-1",
            cpu_capacity=2.0,
            memory_capacity=1024.0,
            cpu_utilization=50.0,
            memory_utilization=25.0,
            request_rate=100.0,
            status=InstanceStatus.HEALTHY,
        )
    )
    service.add_instance(
        Instance(
            name="instance-2",
            cpu_capacity=2.0,
            memory_capacity=1024.0,
            cpu_utilization=50.0,
            memory_utilization=25.0,
            request_rate=50.0,
            status=InstanceStatus.HEALTHY,
        )
    )
    infrastructure = Infrastructure()
    infrastructure.add_service(service)
    return infrastructure


def make_execution_result(scenario_type, experiment_id):
    parameters = {
        ScenarioType.TRAFFIC_SURGE: ScenarioParameters.traffic_surge(2.0),
        ScenarioType.INSTANCE_FAILURE: ScenarioParameters.instance_failure(
            "instance-1"
        ),
        ScenarioType.SCALE_OUT: ScenarioParameters.scale_out(1),
    }[scenario_type]
    experiment = make_experiment(experiment_id, scenario_type, parameters)
    return executor_module.ExperimentExecutor().execute(
        experiment, make_infrastructure(), SERVICE_NAME
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


@pytest.fixture
def execution_setup():
    repository = FakeRepository()
    current_state_service = FakeCurrentStateService(make_infrastructure())
    executor = FakeExecutor()
    result_repository = FakeResultRepository()
    app.dependency_overrides[get_experiment_repository] = lambda: repository
    app.dependency_overrides[get_current_state_service] = (
        lambda: current_state_service
    )
    app.dependency_overrides[get_experiment_executor] = lambda: executor
    app.dependency_overrides[get_experiment_result_repository] = (
        lambda: result_repository
    )
    yield repository, current_state_service, executor, result_repository
    app.dependency_overrides.clear()


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


@pytest.mark.parametrize(
    "scenario_type",
    [ScenarioType.TRAFFIC_SURGE, ScenarioType.INSTANCE_FAILURE, ScenarioType.SCALE_OUT],
)
def test_execute_experiment_returns_typed_result(
    client, execution_setup, scenario_type
):
    repository, current_state_service, executor, result_repository = execution_setup
    experiment_id = f"EXP-{scenario_type.value}"
    experiment = make_experiment(experiment_id, scenario_type)
    result = make_execution_result(scenario_type, experiment_id)
    repository.experiments[experiment_id] = experiment
    executor.result = result

    response = client.post(
        f"/experiments/{experiment_id}/execute",
        json={"service_name": SERVICE_NAME},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == experiment_id
    assert body["scenario_type"] == scenario_type.value
    assert body["service_name"] == SERVICE_NAME
    assert "simulation" in body
    assert "impact" in body
    assert "prediction" in body
    assert "bottleneck" in body
    assert current_state_service.calls == 1
    assert executor.calls == [(experiment, current_state_service.state, SERVICE_NAME)]
    assert result_repository.create_calls == []
    assert repository.update_status_calls == []


def test_execute_missing_experiment_returns_not_found(client, execution_setup):
    repository, current_state_service, executor, _ = execution_setup

    response = client.post(
        "/experiments/missing/execute",
        json={"service_name": SERVICE_NAME},
    )

    assert response.status_code == 404
    assert repository.get_ids == ["missing"]
    assert current_state_service.calls == 0
    assert executor.calls == []


@pytest.mark.parametrize("status", [ExperimentStatus.EXECUTED, ExperimentStatus.VALIDATED])
def test_execute_non_created_experiment_returns_conflict(
    client, execution_setup, status
):
    repository, current_state_service, executor, _ = execution_setup
    repository.experiments["EXP-STATUS"] = make_experiment(status=status)

    response = client.post(
        "/experiments/EXP-STATUS/execute",
        json={"service_name": SERVICE_NAME},
    )

    assert response.status_code == 409
    assert current_state_service.calls == 0
    assert executor.calls == []


def test_execute_passes_path_id_and_service_name_to_executor(
    client, execution_setup
):
    repository, current_state_service, executor, _ = execution_setup
    experiment = make_experiment("EXP-CALL")
    repository.experiments["EXP-CALL"] = experiment
    executor.result = make_execution_result(ScenarioType.TRAFFIC_SURGE, "EXP-CALL")

    response = client.post(
        "/experiments/EXP-CALL/execute",
        json={"service_name": "custom-service"},
    )

    assert response.status_code == 200
    assert executor.calls == [(experiment, current_state_service.state, "custom-service")]


def test_execute_repository_error_returns_service_unavailable(client, execution_setup):
    repository, current_state_service, executor, _ = execution_setup
    repository.error = DatabaseError("database unavailable")

    response = client.post(
        "/experiments/EXP-DB/execute",
        json={"service_name": SERVICE_NAME},
    )

    assert response.status_code == 503
    assert current_state_service.calls == 0
    assert executor.calls == []


def test_execute_current_state_error_returns_service_unavailable(
    client, execution_setup
):
    repository, current_state_service, executor, _ = execution_setup
    repository.experiments["EXP-PROM"] = make_experiment("EXP-PROM")
    current_state_service.error = PrometheusCollectorError("prometheus unavailable")

    response = client.post(
        "/experiments/EXP-PROM/execute",
        json={"service_name": SERVICE_NAME},
    )

    assert response.status_code == 503
    assert executor.calls == []


def test_execute_failure_returns_controlled_error(client, execution_setup):
    repository, current_state_service, executor, _ = execution_setup
    repository.experiments["EXP-FAIL"] = make_experiment("EXP-FAIL")
    executor.error = ExperimentExecutionError("internal details")

    response = client.post(
        "/experiments/EXP-FAIL/execute",
        json={"service_name": SERVICE_NAME},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "experiment execution failed"}
    assert current_state_service.calls == 1


def test_execute_rejects_blank_service_name(client, execution_setup):
    repository, current_state_service, executor, _ = execution_setup
    repository.experiments["EXP-BLANK"] = make_experiment("EXP-BLANK")

    response = client.post(
        "/experiments/EXP-BLANK/execute",
        json={"service_name": "   "},
    )

    assert response.status_code == 422
    assert current_state_service.calls == 0
    assert executor.calls == []


@pytest.fixture
def result_repository():
    fake = FakeResultRepository()
    app.dependency_overrides[get_experiment_result_repository] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def test_get_execution_result_returns_existing_result(client, result_repository):
    result = make_execution_result(ScenarioType.TRAFFIC_SURGE, "EXP-RESULT")
    result_repository.results["EXP-RESULT"] = result

    response = client.get("/experiments/EXP-RESULT/result")

    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == "EXP-RESULT"
    assert body["scenario_type"] == ScenarioType.TRAFFIC_SURGE.value
    assert body["service_name"] == SERVICE_NAME
    assert body["simulation"]["simulated_request_rate"] == 300.0
    assert body["prediction"]["cpu_status"] == "SUFFICIENT"
    assert body["bottleneck"]["overall_status"] == "NO_BOTTLENECK"
    assert result_repository.get_ids == ["EXP-RESULT"]
    assert result_repository.create_calls == []


def test_get_execution_result_returns_not_found(client, result_repository):
    response = client.get("/experiments/missing/result")

    assert response.status_code == 404
    assert response.json() == {"detail": "execution result not found"}
    assert result_repository.get_ids == ["missing"]


def test_get_execution_result_maps_database_error(client):
    repository = FakeResultRepository(error=DatabaseError("database failed"))
    app.dependency_overrides[get_experiment_result_repository] = lambda: repository

    response = client.get("/experiments/EXP-DB/result")

    app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "experiment result database unavailable"}