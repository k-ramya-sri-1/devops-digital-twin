import pytest
from fastapi.testclient import TestClient

from app.src.main import app
from app.src.routes.experiments import (
    get_experiment_repository,
    get_experiment_result_repository,
)
from database.connection import DatabaseError
from tests.test_deployment_impact import (
    make_actual,
    make_comparison,
    make_execution_result,
)
from tests.test_deployment_impact_api import (
    FakeExperimentRepository,
    FakeExperimentResultRepository,
    make_experiment,
)


EXPERIMENT_ID = "EXP-027A"


class ErrorExperimentRepository(FakeExperimentRepository):
    def get_by_id(self, experiment_id):
        raise DatabaseError("database failed")


class ErrorExperimentResultRepository(FakeExperimentResultRepository):
    def get_by_experiment_id(self, experiment_id):
        raise DatabaseError("database failed")


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


def test_successful_recommendation_retrieval(api_setup):
    client, _, result_repository = api_setup

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == EXPERIMENT_ID
    assert body["overall_priority"] == "LOW"
    assert body["recommendations"][0]["action"] == "MAINTAIN"
    assert body["recommendations"][0]["priority"] == "LOW"
    assert result_repository.actual_comparison_calls == [EXPERIMENT_ID]


def test_successful_retrieval_with_actual_and_comparison(api_setup):
    client, _, result_repository = api_setup
    result_repository.actual = make_actual()
    result_repository.comparison = make_comparison(status="MISMATCH")

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert [item["action"] for item in body["recommendations"]] == [
        "MAINTAIN",
        "REVIEW_PREDICTION",
    ]
    assert body["overall_priority"] == "MEDIUM"
    assert body["limitations"] == []


def test_response_structure_and_nested_recommendation_fields(api_setup):
    client, _, _ = api_setup

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "experiment_id",
        "recommendations",
        "overall_priority",
        "limitations",
    }
    assert set(body["recommendations"][0]) == {
        "action",
        "priority",
        "reason",
        "evidence",
        "experiment_id",
    }
    assert body["recommendations"][0]["experiment_id"] == EXPERIMENT_ID
    assert isinstance(body["recommendations"][0]["evidence"], list)


def test_limitations_are_preserved(api_setup):
    client, _, _ = api_setup

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 200
    assert "actual validation is pending or unavailable" in response.json()[
        "limitations"
    ]
    assert "prediction comparison is not available" in response.json()[
        "limitations"
    ]


def test_missing_experiment_returns_not_found(api_setup):
    client, experiment_repository, result_repository = api_setup
    experiment_repository.experiment = None

    response = client.get("/experiments/missing/recommendations")

    assert response.status_code == 404
    assert response.json() == {"detail": "experiment not found"}
    assert result_repository.get_calls == []


def test_missing_execution_result_returns_conflict(api_setup):
    client, _, result_repository = api_setup
    result_repository.result = None

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 409
    assert response.json() == {"detail": "execution result not found"}
    assert result_repository.actual_comparison_calls == []


def test_endpoint_is_read_only_and_does_not_change_experiment(api_setup):
    client, experiment_repository, result_repository = api_setup
    original_status = experiment_repository.experiment.status

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 200
    assert experiment_repository.experiment.status is original_status
    assert experiment_repository.write_calls == []
    assert result_repository.write_calls == []


def test_domain_error_is_converted_to_controlled_response(api_setup):
    client, _, result_repository = api_setup
    result_repository.actual = make_actual("OTHER-EXPERIMENT")

    response = client.get(f"/experiments/{EXPERIMENT_ID}/recommendations")

    assert response.status_code == 422
    assert "actual_result experiment ID" in response.json()["detail"]


@pytest.mark.parametrize(
    ("repository_factory", "expected_detail"),
    [
        (ErrorExperimentRepository, "experiment database unavailable"),
        (ErrorExperimentResultRepository, "experiment result database unavailable"),
    ],
)
def test_repository_errors_are_converted_to_controlled_responses(
    repository_factory, expected_detail
):
    experiment_repository = (
        repository_factory(make_experiment())
        if repository_factory is ErrorExperimentRepository
        else FakeExperimentRepository(make_experiment())
    )
    result_repository = (
        repository_factory(make_execution_result())
        if repository_factory is ErrorExperimentResultRepository
        else ErrorExperimentResultRepository(make_execution_result())
    )
    app.dependency_overrides[get_experiment_repository] = (
        lambda: experiment_repository
    )
    app.dependency_overrides[get_experiment_result_repository] = (
        lambda: result_repository
    )
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/experiments/{EXPERIMENT_ID}/recommendations"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": expected_detail}
