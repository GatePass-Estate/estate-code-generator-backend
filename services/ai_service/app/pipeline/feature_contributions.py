"""Per-feature weights and contributions for spatial anomaly transparency."""

from __future__ import annotations

import math

from app.core.ensemble_config import feature_base_weight
from app.domain.scopes import AnalysisScope


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mu = sum(values) / len(values)
    if len(values) < 2:
        return mu, 0.0
    var = sum((v - mu) ** 2 for v in values) / len(values)
    return mu, math.sqrt(var)


def compute_feature_contributions(
    scope: AnalysisScope,
    focal_features: dict[str, float],
    historical_features: list[dict[str, float]],
    scope_score: float,
) -> list[dict[str, float | str | None]]:
    """
    Derive feature ``weight`` and ``contribution`` for transparency payloads.

    ``weight`` combines a configured feature prior with normalized absolute
    z-score vs historical cohort (uniform when no history). ``contribution`` is
    ``weight * scope_score``.

    Returns:
        List of dicts with ``feature_name``, ``value``, ``weight``,
        ``contribution`` (keys align with :class:`FeatureContribution`).
    """
    if not focal_features:
        return []

    names = sorted(focal_features.keys())
    abs_z: list[float] = []
    for name in names:
        focal_val = float(focal_features[name])
        hist_vals = [
            float(row[name])
            for row in historical_features
            if name in row and row[name] is not None
        ]
        if not hist_vals:
            abs_z.append(0.0)
            continue
        mu, sigma = _mean_std(hist_vals)
        if sigma < 1e-9:
            abs_z.append(0.0 if abs(focal_val - mu) < 1e-9 else 1.0)
        else:
            abs_z.append(abs((focal_val - mu) / sigma))

    z_sum = sum(abs_z)
    if z_sum < 1e-9:
        dev_weights = [1.0 / len(names)] * len(names)
    else:
        dev_weights = [z / z_sum for z in abs_z]

    combined = [
        feature_base_weight(scope, name) * dev
        for name, dev in zip(names, dev_weights)
    ]
    combined_sum = sum(combined) or 1.0
    effective = [c / combined_sum for c in combined]

    out: list[dict[str, float | str | None]] = []
    for name, eff in zip(names, effective):
        out.append(
            {
                "feature_name": name,
                "value": float(focal_features[name]),
                "weight": round(float(eff), 6),
                "contribution": round(float(eff * scope_score), 6),
            }
        )
    return out
