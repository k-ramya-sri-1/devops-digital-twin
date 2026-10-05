import importlib

import pytest


experiment = importlib.import_module("digital-twin.experiment")
Experiment = experiment.Experiment
ExperimentError = experiment.ExperimentError
ExperimentStatus = experiment.ExperimentStatus
ScenarioParameters = experiment.ScenarioParameters
ScenarioType = experiment.ScenarioType


def test_creating_traffic_surge_experiment() -> None:
    item = Experiment(
        "exp-1",
        "double traffic",
        ScenarioType.TRAFFIC_SURGE,
        ScenarioParameters.traffic_surge(2.0),
    )

    assert item.experiment_id == "exp-1"
    assert item.scenario_type is ScenarioType.TRAFFIC_SURGE
    assert item.parameters.multiplier == 2.0
    assert item.status is ExperimentStatus.CREATED


def test_creating_instance_failure_experiment() -> None:
    item = Experiment(
        "exp-2",
        "fail instance",
        ScenarioType.INSTANCE_FAILURE,
        ScenarioParameters.instance_failure("instance-1"),
    )

    assert item.parameters.instance_name == "instance-1"


def test_creating_scale_out_experiment() -> None:
    item = Experiment(
        "exp-3",
        "add capacity",
        ScenarioType.SCALE_OUT,
        ScenarioParameters.scale_out(2),
    )

    assert item.parameters.additional_instances == 2


@pytest.mark.parametrize(
    ("scenario_type", "parameters"),
    [
        (ScenarioType.TRAFFIC_SURGE, ScenarioParameters(multiplier=0)),
        (ScenarioType.TRAFFIC_SURGE, ScenarioParameters(multiplier=-1)),
        (ScenarioType.INSTANCE_FAILURE, ScenarioParameters(instance_name="")),
        (ScenarioType.SCALE_OUT, ScenarioParameters(additional_instances=0)),
        (ScenarioType.SCALE_OUT, ScenarioParameters(additional_instances=1.5)),
        (ScenarioType.TRAFFIC_SURGE, ScenarioParameters(instance_name="instance-1")),
    ],
)
def test_invalid_scenario_parameters_are_rejected(scenario_type, parameters) -> None:
    with pytest.raises(ExperimentError):
        Experiment("exp-invalid", "invalid", scenario_type, parameters)


def test_experiment_name_validation() -> None:
    with pytest.raises(ExperimentError, match="experiment name"):
        Experiment(
            "exp-1",
            " ",
            ScenarioType.TRAFFIC_SURGE,
            ScenarioParameters.traffic_surge(2),
        )


def test_lifecycle_status_progression() -> None:
    item = Experiment(
        "exp-life",
        "lifecycle",
        ScenarioType.SCALE_OUT,
        ScenarioParameters.scale_out(1),
    )

    item.transition_to(ExperimentStatus.SIMULATED)
    item.transition_to(ExperimentStatus.EXECUTED)
    item.transition_to(ExperimentStatus.VALIDATED)

    assert item.status is ExperimentStatus.VALIDATED


def test_invalid_lifecycle_transition_is_rejected() -> None:
    item = Experiment(
        "exp-life-invalid",
        "lifecycle",
        ScenarioType.SCALE_OUT,
        ScenarioParameters.scale_out(1),
    )

    with pytest.raises(ExperimentError, match="invalid lifecycle transition"):
        item.transition_to(ExperimentStatus.EXECUTED)


def test_expected_actual_and_validation_results_are_stored() -> None:
    expected = {"status": "NO_BOTTLENECK"}
    actual = {"status": "WARNING"}
    validation = {"overall_status": "MISMATCH"}
    item = Experiment(
        "exp-results",
        "results",
        ScenarioType.TRAFFIC_SURGE,
        ScenarioParameters.traffic_surge(2),
        expected_result=expected,
        actual_result=actual,
        validation_result=validation,
    )

    assert item.expected_result == expected
    assert item.actual_result == actual
    assert item.validation_result == validation


def test_references_are_copied() -> None:
    baseline = {"instances": ["instance-1"]}
    expected = {"request_rate": 200}
    item = Experiment(
        "exp-copy",
        "copy references",
        ScenarioType.TRAFFIC_SURGE,
        ScenarioParameters.traffic_surge(2),
        baseline_state=baseline,
        expected_result=expected,
    )

    baseline["instances"].append("instance-2")
    expected["request_rate"] = 300

    assert item.baseline_state == {"instances": ["instance-1"]}
    assert item.expected_result == {"request_rate": 200}


def test_invalid_experiment_data_is_rejected() -> None:
    with pytest.raises(ExperimentError, match="experiment_id"):
        Experiment(
            "",
            "name",
            ScenarioType.TRAFFIC_SURGE,
            ScenarioParameters.traffic_surge(2),
        )
    with pytest.raises(ExperimentError, match="unsupported scenario"):
        Experiment(
            "exp-unsupported",
            "name",
            "UNSUPPORTED",
            ScenarioParameters.traffic_surge(2),
        )
    with pytest.raises(ExperimentError, match="scenario_parameters"):
        Experiment("exp-parameters", "name", ScenarioType.SCALE_OUT, {})