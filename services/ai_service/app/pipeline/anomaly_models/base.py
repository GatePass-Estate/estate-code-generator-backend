"""Abstract base for scope-level anomaly detectors (K-means, DBSCAN, …)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.pipeline.anomaly_models.preprocess import ProcessedFeatureBlock


class AnomalyDetectorModel(ABC):
    """
    Contract: ``process`` builds tensors from raw feature dicts; ``predict``
    fits or applies the detector and returns a scalar anomaly score.
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """
        Short id for this detector (e.g. ``kmeans``), used in API transparency
        and ``run_models`` result keys.
        """

    @abstractmethod
    def process(
        self,
        focal_features: dict[str, float],
        historical_features: list[dict[str, float]],
    ) -> ProcessedFeatureBlock:
        """
        Turn raw feature dicts into a :class:`ProcessedFeatureBlock`.

        Implementations typically align keys, impute missing values, and scale
        so :meth:`predict` operates in a stable numeric space.
        """

    @abstractmethod
    def predict(self, data: ProcessedFeatureBlock) -> float:
        """
        Run the model and return an anomaly score in ``[0, 1]``.

        Higher values indicate stronger deviation from the historical cohort.
        """

    def invoke(self, data: ProcessedFeatureBlock) -> float:
        """Synonym for :meth:`predict` for streaming-style call sites."""
        return self.predict(data)
