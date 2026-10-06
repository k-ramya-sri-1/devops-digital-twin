"""Environment-backed MySQL configuration."""

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


class DatabaseConfigurationError(ValueError):
    """Raised when database environment variables are invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str = "localhost"
    port: int = 3306
    database: str = "devops_digital_twin"
    user: str = "root"
    password: str = ""

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "DatabaseConfig":
        if environ is None:
            load_dotenv(
                dotenv_path=Path(__file__).resolve().parents[1] / ".env",
                override=False,
            )
            values = os.environ
        else:
            values = environ
        port_text = values.get("MYSQL_PORT", "3306")
        try:
            port = int(port_text)
        except (TypeError, ValueError) as error:
            raise DatabaseConfigurationError("MYSQL_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise DatabaseConfigurationError("MYSQL_PORT must be between 1 and 65535")

        config = cls(
            host=values.get("MYSQL_HOST", "localhost").strip(),
            port=port,
            database=values.get("MYSQL_DATABASE", "devops_digital_twin").strip(),
            user=values.get("MYSQL_USER", "root").strip(),
            password=values.get("MYSQL_PASSWORD", ""),
        )
        if not config.host or not config.database or not config.user:
            raise DatabaseConfigurationError(
                "MYSQL_HOST, MYSQL_DATABASE, and MYSQL_USER must not be empty"
            )
        return config