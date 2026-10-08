import importlib
from dataclasses import FrozenInstanceError, replace

import pytest

from tests.test_deployment_impact import (
    make_actual,
    make_comparison,
    make_execution_result,
)


deployment_impact_module = importlib.import_module("digital-twin.deployment_impact")
experiment_module = importlib.import_module("digital-twin.experiment")
bottleneck_module = importlib.import_module("digital-twin.bottleneck")
predictor_module = importlib.import_module("digital-twin.predictor")
recommendation_module = importlib.import_module("digital-twin.recommendation")

BottleneckStatus = bottleneck_module.BottleneckStatus
DeploymentImpactReportBuilder = deployment_impact_module.DeploymentImpactReportBuilder
ImpactSeverity = deployment_impact_module.ImpactSeverity
ScenarioType = experiment_module.ScenarioType
ResourceStatus = predictor_module.ResourceStatus
Recommendation = recommendation_module.Recommendation
RecommendationAction = recommendation_module.RecommendationAction
RecommendationEngine = recommendation_module.RecommendationEngine
RecommendationError = recommendation_module.RecommendationError
RecommendationPriority = recommendation_module.RecommendationPriority
RecommendationReport = recommendation_module.RecommendationReport


def make_report(
    *,
    scenario_type=ScenarioType.SCALE_OUT,
    bottleneck_status=BottleneckStatus.NO_BOTTLENECK,
    cpu_status=ResourceStatus.SUFFICIENT,
    memory_status=ResourceStatus.SUFFICIENT,
    with_comparison=False,
    comparison_status="MATCH",
):
    execution_result = make_execution_result(
        scenario_type,
        bottleneck_status=bottleneck_status,
        cpu_status=cpu_status,
        memory_status=memory_status,
    )
    return DeploymentImpactReportBuilder().build(
        execution_result,
        make_actual() if with_comparison else None,
        make_comparison(status=comparison_status) if with_comparison else None,
    )


def actions(report):
    return [recommendation.action for recommendation in report.recommendations]


def find_action(report, action):
    return next(item for item in report.recommendations if item.action is action)


def test_bottleneck_produces_high_investigate_recommendation():
    result = RecommendationEngine().recommend(
        make_report(bottleneck_status=BottleneckStatus.BOTTLENECK)
    )

    recommendation = find_action(result, RecommendationAction.INVESTIGATE_BOTTLENECK)
    assert recommendation.priority is RecommendationPriority.HIGH
    assert result.overall_priority is RecommendationPriority.HIGH


def test_insufficient_prediction_produces_high_scale_out_recommendation():
    result = RecommendationEngine().recommend(
        make_report(cpu_status=ResourceStatus.INSUFFICIENT)
    )

    recommendation = find_action(result, RecommendationAction.SCALE_OUT)
    assert recommendation.priority is RecommendationPriority.HIGH
    assert recommendation.evidence == ("cpu_status=INSUFFICIENT",)


def test_warning_produces_medium_monitor_recommendation():
    result = RecommendationEngine().recommend(
        make_report(bottleneck_status=BottleneckStatus.WARNING)
    )

    recommendation = find_action(result, RecommendationAction.MONITOR)
    assert recommendation.priority is RecommendationPriority.MEDIUM
    assert result.overall_priority is RecommendationPriority.MEDIUM


def test_sufficient_prediction_without_bottleneck_produces_low_maintain():
    result = RecommendationEngine().recommend(make_report())

    recommendation = find_action(result, RecommendationAction.MAINTAIN)
    assert recommendation.priority is RecommendationPriority.LOW
    assert result.overall_priority is RecommendationPriority.LOW


def test_prediction_mismatch_produces_review_recommendation():
    result = RecommendationEngine().recommend(
        make_report(with_comparison=True, comparison_status="MISMATCH")
    )

    recommendation = find_action(result, RecommendationAction.REVIEW_PREDICTION)
    assert recommendation.priority is RecommendationPriority.MEDIUM


def test_prediction_mismatch_does_not_override_high_risk():
    result = RecommendationEngine().recommend(
        make_report(
            bottleneck_status=BottleneckStatus.BOTTLENECK,
            with_comparison=True,
            comparison_status="MISMATCH",
        )
    )

    assert actions(result) == [
        RecommendationAction.INVESTIGATE_BOTTLENECK,
        RecommendationAction.REVIEW_PREDICTION,
    ]
    assert result.overall_priority is RecommendationPriority.HIGH


def test_insufficient_data_produces_informational_collect_data():
    result = RecommendationEngine().recommend(
        make_report(cpu_status=ResourceStatus.INSUFFICIENT_DATA)
    )

    recommendation = find_action(result, RecommendationAction.COLLECT_DATA)
    assert recommendation.priority is RecommendationPriority.INFORMATIONAL
    assert result.overall_priority is RecommendationPriority.INFORMATIONAL
    assert "recommendation data is insufficient" in result.limitations[-1]


def test_multiple_recommendations_can_coexist():
    result = RecommendationEngine().recommend(
        make_report(
            bottleneck_status=BottleneckStatus.BOTTLENECK,
            cpu_status=ResourceStatus.INSUFFICIENT,
            memory_status=ResourceStatus.INSUFFICIENT_DATA,
            with_comparison=True,
            comparison_status="MISMATCH",
        )
    )

    assert actions(result) == [
        RecommendationAction.INVESTIGATE_BOTTLENECK,
        RecommendationAction.SCALE_OUT,
        RecommendationAction.REVIEW_PREDICTION,
        RecommendationAction.COLLECT_DATA,
    ]
    assert result.overall_priority is RecommendationPriority.HIGH


def test_recommendation_output_is_deterministic():
    report = make_report(
        bottleneck_status=BottleneckStatus.WARNING,
        with_comparison=True,
        comparison_status="MISMATCH",
    )

    first = RecommendationEngine().recommend(report)
    second = RecommendationEngine().recommend(report)

    assert first == second
    assert first.to_dict() == second.to_dict()



def test_result_objects_are_frozen():
    result = RecommendationEngine().recommend(make_report())

    with pytest.raises(FrozenInstanceError):
        result.overall_priority = RecommendationPriority.HIGH
    with pytest.raises(FrozenInstanceError):
        result.recommendations[0].action = RecommendationAction.MONITOR


def test_experiment_id_is_preserved():
    result = RecommendationEngine().recommend(make_report())

    assert result.experiment_id == "EXP-027A"
    assert all(
        recommendation.experiment_id == "EXP-027A"
        for recommendation in result.recommendations
    )


def test_report_limitations_are_preserved():
    report = make_report()
    report = replace(
        report,
        limitations=("actual validation is pending or unavailable",),
    )

    result = RecommendationEngine().recommend(report)

    assert result.limitations == ("actual validation is pending or unavailable",)


@pytest.mark.parametrize(
    "scenario_type",
    [
        ScenarioType.TRAFFIC_SURGE,
        ScenarioType.INSTANCE_FAILURE,
        ScenarioType.SCALE_OUT,
    ],
)
def test_all_existing_scenarios_are_supported(scenario_type):
    result = RecommendationEngine().recommend(
        make_report(scenario_type=scenario_type)
    )

    assert result.experiment_id == "EXP-027A"
    assert actions(result) == [RecommendationAction.MAINTAIN]


def test_to_dict_serializes_report_and_recommendations():
    result = RecommendationEngine().recommend(
        make_report(with_comparison=True, comparison_status="MISMATCH")
    )

    serialized = result.to_dict()

    assert serialized["experiment_id"] == "EXP-027A"
    assert serialized["overall_priority"] == "MEDIUM"
    assert serialized["recommendations"][0]["action"] == "MAINTAIN"
    assert serialized["recommendations"][1]["action"] == "REVIEW_PREDICTION"
    assert serialized["recommendations"][0]["evidence"]


def test_invalid_report_identity_is_rejected():
    report = replace(make_report(), experiment_id=" ")

    with pytest.raises(RecommendationError, match="experiment_id"):
        RecommendationEngine().recommend(report)


def test_invalid_report_type_is_rejected():
    with pytest.raises(RecommendationError, match="DeploymentImpactReport"):
        RecommendationEngine().recommend(object())


def test_recommendation_dataclass_is_frozen_and_serializable():
    recommendation = Recommendation(
        action=RecommendationAction.MONITOR,
        priority=RecommendationPriority.MEDIUM,
        reason="test reason",
        evidence=("test evidence",),
        experiment_id="EXP-027A",
    )

    assert recommendation.to_dict() == {
        "action": "MONITOR",
        "priority": "MEDIUM",
        "reason": "test reason",
        "evidence": ["test evidence"],
        "experiment_id": "EXP-027A",
    }
    with pytest.raises(FrozenInstanceError):
        recommendation.reason = "changed"


def test_engine_has_no_external_system_dependencies():
    engine = RecommendationEngine()

    assert not hasattr(engine, "kubernetes")
    assert not hasattr(engine, "prometheus")
    assert not hasattr(engine, "mysql")
