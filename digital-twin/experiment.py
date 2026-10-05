"""Typed experiment records for Digital Twin what-if workflows."""

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real
from typing import Any


class ExperimentError(ValueError):
    """Raised when experiment data or lifecycle transitions are invalid."""


class ScenarioType(str, Enum):
    """Scenarios supported by the Digital Twin simulator."""

    TRAFFIC_SURGE = "TRAFFIC_SURGE"
    INSTANCE_FAILURE = "INSTANCE_FAILURE"
    SCALE_OUT = "SCALE_OUT"


class ExperimentStatus(str, Enum):
    """Lifecycle states for an experiment."""

    CREATED = "CREATED"
    SIMULATED = "SIMULATED"
    EXECUTED = "EXECUTED"
    VALIDATED = "VALIDATED"


@dataclass(frozen=True)
class ScenarioParameters:
    """Validated parameters for one supported experiment scenario."""

    multiplier: float | None = None
    instance_name: str | None = None
    additional_instances: int | None = None

    @classmethod
    def traffic_surge(cls, multiplier: float) -> "ScenarioParameters":
        """Create parameters for a traffic surge experiment."""
        parameters = cls(multiplier=multiplier)
        parameters.validate(ScenarioType.TRAFFIC_SURGE)
        return parameters

    @classmethod
    def instance_failure(cls, instance_name: str) -> "ScenarioParameters":
        """Create parameters for an instance failure experiment."""
        parameters = cls(instance_name=instance_name)
        parameters.validate(ScenarioType.INSTANCE_FAILURE)
        return parameters

    @classmethod
    def scale_out(cls, additional_instances: int) -> "ScenarioParameters":
        """Create parameters for a scale-out experiment."""
        parameters = cls(additional_instances=additional_instances)
        parameters.validate(ScenarioType.SCALE_OUT)
        return parameters

    def validate(self, scenario_type: ScenarioType | str) -> None:
        """Validate required and scenario-specific parameter values."""
        try:
            scenario = ScenarioType(scenario_type)
        except (TypeError, ValueError) as error:
            raise ExperimentError("unsupported scenario type") from error

        if scenario is ScenarioType.TRAFFIC_SURGE:
            if self.multiplier is None or not self._positive_number(self.multiplier):
                raise ExperimentError("traffic surge requires a positive multiplier")
            if self.instance_name is not None or self.additional_instances is not None:
                raise ExperimentError("traffic surge has unsupported parameters")
        elif scenario is ScenarioType.INSTANCE_FAILURE:
            if self.instance_name is None or not self.instance_name.strip():
                raise ExperimentError("instance failure requires an instance name")
            if self.multiplier is not None or self.additional_instances is not None:
                raise ExperimentError("instance failure has unsupported parameters")
        elif scenario is ScenarioType.SCALE_OUT:
            if (
                self.additional_instances is None
                or isinstance(self.additional_instances, bool)
                or not isinstance(self.additional_instances, int)
                or self.additional_instances <= 0
            ):
                raise ExperimentError(
                    "scale out requires a positive integer additional_instances"
                )
            if self.multiplier is not None or self.instance_name is not None:
                raise ExperimentError("scale out has unsupported parameters")

    @staticmethod
    def _positive_number(value: object) -> bool:
        return (
            not isinstance(value, bool)
            and isinstance(value, Real)
            and isfinite(float(value))
            and float(value) > 0
        )


@dataclass
class Experiment:
    """Represent one Digital Twin experiment and its staged results."""

    experiment_id: str
    name: str
    scenario_type: ScenarioType | str
    scenario_parameters: ScenarioParameters
    status: ExperimentStatus | str = ExperimentStatus.CREATED
    baseline_state: Any | None = None
    expected_result: Any | None = None
    actual_result: Any | None = None
    validation_result: Any | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise ExperimentError("experiment_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ExperimentError("experiment name must be a non-empty string")
        try:
            self.scenario_type = ScenarioType(self.scenario_type)
        except (TypeError, ValueError) as error:
            raise ExperimentError("unsupported scenario type") from error
        try:
            self.status = ExperimentStatus(self.status)
        except (TypeError, ValueError) as error:
            raise ExperimentError("invalid experiment status") from error
        if not isinstance(self.scenario_parameters, ScenarioParameters):
            raise ExperimentError("scenario_parameters must be ScenarioParameters")
        self.scenario_parameters.validate(self.scenario_type)
        self.baseline_state = deepcopy(self.baseline_state)
        self.expected_result = deepcopy(self.expected_result)
        self.actual_result = deepcopy(self.actual_result)
        self.validation_result = deepcopy(self.validation_result)

    def transition_to(self, new_status: ExperimentStatus | str) -> None:
        """Advance exactly one step through the experiment lifecycle."""
        try:
            target = ExperimentStatus(new_status)
        except (TypeError, ValueError) as error:
            raise ExperimentError("invalid experiment status") from error
        transitions = {
            ExperimentStatus.CREATED: ExperimentStatus.SIMULATED,
            ExperimentStatus.SIMULATED: ExperimentStatus.EXECUTED,
            ExperimentStatus.EXECUTED: ExperimentStatus.VALIDATED,
        }
        if transitions.get(self.status) is not target:
            raise ExperimentError(
                f"invalid lifecycle transition: {self.status.value} -> {target.value}"
            )
        self.status = target

    @property
    def parameters(self) -> ScenarioParameters:
        """Return the structured scenario parameters."""
        return self.scenario_parameters