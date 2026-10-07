import importlib
from unittest.mock import Mock

import pytest


comparison_module = importlib.import_module("digital-twin.prediction_comparison")
validator_module = importlib.import_module("digital-twin.validator")

PredictionComparisonError = comparison_module.PredictionComparisonError
PredictionVsActualAnalyzer = comparison_module.PredictionVsActualAnalyzer
PredictionValidator = validator_module.PredictionValidator
ValidationStatus = validator_module.ValidationStatus


def metric(result, name: str):
    return next(item for item in result.comparisons if item.metric_name == name)


def test_exact_match() -> None:
    result = PredictionVsActualAnalyzer().compare("EXP-026A", {"cpu": 78}, {"cpu": 78})

    comparison = metric(result, "cpu")
    assert comparison.absolute_error == 0.0
    assert comparison.percentage_error == 0.0
    assert comparison.status == ValidationStatus.MATCH.value
    assert result.overall_status == ValidationStatus.MATCH.value


def test_numeric_difference_uses_validator_percentage_behavior() -> None:
    result = PredictionVsActualAnalyzer().compare("EXP-026A", {"cpu": 78}, {"cpu": 74})

    comparison = metric(result, "cpu")
    assert comparison.absolute_error == 4.0
    assert comparison.percentage_error == pytest.approx(4 / 78 * 100)


def test_multiple_metrics_are_compared() -> None:
    result = PredictionVsActualAnalyzer().compare(
        "EXP-026A", {"cpu": 78, "memory": 512}, {"cpu": 78, "memory": 500}
    )

    assert {item.metric_name for item in result.comparisons} == {"cpu", "memory"}
    assert metric(result, "memory").absolute_error == 12.0


def test_zero_expected_value_preserves_validator_behavior() -> None:
    comparison = metric(
        PredictionVsActualAnalyzer().compare("EXP-026A", {"cpu": 0}, {"cpu": 2}),
        "cpu",
    )

    assert comparison.absolute_error == 2.0
    assert comparison.percentage_error is None


@pytest.mark.parametrize(
    ("expected", "actual", "metric_name"),
    [({"cpu": 78}, {}, "cpu"), ({}, {"cpu": 78}, "cpu")],
)
def test_missing_metric_is_insufficient_data(expected, actual, metric_name) -> None:
    result = PredictionVsActualAnalyzer().compare("EXP-026A", expected, actual)

    comparison = metric(result, metric_name)
    assert comparison.status == ValidationStatus.INSUFFICIENT_DATA.value
    assert result.overall_status == ValidationStatus.INSUFFICIENT_DATA.value


def test_all_insufficient_data_has_insufficient_overall_status() -> None:
    result = PredictionVsActualAnalyzer().compare(
        "EXP-026A", {"cpu": None}, {"cpu": None}
    )

    assert result.overall_status == ValidationStatus.INSUFFICIENT_DATA.value


@pytest.mark.parametrize("experiment_id", [None, "", " ", 1, True])
def test_experiment_id_validation(experiment_id) -> None:
    with pytest.raises(PredictionComparisonError):
        PredictionVsActualAnalyzer().compare(experiment_id, {}, {})


@pytest.mark.parametrize("expected, actual", [([], {}), ({}, [])])
def test_metrics_must_be_mappings(expected, actual) -> None:
    with pytest.raises(PredictionComparisonError):
        PredictionVsActualAnalyzer().compare("EXP-026A", expected, actual)


def test_mixed_metric_outcomes_fail_overall_comparison() -> None:
    result = PredictionVsActualAnalyzer().compare(
        "EXP-026A", {"cpu": 78, "memory": None}, {"cpu": 74, "memory": 512}
    )

    assert result.overall_status == ValidationStatus.MISMATCH.value


def test_to_dict_is_json_compatible_structure() -> None:
    result = PredictionVsActualAnalyzer().compare("EXP-026A", {"cpu": 78}, {"cpu": 78})

    assert result.to_dict() == {
        "experiment_id": "EXP-026A",
        "comparisons": [
            {
                "metric_name": "cpu",
                "expected": 78,
                "actual": 78,
                "absolute_error": 0.0,
                "percentage_error": 0.0,
                "status": "MATCH",
            }
        ],
        "overall_status": "MATCH",
    }


def test_analyzer_delegates_comparison_to_injected_validator() -> None:
    validator = Mock(spec=PredictionValidator)
    validator.validate.return_value = PredictionValidator().validate(
        "EXP-026A", {"cpu": 78}, {"cpu": 74}
    )

    PredictionVsActualAnalyzer(validator).compare(
        "EXP-026A", {"cpu": 78}, {"cpu": 74}
    )

    validator.validate.assert_called_once_with(
        "EXP-026A", {"cpu": 78}, {"cpu": 74}
    )