"""Distance-to-centroid anomaly score from a K-means fit on history."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans

from app.core.config import settings
from app.pipeline.spatial_anomaly_models.base import AnomalyDetectorModel
from app.pipeline.spatial_anomaly_models.preprocess import (
    ProcessedFeatureBlock,
    build_processed_block,
)


class KMeansAnomalyModel(AnomalyDetectorModel):
    """
    Fit K-means on historical rows; score focal by normalized nearest-centroid
    distance relative to historical distances.
    """

    @property
    def model_id(self) -> str:
        """Return the literal ``kmeans`` key used in ``run_models`` output."""
        return "kmeans"

    def process(
        self,
        focal_features: dict[str, float],
        historical_features: list[dict[str, float]],
    ) -> ProcessedFeatureBlock:
        """Delegate to :func:`build_processed_block` (shared preprocessing)."""
        return build_processed_block(focal_features, historical_features)

    def predict(self, data: ProcessedFeatureBlock) -> float:
        """
        Fit K-means on historical rows and score the focal by distance ratio.

        Returns ``0.0`` when there is no history or no feature columns. Otherwise
        returns ``min`` distance from the focal to any centroid, divided by the
        ``SPATIAL_KMEANS_HIST_DISTANCE_PERCENTILE`` of historical min-centroid
        distances, clipped to ``[0, 1]``. Cluster count, random seed, and the
        reference percentile come from :mod:`app.core.config`.
        """
        X = data.X_historical
        n_hist, d = X.shape
        if n_hist < 1 or d < 1:
            return 0.0

        n_clusters = max(1, min(settings.SPATIAL_KMEANS_MAX_CLUSTERS, n_hist))
        km = KMeans(
            n_clusters=n_clusters,
            random_state=settings.SPATIAL_KMEANS_RANDOM_STATE,
            n_init="auto",
        )
        km.fit(X)
        focal_dist = float(km.transform(data.x_focal.reshape(1, -1)).min())
        hist_dists = km.transform(X).min(axis=1)
        ref = float(
            np.percentile(
                hist_dists, settings.SPATIAL_KMEANS_HIST_DISTANCE_PERCENTILE
            )
            + 1e-9
        )
        return float(np.clip(focal_dist / ref, 0.0, 1.0))
