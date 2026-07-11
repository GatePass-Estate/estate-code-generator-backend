"""Local Outlier Factor (LOF) anomaly score on history + focal in scaled space."""

from __future__ import annotations

import numpy as np
from sklearn.neighbors import LocalOutlierFactor

from app.pipeline.anomaly_models.base import AnomalyDetectorModel
from app.pipeline.anomaly_models.preprocess import (
    ProcessedFeatureBlock,
    build_processed_block,
)


class LOFAnomalyModel(AnomalyDetectorModel):
    """
    Fit LOF on historical rows (``novelty=True``), then score the focal visit.

    LOF compares each point's local density to that of its k-nearest neighbours;
    outliers are points substantially sparser than their neighbours (see sklearn
    ``LocalOutlierFactor`` and standard LOF tutorials). A focal label ``-1``
    yields a high score; inlier focals get a low score from ``decision_function``
    relative to the historical cohort.
    """

    @property
    def model_id(self) -> str:
        """Return the literal ``lof`` key used in ``run_models`` output."""
        return "lof"

    def process(
        self,
        focal_features: dict[str, float],
        historical_features: list[dict[str, float]],
    ) -> ProcessedFeatureBlock:
        """Delegate to :func:`build_processed_block` (shared preprocessing)."""
        return build_processed_block(focal_features, historical_features)

    def predict(self, data: ProcessedFeatureBlock) -> float:
        """
        Score the focal row with LOF against the historical cohort.

        Returns ``0.0`` when there is no history or no feature columns. A focal
        outlier label ``-1`` (negative ``decision_function``) yields ``1.0``;
        inlier focals get a low baseline or a mild uplift from decision scores.
        """
        X = data.X_historical
        n_hist, d = X.shape
        if n_hist < 1 or d < 1:
            return 0.0

        x_focal = data.x_focal.reshape(1, -1)

        # sklearn requires n_neighbors < n_samples_fit; need >= 2 history rows.
        if n_hist < 2:
            dist = float(np.linalg.norm(X[0] - x_focal))
            return float(np.clip(dist / (dist + 1.0), 0.0, 1.0))

        n_neighbors = max(1, min(20, n_hist - 1))
        lof = LocalOutlierFactor(
            n_neighbors=n_neighbors,
            contamination="auto",
            novelty=True,
        )
        lof.fit(X)
        if int(lof.predict(x_focal)[0]) == -1:
            return 1.0

        focal_dec = float(lof.decision_function(x_focal)[0])
        if focal_dec < 0:
            return 1.0

        hist_dec = lof.decision_function(X)
        hi = float(np.max(hist_dec))
        lo = float(np.min(hist_dec))
        span = hi - lo + 1e-9
        relative = (hi - focal_dec) / span
        return float(np.clip(0.05 + 0.45 * relative, 0.05, 0.5))
