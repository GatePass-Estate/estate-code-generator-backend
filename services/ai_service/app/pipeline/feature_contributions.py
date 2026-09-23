"""
Per-feature weights and contributions for spatial anomaly transparency.

These values explain *why* a scope scored high in UI spider plots; they do
**not** feed K-means/DBSCAN/LOF inputs. Priors come from
:mod:`app.core.ensemble_config`; deviation comes from focal z-scores vs history.
"""

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

    Algorithm:

    1. For each active focal feature, compute absolute z-score vs stored history
       (0 when no history or zero variance).
    2. Normalise z-scores to ``dev_weights`` (uniform split when all zero).
    3. Multiply each ``dev_weight`` by :func:`feature_base_weight` prior.
    4. Renormalise to effective weights summing to 1.
    5. ``contribution = effective_weight × scope_score``.

    Returns:
        List of dicts with ``feature_name``, ``value``, ``weight``,
        ``contribution`` (keys align with :class:`FeatureContribution`).
    """
    if not focal_features:
        return []

    names = sorted(focal_features.keys())
    # Step 1 — absolute z-scores per feature vs historical cohort.
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

    # Step 2 — normalise deviations; uniform when focal matches history mean.
    z_sum = sum(abs_z)
    if z_sum < 1e-9:
        dev_weights = [1.0 / len(names)] * len(names)
    else:
        dev_weights = [z / z_sum for z in abs_z]

    # Steps 3–4 — blend configured priors with deviation weights.
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
