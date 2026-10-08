"""Deterministic DevOps recommendations from deployment impact reports."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .bottleneck import BottleneckStatus
from .deployment_impact import DeploymentImpactReport
from .predictor import ResourceStatus


class RecommendationError(ValueError):
    """Raised when a deployment impact report cannot be recommended from."""


class RecommendationPriority(str, Enum):
    """Priority assigned to one recommendation."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


class RecommendationAction(str, Enum):
    """Action categories supported by the recommendation engine."""

    SCALE_OUT = "SCALE_OUT"
    MAINTAIN = "MAINTAIN"
    INVESTIGATE_BOTTLENECK = "INVESTIGATE_BOTTLENECK"
    MONITOR = "MONITOR"
    COLLECT_DATA = "COLLECT_DATA"
    REVIEW_PREDICTION = "REVIEW_PREDICTION"


@dataclass(frozen=True)
class Recommendation:
    """Immutable recommendation backed by report evidence."""

    action: RecommendationAction
    priority: RecommendationPriority
    reason: str
    evidence: tuple[str, ...]
    experiment_id: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of the recommendation."""
        return {
            "action": self.action.value,
            "priority": self.priority.value,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "experiment_id": self.experiment_id,
        }


@dataclass(frozen=True)
class RecommendationReport:
    """Immutable recommendations produced for one deployment impact report."""

    experiment_id: str
    recommendations: tuple[Recommendation, ...]
    overall_priority: RecommendationPriority
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation of the report."""
        return {
            "experiment_id": self.experiment_id,
            "recommendations": [
                recommendation.to_dict()
                for recommendation in self.recommendations
            ],
            "overall_priority": self.overall_priority.value,
            "limitations": list(self.limitations),
        }


class RecommendationEngine:
    """Apply deterministic recommendation rules to an impact report."""

    def recommend(
        self, report: DeploymentImpactReport
    ) -> RecommendationReport:
        """Create recommendations without performing any external operations."""
        self._validate_report(report)
        experiment_id = report.experiment_id
        recommendations: list[Recommendation] = []
        bottleneck_status = report.bottleneck.overall_status
        prediction_statuses = (
            report.predicted_demand.cpu_status,
            report.predicted_demand.memory_status,
        )

        if bottleneck_status is BottleneckStatus.BOTTLENECK:
            recommendations.append(
                Recommendation(
                    action=RecommendationAction.INVESTIGATE_BOTTLENECK,
                    priority=RecommendationPriority.HIGH,
                    reason="investigate the detected deployment bottleneck",
                    evidence=(
                        f"bottleneck.overall_status={bottleneck_status.value}",
                    ),
                    experiment_id=experiment_id,
                )
            )

        insufficient_statuses = tuple(
            status
            for status in prediction_statuses
            if status is ResourceStatus.INSUFFICIENT
        )
        if insufficient_statuses:
            recommendations.append(
                Recommendation(
                    action=RecommendationAction.SCALE_OUT,
                    priority=RecommendationPriority.HIGH,
                    reason="scale out to address insufficient predicted capacity",
                    evidence=tuple(
                        f"{resource}_status={status.value}"
                        for resource, status in zip(
                            ("cpu", "memory"), prediction_statuses
                        )
                        if status is ResourceStatus.INSUFFICIENT
                    ),
                    experiment_id=experiment_id,
                )
            )

        if bottleneck_status is BottleneckStatus.WARNING:
            recommendations.append(
                Recommendation(
                    action=RecommendationAction.MONITOR,
                    priority=RecommendationPriority.MEDIUM,
                    reason="monitor the deployment because a bottleneck warning was detected",
                    evidence=(
                        f"bottleneck.overall_status={bottleneck_status.value}",
                    ),
                    experiment_id=experiment_id,
                )
            )

        if (
            bottleneck_status is BottleneckStatus.NO_BOTTLENECK
            and all(status is ResourceStatus.SUFFICIENT for status in prediction_statuses)
        ):
            recommendations.append(
                Recommendation(
                    action=RecommendationAction.MAINTAIN,
                    priority=RecommendationPriority.LOW,
                    reason="maintain the deployment because predicted demand is covered",
                    evidence=(
                        "bottleneck.overall_status=NO_BOTTLENECK",
                        "cpu_status=SUFFICIENT",
                        "memory_status=SUFFICIENT",
                    ),
                    experiment_id=experiment_id,
                )
            )

        if report.prediction_accuracy is not None and (
            report.prediction_accuracy.overall_status == "MISMATCH"
        ):
            recommendations.append(
                Recommendation(
                    action=RecommendationAction.REVIEW_PREDICTION,
                    priority=RecommendationPriority.MEDIUM,
                    reason="review the prediction because observed results differed",
                    evidence=(
                        "prediction_accuracy.overall_status=MISMATCH",
                    ),
                    experiment_id=experiment_id,
                )
            )

        data_insufficient = tuple(
            status
            for status in prediction_statuses
            if status is ResourceStatus.INSUFFICIENT_DATA
        )
        if data_insufficient:
            recommendations.append(
                Recommendation(
                    action=RecommendationAction.COLLECT_DATA,
                    priority=RecommendationPriority.INFORMATIONAL,
                    reason="collect missing prediction data before making a complete assessment",
                    evidence=tuple(
                        f"{resource}_status={status.value}"
                        for resource, status in zip(
                            ("cpu", "memory"), prediction_statuses
                        )
                        if status is ResourceStatus.INSUFFICIENT_DATA
                    ),
                    experiment_id=experiment_id,
                )
            )

        limitations = list(report.limitations)
        if data_insufficient:
            limitations.append(
                "recommendation data is insufficient for a complete assessment"
            )
        if not recommendations:
            limitations.append("no actionable recommendation could be determined")
        limitations = list(dict.fromkeys(limitations))

        return RecommendationReport(
            experiment_id=experiment_id,
            recommendations=tuple(recommendations),
            overall_priority=self._overall_priority(recommendations),
            limitations=tuple(limitations),
        )

    @staticmethod
    def _validate_report(report: DeploymentImpactReport) -> None:
        if not isinstance(report, DeploymentImpactReport):
            raise RecommendationError(
                "report must be a DeploymentImpactReport"
            )
        if not isinstance(report.experiment_id, str) or not report.experiment_id.strip():
            raise RecommendationError("experiment_id must be a non-empty string")

    @staticmethod
    def _overall_priority(
        recommendations: list[Recommendation],
    ) -> RecommendationPriority:
        priority_order = (
            RecommendationPriority.HIGH,
            RecommendationPriority.MEDIUM,
            RecommendationPriority.LOW,
            RecommendationPriority.INFORMATIONAL,
        )
        for priority in priority_order:
            if any(item.priority is priority for item in recommendations):
                return priority
        return RecommendationPriority.INFORMATIONAL
