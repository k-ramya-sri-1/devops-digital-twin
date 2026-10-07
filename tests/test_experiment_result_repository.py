import importlib
import json

import pytest


models = importlib.import_module("digital-twin.models")
actual_result_module = importlib.import_module("digital-twin.actual_result")
prediction_comparison_module = importlib.import_module(
    "digital-twin.prediction_comparison"
)
experiment_module = importlib.import_module("digital-twin.experiment")
executor_module = importlib.import_module("digital-twin.executor")
repository_module = importlib.import_module("database.experiment_result_repository")

Infrastructure = models.Infrastructure
Instance = models.Instance
InstanceStatus = models.InstanceStatus
Service = models.Service
ActualKubernetesResult = actual_result_module.ActualKubernetesResult
PredictionMetricComparison = prediction_comparison_module.PredictionMetricComparison
PredictionVsActualResult = prediction_comparison_module.PredictionVsActualResult
Experiment = experiment_module.Experiment
ScenarioParameters = experiment_module.ScenarioParameters
ScenarioType = experiment_module.ScenarioType
ExecutionResult = executor_module.ExecutionResult
ExperimentExecutor = executor_module.ExperimentExecutor
DatabaseError = repository_module.DatabaseError
ExperimentResultRepository = repository_module.ExperimentResultRepository

SERVICE_NAME = "devops-digital-twin"


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
        self.closed = False

    def execute(self, query, parameters=None):
        self.calls.append((query, parameters))
        if self.error:
            raise self.error

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        self.closed = True


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


def make_infrastructure() -> Infrastructure:
    service = Service(name=SERVICE_NAME, dependencies={"database"})
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


def make_result(scenario_type: ScenarioType, experiment_id: str) -> ExecutionResult:
    parameters = {
        ScenarioType.TRAFFIC_SURGE: ScenarioParameters.traffic_surge(2.0),
        ScenarioType.INSTANCE_FAILURE: ScenarioParameters.instance_failure(
            "instance-1"
        ),
        ScenarioType.SCALE_OUT: ScenarioParameters.scale_out(1),
    }[scenario_type]
    experiment = Experiment(experiment_id, "repository test", scenario_type, parameters)
    return ExperimentExecutor().execute(
        experiment, make_infrastructure(), SERVICE_NAME
    )


def repository_for(cursor):
    connection = FakeConnection(cursor)
    repository = ExperimentResultRepository(
        connection_factory=lambda config: connection
    )
    return repository, connection


def stored_row(result: ExecutionResult):
    cursor = FakeCursor()
    repository, _ = repository_for(cursor)
    repository.create(result)
    return cursor.calls[0][1]


def make_actual_result(experiment_id: str = "EXP-COMPARISON"):
    return ActualKubernetesResult(
        experiment_id=experiment_id,
        deployment_name=SERVICE_NAME,
        namespace="default",
        desired_replicas=4,
        ready_replicas=4,
        available_replicas=4,
        updated_replicas=4,
    )


def make_prediction_comparison(experiment_id: str = "EXP-COMPARISON"):
    return PredictionVsActualResult(
        experiment_id=experiment_id,
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


@pytest.mark.parametrize(
    "scenario_type",
    [ScenarioType.TRAFFIC_SURGE, ScenarioType.INSTANCE_FAILURE, ScenarioType.SCALE_OUT],
)
def test_round_trip_preserves_typed_execution_result(scenario_type) -> None:
    original = make_result(scenario_type, f"EXP-{scenario_type.value}")
    repository, _ = repository_for(FakeCursor([stored_row(original)]))

    restored = repository.get_by_experiment_id(original.experiment_id)

    assert restored == original
    assert type(restored.simulation) is type(original.simulation)
    assert type(restored.impact) is type(original.impact)
    assert type(restored.prediction) is type(original.prediction)
    assert type(restored.bottleneck) is type(original.bottleneck)


def test_create_uses_parameterized_sql_commits_and_closes() -> None:
    result = make_result(ScenarioType.TRAFFIC_SURGE, "EXP-CREATE")
    cursor = FakeCursor()
    repository, connection = repository_for(cursor)

    repository.create(result)

    query, parameters = cursor.calls[0]
    assert "VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL)" in query
    assert result.experiment_id not in query
    assert parameters[0] == "EXP-CREATE"
    assert parameters[1] == "TRAFFIC_SURGE"
    assert json.loads(parameters[3])["infrastructure"]["services"][SERVICE_NAME]
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert cursor.closed
    assert connection.closed


def test_update_actual_comparison_persists_parameterized_json() -> None:
    cursor = FakeCursor()
    repository, connection = repository_for(cursor)
    actual_result = make_actual_result()
    comparison = make_prediction_comparison()

    repository.update_actual_comparison("EXP-COMPARISON", actual_result, comparison)

    query, parameters = cursor.calls[0]
    assert "UPDATE experiment_results SET actual_result = %s" in query
    assert "prediction_comparison = %s" in query
    assert "EXP-COMPARISON" not in query
    assert json.loads(parameters[0]) == actual_result.to_dict()
    assert json.loads(parameters[1]) == comparison.to_dict()
    assert parameters[2] == "EXP-COMPARISON"
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert cursor.closed
    assert connection.closed


def test_get_actual_comparison_reconstructs_typed_objects() -> None:
    actual_result = make_actual_result()
    comparison = make_prediction_comparison()
    row = (json.dumps(actual_result.to_dict()), json.dumps(comparison.to_dict()))
    repository, _ = repository_for(FakeCursor([row]))

    restored_actual, restored_comparison = repository.get_actual_comparison(
        "EXP-COMPARISON"
    )

    assert restored_actual == actual_result
    assert restored_comparison == comparison
    assert type(restored_actual) is ActualKubernetesResult
    assert type(restored_comparison) is PredictionVsActualResult
    assert type(restored_comparison.comparisons[0]) is PredictionMetricComparison


def test_get_actual_comparison_handles_legacy_null_columns() -> None:
    repository, _ = repository_for(FakeCursor([(None, None)]))

    assert repository.get_actual_comparison("EXP-LEGACY") == (None, None)


def test_get_actual_comparison_handles_actual_only_partial_state() -> None:
    actual_result = make_actual_result()
    repository, _ = repository_for(
        FakeCursor([(json.dumps(actual_result.to_dict()), None)])
    )

    restored_actual, restored_comparison = repository.get_actual_comparison(
        "EXP-COMPARISON"
    )

    assert restored_actual == actual_result
    assert restored_comparison is None


def test_get_actual_comparison_handles_comparison_only_partial_state() -> None:
    comparison = make_prediction_comparison()
    repository, _ = repository_for(
        FakeCursor([(None, json.dumps(comparison.to_dict()))])
    )

    restored_actual, restored_comparison = repository.get_actual_comparison(
        "EXP-COMPARISON"
    )

    assert restored_actual is None
    assert restored_comparison == comparison


@pytest.mark.parametrize(
    "row",
    [("{invalid", None), (None, '{"comparisons": "invalid"}')],
)
def test_malformed_actual_comparison_json_raises_database_error(row) -> None:
    repository, _ = repository_for(FakeCursor([row]))

    with pytest.raises(DatabaseError, match="invalid experiment result data"):
        repository.get_actual_comparison("EXP-MALFORMED-COMPARISON")


def test_update_actual_comparison_failure_rolls_back_and_closes() -> None:
    cursor = FakeCursor(error=FakeDatabaseError("SQL failed"))
    repository, connection = repository_for(cursor)

    with pytest.raises(DatabaseError, match="database error"):
        repository.update_actual_comparison(
            "EXP-COMPARISON", make_actual_result(), make_prediction_comparison()
        )

    assert connection.rollbacks == 1
    assert cursor.closed
    assert connection.closed


def test_list_all_returns_typed_results() -> None:
    results = [
        make_result(ScenarioType.TRAFFIC_SURGE, "EXP-001"),
        make_result(ScenarioType.INSTANCE_FAILURE, "EXP-002"),
        make_result(ScenarioType.SCALE_OUT, "EXP-003"),
    ]
    repository, _ = repository_for(FakeCursor([stored_row(result) for result in results]))

    restored = repository.list_all()

    assert [result.experiment_id for result in restored] == [
        "EXP-001",
        "EXP-002",
        "EXP-003",
    ]


def test_missing_result_returns_none() -> None:
    repository, _ = repository_for(FakeCursor())
    assert repository.get_by_experiment_id("missing") is None


def test_duplicate_result_id_is_wrapped() -> None:
    result = make_result(ScenarioType.TRAFFIC_SURGE, "EXP-DUPLICATE")
    repository, connection = repository_for(
        FakeCursor(error=FakeDatabaseError(errno=1062))
    )

    with pytest.raises(DatabaseError, match="duplicate experiment result ID"):
        repository.create(result)

    assert connection.rollbacks == 1


def test_create_failure_rolls_back_and_closes() -> None:
    result = make_result(ScenarioType.TRAFFIC_SURGE, "EXP-FAILURE")
    cursor = FakeCursor(error=FakeDatabaseError("SQL failed"))
    repository, connection = repository_for(cursor)

    with pytest.raises(DatabaseError, match="database error"):
        repository.create(result)

    assert connection.rollbacks == 1
    assert cursor.closed
    assert connection.closed


def test_malformed_json_raises_database_error() -> None:
    result = make_result(ScenarioType.TRAFFIC_SURGE, "EXP-MALFORMED")
    row = list(stored_row(result))
    row[3] = "{invalid"
    repository, _ = repository_for(FakeCursor([tuple(row)]))

    with pytest.raises(DatabaseError, match="invalid experiment result data"):
        repository.get_by_experiment_id("EXP-MALFORMED")


def test_invalid_stored_result_raises_database_error() -> None:
    result = make_result(ScenarioType.TRAFFIC_SURGE, "EXP-INVALID")
    row = list(stored_row(result))
    simulation = json.loads(row[3])
    del simulation["service_name"]
    row[3] = json.dumps(simulation)
    repository, _ = repository_for(FakeCursor([tuple(row)]))

    with pytest.raises(DatabaseError, match="invalid experiment result data"):
        repository.get_by_experiment_id("EXP-INVALID")
