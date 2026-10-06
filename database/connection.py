"""MySQL connection boundary and project-specific database errors."""

from collections.abc import Callable
from typing import Any

from .config import DatabaseConfig, DatabaseConfigurationError


class DatabaseError(RuntimeError):
    """Raised when a database operation cannot be completed."""


def connect(
    config: DatabaseConfig | None = None,
    connector: Callable[..., Any] | None = None,
) -> Any:
    """Open a configured MySQL connection without exposing credentials."""
    try:
        settings = config or DatabaseConfig.from_env()
    except DatabaseConfigurationError as error:
        raise DatabaseError(f"invalid database configuration: {error}") from error

    try:
        if connector is None:
            import mysql.connector

            connector = mysql.connector.connect
        return connector(
            host=settings.host,
            port=settings.port,
            database=settings.database,
            user=settings.user,
            password=settings.password,
        )
    except Exception as error:
        raise DatabaseError("database connection failed") from error