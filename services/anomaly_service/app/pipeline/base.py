"""
ABC for per-scope analysis. Subclasses override feature engineering / thresholds.

Design reference: each scope inherits from a base and overrides methods where semantics differ.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.scopes import AnalysisScope


class ScopeAnalysisBase(ABC):
    """Base class for visitor / resident / security / estate-wide pipelines."""

    scope: AnalysisScope

    def __init__(self, scope: AnalysisScope) -> None:
        self.scope = scope

    @abstractmethod
    def required_feature_keys(self) -> list[str]:
        """Which engineered features this scope participates in (config-driven later)."""

    @abstractmethod
    async def engineer_features(
        self, raw_records: list[dict[str, Any]], context: dict[str, Any]
    ) -> dict[str, float]:
        """Return a flat feature vector for the model ensemble (stub returns zeros)."""

    @abstractmethod
    async def score(self, features: dict[str, float]) -> float:
        """Single-scope anomaly score in [0, 1] (stub)."""


class StubScopeAnalysis(ScopeAnalysisBase):
    """Placeholder until K-means / DBSCAN / LFOA ensemble exists."""

    def required_feature_keys(self) -> list[str]:
        return []

    async def engineer_features(
        self, raw_records: list[dict[str, Any]], context: dict[str, Any]
    ) -> dict[str, float]:
        return {"stub_feature": 0.0}

    async def score(self, features: dict[str, float]) -> float:
        return 0.0
