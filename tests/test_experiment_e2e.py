import importlib

import pytest
from fastapi.testclient import TestClient

from app.src.main import app
from app.src.routes.experiments import (
    get_actual_result_collector,
    get_current_state_service,
    get_experiment_executor,
    get_experiment_repository,
    get_experiment_result_repository,
)


actual_result_module = importlib.import_module("digital-twin.actual_result")
executor_module = importlib.import_module("digital-twin.executor")
kubernetes_module = importlib.import_module("digital-twin.kubernetes_adapter")
models_module = importlib.import_module("digital-twin.models")
experiment_module = importlib.import_module("digital-twin.experiment")

ActualResultCollector = actual_result_module.ActualResultCollector
ExperimentExecutor = executor_module.ExperimentExecutor
ExecutionResult = executor_module.ExecutionResult
KubernetesDeploymentState = kubernetes_module.KubernetesDeploymentState
Infrastructure = models_module.Infrastructure
Instance = models_module.Instance
InstanceStatus = models_module.InstanceStatus
Service = models_module.Service
Experiment = experiment_module.Experiment
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioType = experiment_module.ScenarioType

EXPERIMENT_ID = "EXP-029A"
SERVICE_NAME = "devops-digital-twin"


class InMemoryExperimentRepository:
    def __init__(self):
        self.experiments = {}
        self.write_calls = []
        self.get_calls = []

    def create(self, experiment):
        self.write_calls.append(("create", experiment.experiment_id))
        self.experiments[experiment.experiment_id] = experiment

    def get_by_id(self, experiment_id):
        self.get_calls.append(experiment_id)
        return self.experiments.get(experiment_id)

    def list_all(self):
        return list(self.experiments.values())

    def update_status(self, experiment_id, status):
        self.write_calls.append(("update_status", experiment_id, status))
        self.experiments[experiment_id].status = status


class InMemoryExperimentResultRepository:
    def __init__(self):
        self.results = {}
        self.actual_comparisons = {}
        self.write_calls = []
        self.get_calls = []
        self.actual_comparison_calls = []

    def create(self, result):
        self.write_calls.append(("create", result.experiment_id))
        self.results[result.experiment_id] = result

    def get_by_experiment_id(self, experiment_id):
        self.get_calls.append(experiment_id)
        return self.results.get(experiment_id)

    def update_actual_comparison(
        self, experiment_id, actual_result, prediction_comparison
    ):
        self.write_calls.append(("update_actual_comparison", experiment_id))
        self.actual_comparisons[experiment_id] = (
            actual_result,
            prediction_comparison,
        )

    def get_actual_comparison(self, experiment_id):
        self.actual_comparison_calls.append(experiment_id)
        return self.actual_comparisons.get(experiment_id, (None, None))


class FakeCurrentStateService:
    def __init__(self, state):
        self.state = state
        self.calls = 0

    def get_current_state(self):
        self.calls += 1
        return self.state


class FakeKubernetesAdapter:
    def __init__(self, state):
        self.state = state
        self.calls = 0

    def get_deployment_state(self):
        self.calls += 1
        return self.state


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


@pytest.fixture
def e2e_setup():
    experiment_repository = InMemoryExperimentRepository()
    result_repository = InMemoryExperimentResultRepository()
    current_state_service = FakeCurrentStateService(make_infrastructure())
    deployment_state = KubernetesDeploymentState(
        name=SERVICE_NAME,
        namespace="default",
        desired_replicas=3,
        ready_replicas=3,
        available_replicas=3,
        updated_replicas=3,
    )
    kubernetes_adapter = FakeKubernetesAdapter(deployment_state)
    executor = ExperimentExecutor(
        repository=experiment_repository,
        result_repository=result_repository,
    )

    app.dependency_overrides[get_experiment_repository] = (
        lambda: experiment_repository
    )
    app.dependency_overrides[get_experiment_result_repository] = (
        lambda: result_repository
    )
    app.dependency_overrides[get_current_state_service] = (
        lambda: current_state_service
    )
    app.dependency_overrides[get_experiment_executor] = lambda: executor
    app.dependency_overrides[get_actual_result_collector] = lambda: ActualResultCollector(
        kubernetes_adapter
    )

    with TestClient(app) as client:
        yield {
            "client": client,
            "experiments": experiment_repository,
            "results": result_repository,
            "current_state": current_state_service,
            "adapter": kubernetes_adapter,
        }
    app.dependency_overrides.clear()


def create_scale_out_experiment(client):
    response = client.post(
        "/experiments",
        json={
            "experiment_id": EXPERIMENT_ID,
            "name": "Phase 29A scale-out",
            "scenario_type": "SCALE_OUT",
            "scenario_parameters": {"additional_instances": 1},
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "CREATED"
    return response


def execute_experiment(client):
    response = client.post(
        f"/experiments/{EXPERIMENT_ID}/execute",
        json={"service_name": SERVICE_NAME},
    )
    assert response.status_code == 200
    return response


def test_complete_execute_impact_recommendation_flow(e2e_setup):
    client = e2e_setup["client"]
    experiments = e2e_setup["experiments"]
    results = e2e_setup["results"]

    create_scale_out_experiment(client)
    execute_experiment(client)

    assert experiments.experiments[EXPERIMENT_ID].status is ExperimentStatus.EXECUTED
    assert isinstance(results.results[EXPERIMENT_ID], ExecutionResult)

    impact_response = client.get(f"/experiments/{EXPERIMENT_ID}/impact")
    assert impact_response.status_code == 200
    impact = impact_response.json()
    assert impact["experiment_id"] == EXPERIMENT_ID
    assert impact["scenario_type"] == "SCALE_OUT"
    assert impact["service_name"] == SERVICE_NAME
    assert impact["simulated_impact"]["simulated_instance_count"] == 3
    assert impact["predicted_demand"]["cpu_status"] == "SUFFICIENT"
    assert impact["bottleneck"]["overall_status"] == "WARNING"
    assert "actual validation is pending or unavailable" in impact["limitations"]

    recommendations_response = client.get(
        f"/experiments/{EXPERIMENT_ID}/recommendations"
    )
    assert recommendations_response.status_code == 200
    recommendations = recommendations_response.json()
    assert recommendations["experiment_id"] == EXPERIMENT_ID
    assert recommendations["overall_priority"] == "MEDIUM"
    assert recommendations["recommendations"]
    recommendation = recommendations["recommendations"][0]
    assert recommendation["action"] == "MONITOR"
    assert recommendation["priority"] == "MEDIUM"
    assert recommendation["reason"]
    assert recommendation["evidence"]
    assert recommendation["experiment_id"] == EXPERIMENT_ID


def test_execute_validate_impact_recommendation_flow(e2e_setup):
    client = e2e_setup["client"]
    experiments = e2e_setup["experiments"]
    results = e2e_setup["results"]
    adapter = e2e_setup["adapter"]

    create_scale_out_experiment(client)
    execute_experiment(client)
    assert experiments.experiments[EXPERIMENT_ID].status is ExperimentStatus.EXECUTED

    validation_response = client.post(f"/experiments/{EXPERIMENT_ID}/validate")

    assert validation_response.status_code == 200
    validation = validation_response.json()
    assert validation["prediction_comparison"]["overall_status"] == "MATCH"
    assert validation["prediction_comparison"]["comparisons"] == [
        {
            "metric_name": "replica_count",
            "expected": 3,
            "actual": 3,
            "absolute_error": 0.0,
            "percentage_error": 0.0,
            "status": "MATCH",
        }
    ]
    assert experiments.experiments[EXPERIMENT_ID].status is ExperimentStatus.VALIDATED
    assert results.actual_comparisons[EXPERIMENT_ID][0].desired_replicas == 3
    assert adapter.calls == 1

    impact = client.get(f"/experiments/{EXPERIMENT_ID}/impact")
    assert impact.status_code == 200
    impact_body = impact.json()
    assert impact_body["actual_result"]["desired_replicas"] == 3
    assert impact_body["prediction_accuracy"]["overall_status"] == "MATCH"
    assert "actual validation is pending or unavailable" not in impact_body[
        "limitations"
    ]

    recommendations = client.get(
        f"/experiments/{EXPERIMENT_ID}/recommendations"
    )
    assert recommendations.status_code == 200
    assert recommendations.json()["experiment_id"] == EXPERIMENT_ID
    assert recommendations.json()["recommendations"]


def test_lifecycle_and_in_memory_persistence_are_verified(e2e_setup):
    client = e2e_setup["client"]
    experiments = e2e_setup["experiments"]
    results = e2e_setup["results"]

    create_scale_out_experiment(client)
    assert experiments.experiments[EXPERIMENT_ID].status is ExperimentStatus.CREATED

    execute_experiment(client)
    assert experiments.experiments[EXPERIMENT_ID].status is ExperimentStatus.EXECUTED
    assert ("create", EXPERIMENT_ID) in results.write_calls

    client.post(f"/experiments/{EXPERIMENT_ID}/validate")
    assert experiments.experiments[EXPERIMENT_ID].status is ExperimentStatus.VALIDATED
    assert ("update_actual_comparison", EXPERIMENT_ID) in results.write_calls
    assert ("update_status", EXPERIMENT_ID, ExperimentStatus.VALIDATED) in (
        experiments.write_calls
    )


def test_external_systems_are_not_contacted(e2e_setup):
    client = e2e_setup["client"]
    current_state = e2e_setup["current_state"]
    adapter = e2e_setup["adapter"]

    create_scale_out_experiment(client)
    execute_experiment(client)
    assert current_state.calls == 1
    assert adapter.calls == 0

    client.post(f"/experiments/{EXPERIMENT_ID}/validate")
    assert adapter.calls == 1


def test_impact_before_execution_returns_conflict(e2e_setup):
    client = e2e_setup["client"]

    create_scale_out_experiment(client)

    response = client.get(f"/experiments/{EXPERIMENT_ID}/impact")

    assert response.status_code == 409
    assert response.json() == {"detail": "execution result not found"}



def test_recommendations_before_execution_returns_conflict(e2e_setup):
    client = e2e_setup["client"]

    create_scale_out_experiment(client)

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 409
    assert response.json() == {"detail": "execution result not found"}
