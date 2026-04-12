"""
ABC for visitor- vs resident-centred anomaly pipelines.

Each subclass chooses which feature scopes apply and implements scope-specific
engineering differently (same AnalysisScope + feature name can differ by type).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.scope_config import scopes_for_anomaly_type
from app.domain.anomaly_types import AnomalyType
from app.domain.scopes import AnalysisScope


class AnomalyPipelineBase(ABC):
    """Visitor vs resident subclasses override scope rules and engineering."""

    @property
    @abstractmethod
    def anomaly_type(self) -> AnomalyType:
        """Which high-level detection mode this pipeline implements."""

    def allowed_feature_scopes(self) -> list[AnalysisScope]:
        """Feature scopes for this anomaly type (see ``app.core.scope_config``)."""
        return scopes_for_anomaly_type(self.anomaly_type)

    @abstractmethod
    async def engineer_scope_features(
        self,
        scope: AnalysisScope,
        raw_records: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, float]:
        """
        Build the feature vector for one feature scope.

        Differs by (anomaly_type, scope) even when the scope enum matches.
        """

    @abstractmethod
    async def score_scope(
        self, scope: AnalysisScope, features: dict[str, float]
    ) -> float:
        """Single-scope score in [0, 1] (stub until ensemble models exist)."""


class VisitorAnomalyPipeline(AnomalyPipelineBase):
    """Visitor mode: all feature scopes; engineering uses visitor context."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.VISITOR

    async def engineer_scope_features(
        self,
        scope: AnalysisScope,
        raw_records: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, float]:
        # Placeholder: branch on scope and visitor semantics.
        return {
            "pipeline": "visitor",
            "scope": scope.value,
            "stub": 0.0,
        }

    async def score_scope(
        self, scope: AnalysisScope, features: dict[str, float]
    ) -> float:
        return 0.0


class ResidentAnomalyPipeline(AnomalyPipelineBase):
    """Resident mode: no visitor_specific scope; per-scope engineering differs."""

    @property
    def anomaly_type(self) -> AnomalyType:
        return AnomalyType.RESIDENT

    async def engineer_scope_features(
        self,
        scope: AnalysisScope,
        raw_records: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, float]:
        return {
            "pipeline": "resident",
            "scope": scope.value,
            "stub": 0.0,
        }

    async def score_scope(
        self, scope: AnalysisScope, features: dict[str, float]
    ) -> float:
        return 0.0


def pipeline_for_type(anomaly_type: AnomalyType) -> AnomalyPipelineBase:
    if anomaly_type == AnomalyType.VISITOR:
        return VisitorAnomalyPipeline()
    if anomaly_type == AnomalyType.RESIDENT:
        return ResidentAnomalyPipeline()
    raise ValueError(f"Unsupported anomaly type: {anomaly_type}")
