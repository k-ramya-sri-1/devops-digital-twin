"""Deterministic validation of expected results against actual observations."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real
from typing import Any


class ValidationError(ValueError):
    """Raised when validation input is invalid."""


class ValidationStatus(str, Enum):
    """Statuses for metric comparisons and an overall validation run."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class MetricComparison:
    """Comparison result for one explicitly named expected/actual metric."""

    name: str
    expected: Any
    actual: Any
    status: ValidationStatus
    absolute_error: float | None = None
    percentage_error: float | None = None
    categorical_match: bool | None = None


@dataclass(frozen=True)
class ValidationResult:
    """Structured result for a scenario's expected-versus-actual validation."""

    scenario: str
    comparisons: tuple[MetricComparison, ...]
    comparable_metrics: int
    matching_metrics: int
    mismatched_metrics: int
    overall_status: ValidationStatus


class PredictionValidator:
    """Compare supplied expected and actual values without mutating either input."""

    def validate(
        self,
        scenario: str,
        expected: Mapping[str, object],
        actual: Mapping[str, object],
    ) -> ValidationResult:
        """Compare every metric explicitly supplied by either input mapping."""
        self._validate_inputs(scenario, expected, actual)
        comparisons = tuple(
            self._compare_metric(
                name,
                expected.get(name),
                actual.get(name),
                name in expected,
                name in actual,
            )
            for name in dict.fromkeys((*expected.keys(), *actual.keys()))
        )
        comparable_metrics = sum(
            comparison.status is not ValidationStatus.INSUFFICIENT_DATA
            for comparison in comparisons
        )
        matching_metrics = sum(
            comparison.status is ValidationStatus.MATCH
            for comparison in comparisons
        )
        mismatched_metrics = sum(
            comparison.status is ValidationStatus.MISMATCH
            for comparison in comparisons
        )
        if mismatched_metrics:
            overall_status = ValidationStatus.MISMATCH
        elif not comparisons or any(
            comparison.status is ValidationStatus.INSUFFICIENT_DATA
            for comparison in comparisons
        ):
            overall_status = ValidationStatus.INSUFFICIENT_DATA
        else:
            overall_status = ValidationStatus.MATCH

        return ValidationResult(
            scenario=scenario,
            comparisons=comparisons,
            comparable_metrics=comparable_metrics,
            matching_metrics=matching_metrics,
            mismatched_metrics=mismatched_metrics,
            overall_status=overall_status,
        )

    @staticmethod
    def _validate_inputs(
        scenario: str,
        expected: Mapping[str, object],
        actual: Mapping[str, object],
    ) -> None:
        if not isinstance(scenario, str) or not scenario.strip():
            raise ValidationError("scenario must be a non-empty string")
        if not isinstance(expected, Mapping) or not isinstance(actual, Mapping):
            raise ValidationError("expected and actual values must be mappings")
        for metrics in (expected, actual):
            for name, value in metrics.items():
                if not isinstance(name, str) or not name.strip():
                    raise ValidationError("metric names must be non-empty strings")
                if value is not None and not isinstance(value, (str, Real, Enum)):
                    raise ValidationError(
                        f"metric '{name}' has an unsupported value type"
                    )

    @classmethod
    def _compare_metric(
        cls,
        name: str,
        expected: object,
        actual: object,
        expected_supplied: bool,
        actual_supplied: bool,
    ) -> MetricComparison:
        if (
            not expected_supplied
            or not actual_supplied
            or expected is None
            or actual is None
        ):
            return MetricComparison(
                name=name,
                expected=expected,
                actual=actual,
                status=ValidationStatus.INSUFFICIENT_DATA,
            )

        if cls._is_numeric(expected) and cls._is_numeric(actual):
            expected_number = float(expected)
            actual_number = float(actual)
            absolute_error = abs(expected_number - actual_number)
            percentage_error = (
                absolute_error / abs(expected_number) * 100
                if expected_number != 0
                else None
            )
            return MetricComparison(
                name=name,
                expected=expected,
                actual=actual,
                status=(
                    ValidationStatus.MATCH
                    if expected_number == actual_number
                    else ValidationStatus.MISMATCH
                ),
                absolute_error=absolute_error,
                percentage_error=percentage_error,
            )

        if cls._is_numeric(expected) != cls._is_numeric(actual):
            raise ValidationError(
                f"metric '{name}' cannot compare numeric and categorical values"
            )
        categorical_match = expected == actual
        return MetricComparison(
            name=name,
            expected=expected,
            actual=actual,
            status=(
                ValidationStatus.MATCH
                if categorical_match
                else ValidationStatus.MISMATCH
            ),
            categorical_match=categorical_match,
        )

    @staticmethod
    def _is_numeric(value: object) -> bool:
        if isinstance(value, bool) or isinstance(value, Enum):
            return False
        if not isinstance(value, Real):
            return False
        return isfinite(float(value))