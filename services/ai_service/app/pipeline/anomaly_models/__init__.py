"""
Concrete anomaly detectors (K-means, DBSCAN, LOF) and preprocessing helpers.

:class:`AnomalyDetectorModel` is the extension point for additional algorithms.
"""

from app.pipeline.anomaly_models.base import AnomalyDetectorModel
from app.pipeline.anomaly_models.dbscan_model import DBSCANAnomalyModel
from app.pipeline.anomaly_models.kmeans_model import KMeansAnomalyModel
from app.pipeline.anomaly_models.lof_model import LOFAnomalyModel
from app.pipeline.anomaly_models.preprocess import ProcessedFeatureBlock

__all__ = [
    "AnomalyDetectorModel",
    "DBSCANAnomalyModel",
    "KMeansAnomalyModel",
    "LOFAnomalyModel",
    "ProcessedFeatureBlock",
]
