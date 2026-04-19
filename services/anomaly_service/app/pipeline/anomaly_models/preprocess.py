"""Align heterogeneous feature dicts into fixed-column matrices for sklearn."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class ProcessedFeatureBlock:
    """Historical matrix and focal vector in a shared scaled basis."""

    feature_names: tuple[str, ...]
    X_historical: np.ndarray  # (n_hist, n_features), may be 0 rows
    x_focal: np.ndarray  # (n_features,)


def build_processed_block(
    focal_features: dict[str, float],
    historical_features: list[dict[str, float]],
) -> ProcessedFeatureBlock:
    """
    Sort union of keys, impute missing keys with 0, ``StandardScaler`` on rows.

    Scaler is fit on historical rows only; focal uses the same transform.
    With no history, fit on the focal row alone (reference = self).

    Args:
        focal_features: Engineered feature dict for the current validation.
        historical_features: Prior validations in the same scope (may be empty).

    Returns:
        Frozen :class:`ProcessedFeatureBlock` with aligned scaled matrices.
    """
    keys: set[str] = set(focal_features)
    for row in historical_features:
        keys |= set(row)
    names = tuple(sorted(keys))
    if not names:
        empty = np.zeros((0, 0), dtype=np.float64)
        return ProcessedFeatureBlock((), empty, np.zeros(0))

    def as_vector(row: dict[str, float]) -> np.ndarray:
        """Dense row aligned to ``names``; missing keys become ``0.0``."""
        return np.array(
            [float(row.get(k, 0.0)) for k in names], dtype=np.float64
        )

    x_focal = as_vector(focal_features)
    if historical_features:
        X_hist = np.vstack([as_vector(h) for h in historical_features])
    else:
        X_hist = np.zeros((0, len(names)), dtype=np.float64)

    scaler = StandardScaler()
    if X_hist.shape[0] > 0:
        scaler.fit(X_hist)
        X_scaled = scaler.transform(X_hist)
    else:
        scaler.fit(x_focal.reshape(1, -1))
        X_scaled = X_hist
    xf_scaled = scaler.transform(x_focal.reshape(1, -1)).ravel()

    return ProcessedFeatureBlock(names, X_scaled.astype(np.float64), xf_scaled)
