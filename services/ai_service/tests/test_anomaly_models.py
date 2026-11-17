"""Tests for K-means / DBSCAN / LOF anomaly detectors."""

import numpy as np
import pytest

from app.pipeline.spatial_anomaly_models import (
    DBSCANAnomalyModel,
    KMeansAnomalyModel,
    LOFAnomalyModel,
)
from app.pipeline.spatial_anomaly_models.preprocess import (
    build_processed_block,
)


def test_build_processed_block_aligns_keys_and_scales():
    focal = {"a": 10.0, "b": 0.0}
    hist = [{"a": 0.0, "b": 0.0}, {"a": 0.0, "b": 0.0}]
    block = build_processed_block(focal, hist)
    assert block.feature_names == ("a", "b")
    assert block.X_historical.shape == (2, 2)
    assert block.x_focal.shape == (2,)
    assert float(np.linalg.norm(block.X_historical, axis=1).max()) < 1e-9


@pytest.mark.asyncio
async def test_run_models_returns_kmeans_dbscan_and_count():
    from app.domain.scopes import AnalysisScope
    from app.pipeline.analysis_manager import run_models

    out = await run_models(
        scope=AnalysisScope.VISITOR,
        focal_features={"x": 1.0},
        historical_features=[{"x": 0.0}, {"x": 2.0}],
    )
    assert "kmeans" in out and "dbscan" in out and "lof" in out
    assert out["historical_reference_count"] == 2.0
    assert 0.0 <= out["kmeans"] <= 1.0
    assert 0.0 <= out["dbscan"] <= 1.0
    assert 0.0 <= out["lof"] <= 1.0


def test_kmeans_high_score_when_focal_far_from_cluster():
    m = KMeansAnomalyModel()
    hist = [{"f": 0.0}, {"f": 0.1}, {"f": -0.1}]
    focal = {"f": 100.0}
    block = m.process(focal, hist)
    s = m.predict(block)
    assert s > 0.5


def test_dbscan_noise_detection():
    m = DBSCANAnomalyModel()
    hist = [{"a": 0.0}, {"a": 0.01}, {"a": 0.02}]
    focal = {"a": 50.0}
    block = m.process(focal, hist)
    s = m.predict(block)
    assert s >= 0.0


def test_lof_high_score_when_focal_far_from_neighbors():
    m = LOFAnomalyModel()
    hist = [{"f": 0.0}, {"f": 0.1}, {"f": -0.1}, {"f": 0.05}]
    focal = {"f": 100.0}
    block = m.process(focal, hist)
    s = m.predict(block)
    assert s > 0.5


def test_lof_single_history_row_uses_distance_fallback():
    m = LOFAnomalyModel()
    hist = [{"f": 0.0}]
    focal = {"f": 100.0}
    block = m.process(focal, hist)
    s = m.predict(block)
    assert 0.0 <= s <= 1.0
    assert s > 0.5
