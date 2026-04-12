"""Natural language / structured explanation of scores (stub)."""


def explain(
    final_score: float,
    scope_scores: dict[str, float],
    model_outputs: dict[str, float],
) -> str:
    parts = [
        f"final_score={final_score:.4f}",
        f"scopes={scope_scores}",
        f"models={model_outputs}",
    ]
    return "Draft anomaly explanation — " + "; ".join(parts)
