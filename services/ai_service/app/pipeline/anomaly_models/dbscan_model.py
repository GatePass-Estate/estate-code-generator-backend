"""DBSCAN noise label on focal vs cohort (history + focal) in scaled space."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import pairwise_distances

from app.pipeline.anomaly_models.base import AnomalyDetectorModel
from app.pipeline.anomaly_models.preprocess import (
    ProcessedFeatureBlock,
    build_processed_block,
)


class DBSCANAnomalyModel(AnomalyDetectorModel):
    """
    Fit DBSCAN on stacked historical + focal rows; focal at noise (-1) ⇒ high
    score, otherwise a small baseline from distance to the noise subset.
    """

    @property
    def model_id(self) -> str:
        """Return the literal ``dbscan`` key used in ``run_models`` output."""
        return "dbscan"

    def process(
        self,
        focal_features: dict[str, float],
        historical_features: list[dict[str, float]],
    ) -> ProcessedFeatureBlock:
        """Delegate to :func:`build_processed_block` (shared preprocessing)."""
        return build_processed_block(focal_features, historical_features)

    def predict(self, data: ProcessedFeatureBlock) -> float:
        """
        Cluster history plus focal with DBSCAN; derive an anomaly score.

        Returns ``0.0`` when there is no history or no feature columns. Noise
        label ``-1`` on the focal yields ``1.0``; in-cluster focal yields a low
        baseline or a distance-based blend when historical noise exists.
        """
        X = data.X_historical
        n_hist, d = X.shape
        if n_hist < 1 or d < 1:
            return 0.0

        X_all = np.vstack([X, data.x_focal.reshape(1, -1)])
        if n_hist >= 2:
            pd = pairwise_distances(X)
            tri_i, tri_j = np.triu_indices(n_hist, k=1)
            pair = pd[tri_i, tri_j]
            eps = float(np.median(pair) + 1e-9) if pair.size else 0.75
        else:
            eps = 0.75
        min_samples = max(2, min(5, n_hist))
        labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(X_all)
        if int(labels[-1]) == -1:
            return 1.0
        noise_mask = labels[:-1] == -1
        if not np.any(noise_mask):
            return 0.05
        dists = np.linalg.norm(X - data.x_focal.reshape(1, -1), axis=1)
        near_noise = float(np.min(dists[noise_mask]))
        blend = 0.15 + 0.85 * near_noise / (near_noise + 1.0)
        return float(np.clip(blend, 0.0, 1.0))
