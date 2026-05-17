"""Human-readable and structured transparency for anomaly scores."""


def explain(
    final_score: float,
    scope_scores: dict[str, float],
    model_outputs: dict[str, float],
) -> str:
    """Build a short human-readable summary line for the analysis response."""
    parts = [
        f"final_score={final_score:.4f}",
        f"scopes={scope_scores}",
        f"models={model_outputs}",
    ]
    return "Draft anomaly explanation — " + "; ".join(parts)
