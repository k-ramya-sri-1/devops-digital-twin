import importlib

import pytest


validator = importlib.import_module("digital-twin.validator")
PredictionValidator = validator.PredictionValidator
ValidationError = validator.ValidationError
ValidationStatus = validator.ValidationStatus


def comparison(result, name: str):
    return next(item for item in result.comparisons if item.name == name)


def test_exact_numeric_match() -> None:
    result = PredictionValidator().validate(
        "traffic-surge", {"request_rate": 100}, {"request_rate": 100}
    )

    metric = comparison(result, "request_rate")
    assert metric.status is ValidationStatus.MATCH
    assert metric.absolute_error == 0.0
    assert metric.percentage_error == 0.0


def test_numeric_mismatch_and_errors() -> None:
    result = PredictionValidator().validate(
        "traffic-surge", {"request_rate": 100}, {"request_rate": 125}
    )

    metric = comparison(result, "request_rate")
    assert metric.status is ValidationStatus.MISMATCH
    assert metric.absolute_error == 25.0
    assert metric.percentage_error == 25.0


def test_zero_expected_value_is_safe() -> None:
    result = PredictionValidator().validate(
        "zero-baseline", {"healthy_instances": 0}, {"healthy_instances": 2}
    )

    metric = comparison(result, "healthy_instances")
    assert metric.absolute_error == 2.0
    assert metric.percentage_error is None


def test_instance_and_healthy_instance_comparisons() -> None:
    result = PredictionValidator().validate(
        "instance-failure",
        {"instance_count": 3, "healthy_instance_count": 3},
        {"instance_count": 3, "healthy_instance_count": 2},
    )

    assert comparison(result, "instance_count").status is ValidationStatus.MATCH
    assert comparison(result, "healthy_instance_count").status is ValidationStatus.MISMATCH


def test_categorical_bottleneck_status_match() -> None:
    result = PredictionValidator().validate(
        "capacity-check", {"overall_status": "BOTTLENECK"}, {"overall_status": "BOTTLENECK"}
    )

    metric = comparison(result, "overall_status")
    assert metric.status is ValidationStatus.MATCH
    assert metric.categorical_match is True


def test_categorical_status_mismatch() -> None:
    result = PredictionValidator().validate(
        "capacity-check", {"cpu_status": "WARNING"}, {"cpu_status": "NORMAL"}
    )

    metric = comparison(result, "cpu_status")
    assert metric.status is ValidationStatus.MISMATCH
    assert metric.categorical_match is False


def test_unavailable_values_are_insufficient_data() -> None:
    result = PredictionValidator().validate(
        "missing-telemetry", {"cpu_status": None}, {"cpu_status": "NORMAL"}
    )

    metric = comparison(result, "cpu_status")
    assert metric.status is ValidationStatus.INSUFFICIENT_DATA
    assert result.overall_status is ValidationStatus.INSUFFICIENT_DATA


def test_overall_match() -> None:
    result = PredictionValidator().validate(
        "all-match",
        {"request_rate": 100, "overall_status": "NORMAL"},
        {"request_rate": 100, "overall_status": "NORMAL"},
    )

    assert result.comparable_metrics == 2
    assert result.matching_metrics == 2
    assert result.mismatched_metrics == 0
    assert result.overall_status is ValidationStatus.MATCH


def test_overall_mismatch() -> None:
    result = PredictionValidator().validate(
        "one-mismatch", {"request_rate": 100, "count": 2}, {"request_rate": 110, "count": 2}
    )

    assert result.comparable_metrics == 2
    assert result.matching_metrics == 1
    assert result.mismatched_metrics == 1
    assert result.overall_status is ValidationStatus.MISMATCH


def test_overall_insufficient_data() -> None:
    result = PredictionValidator().validate(
        "no-data", {"request_rate": None}, {"request_rate": None}
    )

    assert result.comparable_metrics == 0
    assert result.overall_status is ValidationStatus.INSUFFICIENT_DATA


def test_explicit_resource_statuses_are_compared() -> None:
    result = PredictionValidator().validate(
        "resource-status",
        {"cpu_status": "WARNING", "memory_status": "NORMAL"},
        {"cpu_status": "WARNING", "memory_status": "BOTTLENECK"},
    )

    assert result.matching_metrics == 1
    assert result.mismatched_metrics == 1


def test_inputs_remain_unchanged() -> None:
    expected = {"request_rate": 100, "overall_status": "NORMAL"}
    actual = {"request_rate": 100, "overall_status": "NORMAL"}

    PredictionValidator().validate("immutable-inputs", expected, actual)

    assert expected == {"request_rate": 100, "overall_status": "NORMAL"}
    assert actual == {"request_rate": 100, "overall_status": "NORMAL"}


@pytest.mark.parametrize(
    ("scenario", "expected", "actual"),
    [
        ("", {}, {}),
        ("scenario", [], {}),
        ("scenario", {"request_rate": []}, {}),
    ],
)
def test_invalid_input_is_rejected(scenario, expected, actual) -> None:
    with pytest.raises(ValidationError):
        PredictionValidator().validate(scenario, expected, actual)