"""Ensemble of per-model scores (K-means, DBSCAN, LFOA) — stub."""


async def ensemble_score(per_scope_scores: list[float]) -> float:
    if not per_scope_scores:
        return 0.0
    return sum(per_scope_scores) / len(per_scope_scores)


async def run_models(features: dict[str, float]) -> dict[str, float]:
    """Placeholder for K-means / DBSCAN / LFOA outputs."""
    return {"kmeans": 0.0, "dbscan": 0.0, "lfoa": 0.0}
