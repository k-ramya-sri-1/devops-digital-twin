"""Data access for the existing experiments table."""

from collections.abc import Callable, Sequence
import importlib
import json
from typing import Any

from .config import DatabaseConfig
from .connection import DatabaseError, connect


experiment_module = importlib.import_module("digital-twin.experiment")
Experiment = experiment_module.Experiment
ExperimentStatus = experiment_module.ExperimentStatus
ScenarioParameters = experiment_module.ScenarioParameters


class ExperimentRepository:
    """Persist Phase 15 experiments in the existing MySQL table."""

    _SELECT_COLUMNS = (
        "experiment_id, name, scenario_type, status, scenario_parameters"
    )

    def __init__(
        self,
        config: DatabaseConfig | None = None,
        connection_factory: Callable[[DatabaseConfig | None], Any] | None = None,
    ) -> None:
        self._config = config
        self._connection_factory = connection_factory or connect

    def create(self, experiment: Any) -> None:
        parameters = json.dumps(
            {
                "multiplier": experiment.scenario_parameters.multiplier,
                "instance_name": experiment.scenario_parameters.instance_name,
                "additional_instances": experiment.scenario_parameters.additional_instances,
            }
        )
        query = (
            "INSERT INTO experiments "
            "(experiment_id, name, scenario_type, status, scenario_parameters) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        values = (
            experiment.experiment_id,
            experiment.name,
            experiment.scenario_type.value,
            experiment.status.value,
            parameters,
        )
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query, values)
            connection.commit()
        except Exception as error:
            self._rollback(connection)
            self._raise_operation_error(error, "create experiment")
        finally:
            self._close(cursor, connection)

    def get_by_id(self, experiment_id: str) -> Any | None:
        query = (
            f"SELECT {self._SELECT_COLUMNS} FROM experiments "
            "WHERE experiment_id = %s"
        )
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query, (experiment_id,))
            row = cursor.fetchone()
            return None if row is None else self._from_row(row)
        except Exception as error:
            self._raise_operation_error(error, "retrieve experiment")
        finally:
            self._close(cursor, connection)

    def list_all(self) -> list[Any]:
        query = f"SELECT {self._SELECT_COLUMNS} FROM experiments ORDER BY experiment_id"
        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(query)
            return [self._from_row(row) for row in cursor.fetchall()]
        except Exception as error:
            self._raise_operation_error(error, "list experiments")
        finally:
            self._close(cursor, connection)

    def update_status(self, experiment_id: str, status: Any) -> None:
        try:
            status_value = ExperimentStatus(status).value
        except (TypeError, ValueError) as error:
            raise DatabaseError("invalid experiment status") from error

        connection = self._open()
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE experiments SET status = %s WHERE experiment_id = %s",
                (status_value, experiment_id),
            )
            if cursor.rowcount == 0:
                raise DatabaseError(f"experiment not found: {experiment_id}")
            connection.commit()
        except DatabaseError:
            self._rollback(connection)
            raise
        except Exception as error:
            self._rollback(connection)
            self._raise_operation_error(error, "update experiment status")
        finally:
            self._close(cursor, connection)

    def _open(self) -> Any:
        try:
            return self._connection_factory(self._config)
        except DatabaseError:
            raise
        except Exception as error:
            raise DatabaseError("database connection failed") from error

    @staticmethod
    def _from_row(row: Sequence[Any]) -> Any:
        try:
            parameters = json.loads(row[4]) if isinstance(row[4], str) else row[4]
            return Experiment(
                experiment_id=row[0],
                name=row[1],
                scenario_type=row[2],
                status=row[3],
                scenario_parameters=ScenarioParameters(**parameters),
            )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise DatabaseError("invalid experiment data returned by database") from error

    @staticmethod
    def _raise_operation_error(error: Exception, operation: str) -> None:
        if isinstance(error, DatabaseError):
            raise error
        if getattr(error, "errno", None) == 1062:
            raise DatabaseError("duplicate experiment ID") from error
        raise DatabaseError(f"database error while attempting to {operation}") from error

    @staticmethod
    def _rollback(connection: Any) -> None:
        try:
            connection.rollback()
        except Exception:
            pass

    @staticmethod
    def _close(cursor: Any, connection: Any) -> None:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()