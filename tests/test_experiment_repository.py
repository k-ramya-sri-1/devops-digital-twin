import importlib
import json

import pytest

from database.connection import DatabaseError
from database.experiment_repository import ExperimentRepository


experiment_module = importlib.import_module("digital-twin.experiment")
Experiment = experiment_module.Experiment
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType


class FakeDatabaseError(Exception):
    def __init__(self, message="SQL failure", errno=None):
        super().__init__(message)
        self.errno = errno


class FakeCursor:
    def __init__(self, rows=None, rowcount=1, error=None):
        self.rows = list(rows or [])
        self.rowcount = rowcount
        self.error = error
        self.calls = []

    def execute(self, query, parameters=None):
        self.calls.append((query, parameters))
        if self.error:
            raise self.error

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def make_experiment(experiment_id="EXP-002"):
    return Experiment(
        experiment_id,
        "Traffic Surge Test",
        ScenarioType.TRAFFIC_SURGE,
        ScenarioParameters.traffic_surge(2.0),
    )


def make_repository(cursor):
    connection = FakeConnection(cursor)
    return ExperimentRepository(connection_factory=lambda config: connection), connection


def row(experiment_id="EXP-002", status="CREATED", parameters=None):
    return (
        experiment_id,
        "Traffic Surge Test",
        "TRAFFIC_SURGE",
        status,
        json.dumps(parameters or {"multiplier": 2.0}),
    )


def test_create_serializes_parameters_and_does_not_mutate_original():
    item = make_experiment()
    cursor = FakeCursor()
    repository, connection = make_repository(cursor)

    repository.create(item)

    assert item.status is ExperimentStatus.CREATED
    assert cursor.calls[0][1] == (
        "EXP-002",
        "Traffic Surge Test",
        "TRAFFIC_SURGE",
        "CREATED",
        json.dumps({"multiplier": 2.0, "instance_name": None, "additional_instances": None}),
    )
    assert connection.commits == 1


def test_get_by_id_deserializes_parameters():
    cursor = FakeCursor([row()])
    repository, _ = make_repository(cursor)

    result = repository.get_by_id("EXP-002")

    assert result.parameters.multiplier == 2.0
    assert cursor.calls[0][1] == ("EXP-002",)


def test_get_by_id_missing_returns_none():
    repository, _ = make_repository(FakeCursor())
    assert repository.get_by_id("missing") is None


def test_list_all_returns_experiments():
    repository, _ = make_repository(FakeCursor([row(), row("EXP-003")]))
    assert [item.experiment_id for item in repository.list_all()] == ["EXP-002", "EXP-003"]


def test_update_status_is_parameterized_and_commits():
    cursor = FakeCursor(rowcount=1)
    repository, connection = make_repository(cursor)

    repository.update_status("EXP-002", ExperimentStatus.SIMULATED)

    assert cursor.calls[0][1] == ("SIMULATED", "EXP-002")
    assert connection.commits == 1


def test_duplicate_id_is_a_database_error():
    repository, _ = make_repository(FakeCursor(error=FakeDatabaseError(errno=1062)))
    with pytest.raises(DatabaseError, match="duplicate experiment ID"):
        repository.create(make_experiment())


def test_update_missing_experiment_is_a_database_error():
    repository, _ = make_repository(FakeCursor(rowcount=0))
    with pytest.raises(DatabaseError, match="experiment not found"):
        repository.update_status("missing", "SIMULATED")


def test_sql_errors_are_wrapped_without_credentials():
    repository, _ = make_repository(FakeCursor(error=FakeDatabaseError("password=secret")))
    with pytest.raises(DatabaseError, match="database error") as error:
        repository.list_all()
    assert "secret" not in str(error.value)