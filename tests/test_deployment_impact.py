import importlib
from dataclasses import replace

import pytest


analyzer_module = importlib.import_module("digital-twin.analyzer")
actual_result_module = importlib.import_module("digital-twin.actual_result")
bottleneck_module = importlib.import_module("digital-twin.bottleneck")
deployment_impact_module = importlib.import_module("digital-twin.deployment_impact")
experiment_module = importlib.import_module("digital-twin.experiment")
executor_module = importlib.import_module("digital-twin.executor")
prediction_comparison_module = importlib.import_module(
    "digital-twin.prediction_comparison"
)
predictor_module = importlib.import_module("digital-twin.predictor")

CapacitySnapshot = analyzer_module.CapacitySnapshot
TrafficImpactResult = analyzer_module.TrafficImpactResult
InstanceFailureImpactResult = analyzer_module.InstanceFailureImpactResult
ScaleOutImpactResult = analyzer_module.ScaleOutImpactResult
ActualKubernetesResult = actual_result_module.ActualKubernetesResult
BottleneckResult = bottleneck_module.BottleneckResult
BottleneckStatus = bottleneck_module.BottleneckStatus
DeploymentImpactError = deployment_impact_module.DeploymentImpactError
DeploymentImpactReportBuilder = deployment_impact_module.DeploymentImpactReportBuilder
ImpactSeverity = deployment_impact_module.ImpactSeverity
PredictionMetricComparison = prediction_comparison_module.PredictionMetricComparison
PredictionVsActualResult = prediction_comparison_module.PredictionVsActualResult
ExecutionResult = executor_module.ExecutionResult
ScenarioType = experiment_module.ScenarioType
ResourcePredictionResult = predictor_module.ResourcePredictionResult
ResourceStatus = predictor_module.ResourceStatus

SERVICE_NAME = "devops-digital-twin"
EXPERIMENT_ID = "EXP-027A"


def make_impact(scenario_type):
    if scenario_type is ScenarioType.TRAFFIC_SURGE:
        return TrafficImpactResult(SERVICE_NAME, 150.0, 300.0, 150.0, 100.0)
    if scenario_type is ScenarioType.INSTANCE_FAILURE:
        return InstanceFailureImpactResult(
            service_name=SERVICE_NAME,
            original_instance_count=2,
            simulated_instance_count=2,
            original_healthy_instance_count=2,
            simulated_healthy_instance_count=1,
            original_capacity=CapacitySnapshot(4.0, 2048.0),
            simulated_capacity=CapacitySnapshot(2.0, 1024.0),
            capacity_change=CapacitySnapshot(-2.0, -1024.0),
            healthy_instance_change=-1,
        )
    return ScaleOutImpactResult(
        service_name=SERVICE_NAME,
        original_instance_count=2,
        simulated_instance_count=3,
        instance_count_change=1,
        original_capacity=CapacitySnapshot(4.0, 2048.0),
        simulated_capacity=CapacitySnapshot(6.0, 3072.0),
        capacity_change=CapacitySnapshot(2.0, 1024.0),
    )


def make_prediction(
    *,
    cpu_status=ResourceStatus.SUFFICIENT,
    memory_status=ResourceStatus.SUFFICIENT,
):
    return ResourcePredictionResult(
        service_name=SERVICE_NAME,
        original_request_rate=150.0,
        simulated_request_rate=300.0,
        workload_multiplier=2.0,
        healthy_instance_count=2,
        total_instance_count=2,
        cpu_capacity=4.0,
        memory_capacity=2048.0,
        healthy_cpu_capacity=4.0,
        healthy_memory_capacity=2048.0,
        projected_cpu_demand=4.0,
        projected_memory_demand=1024.0,
        cpu_status=cpu_status,
        memory_status=memory_status,
        insufficient_data=(
            ("cpu",) if cpu_status is ResourceStatus.INSUFFICIENT_DATA else ()
        ),
    )


def make_bottleneck(status=BottleneckStatus.NO_BOTTLENECK):
    return BottleneckResult(
        service_name=SERVICE_NAME,
        cpu_utilization=50.0,
        memory_utilization=25.0,
        cpu_status=BottleneckStatus.NORMAL,
        memory_status=BottleneckStatus.NORMAL,
        total_instance_count=2,
        healthy_instance_count=2,
        unhealthy_instance_count=0,
        total_cpu_capacity=4.0,
        total_memory_capacity=2048.0,
        healthy_cpu_capacity=4.0,
        healthy_memory_capacity=2048.0,
        overall_status=status,
        reasons=("test reason",),
    )


def make_execution_result(
    scenario_type=ScenarioType.SCALE_OUT,
    *,
    bottleneck_status=BottleneckStatus.NO_BOTTLENECK,
    cpu_status=ResourceStatus.SUFFICIENT,
    memory_status=ResourceStatus.SUFFICIENT,
):
    return ExecutionResult(
        experiment_id=EXPERIMENT_ID,
        scenario_type=scenario_type,
        service_name=SERVICE_NAME,
        simulation=object(),
        impact=make_impact(scenario_type),
        prediction=make_prediction(
            cpu_status=cpu_status,
            memory_status=memory_status,
        ),
        bottleneck=make_bottleneck(bottleneck_status),
    )


def make_actual(experiment_id=EXPERIMENT_ID):
    return ActualKubernetesResult(
        experiment_id=experiment_id,
        deployment_name=SERVICE_NAME,
        namespace="default",
        desired_replicas=3,
        ready_replicas=3,
        available_replicas=3,
        updated_replicas=3,
    )


def make_comparison(experiment_id=EXPERIMENT_ID, status="MATCH"):
    return PredictionVsActualResult(
        experiment_id=experiment_id,
        comparisons=(
            PredictionMetricComparison(
                metric_name="replica_count",
                expected=3,
                actual=3 if status == "MATCH" else 2,
                absolute_error=0.0 if status == "MATCH" else 1.0,
                percentage_error=0.0 if status == "MATCH" else 33.333,
                status=status,
            ),
        ),
        overall_status=status,
    )


def test_scale_out_report_without_validation():
    report = DeploymentImpactReportBuilder().build(make_execution_result())

    assert report.experiment_id == EXPERIMENT_ID
    assert report.scenario_type is ScenarioType.SCALE_OUT
    assert report.actual_result is None
    assert report.prediction_accuracy is None
    assert report.limitations == (
        "actual validation is pending or unavailable",
        "prediction comparison is not available",
    )


def test_scale_out_report_preserves_validation_results():
    actual = make_actual()
    comparison = make_comparison()

    report = DeploymentImpactReportBuilder().build(
        make_execution_result(), actual, comparison
    )

    assert report.actual_result is actual
    assert report.prediction_accuracy is comparison
    assert report.limitations == ()


def test_traffic_surge_report():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(ScenarioType.TRAFFIC_SURGE)
    )

    assert report.scenario_type is ScenarioType.TRAFFIC_SURGE
    assert report.simulated_impact is not None
    assert "actual validation is pending or unavailable" in report.limitations


def test_instance_failure_report():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(ScenarioType.INSTANCE_FAILURE)
    )

    assert report.scenario_type is ScenarioType.INSTANCE_FAILURE
    assert report.simulated_impact.healthy_instance_change == -1


def test_high_severity_from_bottleneck():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(bottleneck_status=BottleneckStatus.BOTTLENECK)
    )

    assert report.overall_severity is ImpactSeverity.HIGH


def test_high_severity_from_insufficient_prediction_data():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(cpu_status=ResourceStatus.INSUFFICIENT)
    )

    assert report.overall_severity is ImpactSeverity.HIGH


def test_medium_severity_from_warning():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(bottleneck_status=BottleneckStatus.WARNING)
    )

    assert report.overall_severity is ImpactSeverity.MEDIUM


def test_low_severity_from_no_bottleneck_and_sufficient_prediction():
    report = DeploymentImpactReportBuilder().build(make_execution_result())

    assert report.overall_severity is ImpactSeverity.LOW


def test_insufficient_data_severity():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(
            bottleneck_status=BottleneckStatus.INSUFFICIENT_DATA,
            cpu_status=ResourceStatus.SUFFICIENT,
        )
    )

    assert report.overall_severity is ImpactSeverity.INSUFFICIENT_DATA


def test_prediction_mismatch_does_not_increase_severity():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(), make_actual(), make_comparison(status="MISMATCH")
    )

    assert report.overall_severity is ImpactSeverity.LOW
    assert report.prediction_accuracy.overall_status == "MISMATCH"


def test_missing_actual_result_produces_limitation():
    report = DeploymentImpactReportBuilder().build(make_execution_result())

    assert "actual validation is pending or unavailable" in report.limitations


@pytest.mark.parametrize(
    ("actual_result", "prediction_comparison", "message"),
    [
        (make_actual("OTHER"), None, "actual_result experiment ID"),
        (None, make_comparison("OTHER"), "prediction_comparison experiment ID"),
        (make_actual("OTHER-A"), make_comparison("OTHER-B"), "actual_result experiment ID"),
    ],
)
def test_experiment_id_mismatches_raise_controlled_error(
    actual_result, prediction_comparison, message
):
    with pytest.raises(DeploymentImpactError, match=message):
        DeploymentImpactReportBuilder().build(
            make_execution_result(), actual_result, prediction_comparison
        )


def test_report_preserves_original_typed_result_objects():
    execution_result = make_execution_result()

    report = DeploymentImpactReportBuilder().build(execution_result)

    assert report.simulated_impact is execution_result.impact
    assert report.predicted_demand is execution_result.prediction
    assert report.bottleneck is execution_result.bottleneck


def test_builder_does_not_mutate_execution_result():
    execution_result = make_execution_result()
    before = replace(execution_result)

    DeploymentImpactReportBuilder().build(execution_result)

    assert execution_result == before


def test_to_dict_is_deterministic_and_json_compatible():
    report = DeploymentImpactReportBuilder().build(
        make_execution_result(), make_actual(), make_comparison()
    )

    assert report.to_dict() == report.to_dict()
    assert report.to_dict()["scenario_type"] == "SCALE_OUT"
    assert report.to_dict()["overall_severity"] == "LOW"
    assert report.to_dict()["actual_result"]["desired_replicas"] == 3
    assert report.to_dict()["prediction_accuracy"]["overall_status"] == "MATCH"
