"""Tests for spatial analyze payload serialization helpers."""

from app.pipeline.spatial_anomaly_payload import round_payload_floats


def test_round_payload_floats_recurses_nested_dicts_and_lists():
    raw = {
        "final_score": 0.447123456,
        "per_scope_scores": {
            "temporal": 0.033333,
            "visitor_specific": 0.540001,
        },
        "transparency": {
            "scopes": [
                {
                    "score": 0.606789,
                    "feature_contributions": [
                        {
                            "value": 22.4567,
                            "weight": 0.333333,
                            "contribution": 0.202020,
                        }
                    ],
                    "thresholds": {"history_confidence": 0.200001},
                    "model_outputs": {"kmeans": 0.512345},
                }
            ],
            "scope_weights": [
                {"base_weight": 0.3, "effective_weight": 0.0400001}
            ],
            "detector_weights": {"kmeans": 0.35},
        },
        "is_anomalous": False,
        "matched_count": 7,
    }
    rounded = round_payload_floats(raw)
    assert rounded["final_score"] == 0.45
    assert rounded["per_scope_scores"]["temporal"] == 0.03
    assert rounded["transparency"]["scopes"][0]["score"] == 0.61
    assert (
        rounded["transparency"]["scopes"][0]["feature_contributions"][0][
            "value"
        ]
        == 22.46
    )
    assert (
        rounded["transparency"]["scopes"][0]["model_outputs"]["kmeans"] == 0.51
    )
    assert rounded["is_anomalous"] is False
    assert rounded["matched_count"] == 7
