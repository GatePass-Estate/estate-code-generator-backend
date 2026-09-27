"""add marketplace catalog copy

Revision ID: o8p9q0r1s2t
Revises: n7o8p9q0r1s2
Create Date: 2026-09-27 11:20:00.000000

Tier benefits on each AI feature, plus product features and data insight
on each parent marketplace product. Search responses return the columns.
"""

from typing import Any, Sequence, Union
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "o8p9q0r1s2t"
down_revision: Union[str, None] = "n7o8p9q0r1s2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIER_BENEFITS: dict[str, list[str]] = {
    "access_anomaly_detection_tier_1": [
        "Runs anomaly scans in the background whenever someone validates an access code at the estate gate.",
        "Alerts admins when a visit looks suspicious compared with the access patterns this estate usually sees.",
        "Lists every analysed access case in one review view so admins can inspect what the model decided.",
        "Shows the factors behind each anomaly score so admins can see why that visit was flagged.",
        "Compares the current visit with this estate's stored normal pattern before marking the access as unusual.",
    ],
    "access_anomaly_detection_tier_2": [
        "Turns each analysed access case into a readable report that admins can review without interpreting raw model scores.",
        "Summarises why a particular visit scored as unusual and which parts of the access pattern drove that result.",
        "Highlights the factors that contributed most to the anomaly score for that visitor, resident, or security validation.",
        "Lets admins review a flagged case in plain language instead of reading the underlying detector scores themselves.",
        "Uses GatePass in-house agents to write the case report, without sending the narrative to a third-party model.",
    ],
    "access_anomaly_detection_tier_3": [
        "Writes a deeper narrative for each analysed access case so admins get more context than the in-house report alone.",
        "Explains unusual gate access in operational language that security and estate admins can act on directly.",
        "Adds context beyond the in-house case report by describing how the visit differs from this estate's normal pattern.",
        "Helps admins brief security staff on a flagged visit with a written account of what looked unusual and why.",
        "Uses third-party agents to produce the case narrative when the estate has the advanced review tier enabled.",
    ],
    "incident_report_summary_tier_1": [
        "Collects estate incident reports into one review view so admins can inspect filings for the selected date window.",
        "Ranks incident categories and shows the time of day each category most often occurs across the selected reports.",
        "Shows how reports split between resident-side roles and security, excluding guest and root accounts from that mix.",
        "Surfaces trends in the selected date window, including which categories dominate and when those incidents tend to happen.",
        "Keeps the original report title and narrative next to the analysis so admins can check the source text.",
    ],
    "incident_report_summary_tier_2": [
        "Groups incident reports into themes using in-house topic modelling so repeating issues stand out across the cohort.",
        "Writes a short insight from the category mix, peak times, and reporter split without calling a third-party language model.",
        "Uncovers issues that repeat across many incident reports in the window, even when each individual filing looks small.",
        "Summarises the selected window so admins can grasp the main incident patterns without reading every narrative in full.",
        "Uses GatePass in-house agents to produce the theme summary, keeping that analysis inside the estate's own service.",
    ],
    "incident_report_summary_tier_3": [
        "Generates a longer narrative across the incident cohort so leadership can read one account of what happened in the window.",
        "Calls out repeating categories and emerging risks that show up when the reports are read together rather than one by one.",
        "Uses third-party agents for a deeper read of the report titles, categories, and narratives in the selected date window.",
        "Helps admins brief leadership on incident trends with a written summary of the categories, timing, and reporter mix.",
        "Builds on the same incident reports and category analysis as the other tiers, then adds the third-party narrative on top.",
    ],
}

_PARENTS: tuple[dict[str, Any], ...] = (
    {
        "name": "Access Anomaly Detection",
        "tiers": (
            "access_anomaly_detection_tier_1",
            "access_anomaly_detection_tier_2",
            "access_anomaly_detection_tier_3",
        ),
        "product_features": [
            "Background anomaly scans score each gate validation against the patterns this estate has already recorded as normal.",
            "Each visit is compared with visitor, resident, security, and estate-wide history before the service decides whether it looks unusual.",
            "Admins can open a flagged case and read an optional written report from in-house or third-party agents.",
        ],
        "data": [
            "Visitor full name, gender, and stated relationship to the resident who issued or owns the access record.",
            "The resident user identifier and the security user identifier for the person who validated the access code at the gate.",
            "The clock time of the visit, including hour, day of week, weekend flag, and whether the visit falls at night.",
            "How often that visitor, resident, and validating guard appear at the gate, and the time between their recent visits.",
            "Estate-wide access history stored from earlier non-anomalous visits, used as the baseline for what normal looks like here.",
        ],
    },
    {
        "name": "Incident Report Insights",
        "tiers": (
            "incident_report_summary_tier_1",
            "incident_report_summary_tier_2",
            "incident_report_summary_tier_3",
        ),
        "product_features": [
            "Incident reports for the estate are collected into one review view with filters for category, reporter type, and dates.",
            "The overview ranks categories, shows when incidents tend to occur, and splits reports between resident-side roles and security.",
            "In-house topic modelling finds repeating themes, and an optional third-party narrative summarises the same set of reports.",
        ],
        "data": [
            "Incident title, free-text narrative, and custom category wording, which can include names or other personal details written by the reporter.",
            "The fixed incident categories the reporter selected on the form, such as theft, noise, maintenance, or unauthorized access.",
            "The timestamp when the incident occurred and the timestamp when the report was created and stored for the estate.",
            "The reporter's user identifier, used only to resolve whether that person is a resident-side role or security staff.",
            "The estate identifier the report belongs to, so analysis stays inside that estate and is not mixed with other communities.",
        ],
    },
)


def _execute(sql: str, params: dict[str, Any] | None = None) -> Any:
    """Run a SQL statement on the current Alembic connection."""
    return op.get_bind().execute(sa.text(sql), params or {})


def upgrade() -> None:
    """Add the JSONB columns and fill them for the seeded catalog."""
    op.add_column(
        "ai_feature",
        sa.Column(
            "tier_benefits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="core",
    )
    op.add_column(
        "ai_marketplace_feature",
        sa.Column(
            "tier_benefits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="core",
    )
    op.add_column(
        "ai_marketplace_feature",
        sa.Column(
            "product_features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="core",
    )
    op.add_column(
        "ai_marketplace_feature",
        sa.Column(
            "data_insight",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text('\'{"legal": [], "data": []}\'::jsonb'),
            nullable=False,
        ),
        schema="core",
    )

    for feature_key, benefits in _TIER_BENEFITS.items():
        result = _execute(
            "UPDATE core.ai_feature"
            " SET tier_benefits = CAST(:benefits AS jsonb)"
            " WHERE feature_key = :feature_key"
            " AND COALESCE(is_deleted, false) = false",
            {"benefits": json.dumps(benefits), "feature_key": feature_key},
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected one ai_feature row for {feature_key},"
                f" updated {result.rowcount}"
            )

    for parent in _PARENTS:
        tier_benefits = [
            {
                "tier": f"tier_{index}",
                "benefits": _TIER_BENEFITS[feature_key],
            }
            for index, feature_key in enumerate(parent["tiers"], start=1)
        ]
        result = _execute(
            "UPDATE core.ai_marketplace_feature"
            " SET tier_benefits = CAST(:tier_benefits AS jsonb),"
            " product_features = CAST(:product_features AS jsonb),"
            " data_insight = CAST(:data_insight AS jsonb)"
            " WHERE name = :name"
            " AND COALESCE(is_deleted, false) = false",
            {
                "tier_benefits": json.dumps(tier_benefits),
                "product_features": json.dumps(parent["product_features"]),
                "data_insight": json.dumps(
                    {"legal": [], "data": parent["data"]}
                ),
                "name": parent["name"],
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(
                f"Expected one marketplace row named {parent['name']},"
                f" updated {result.rowcount}"
            )


def downgrade() -> None:
    """Drop the catalog copy columns."""
    op.drop_column("ai_marketplace_feature", "data_insight", schema="core")
    op.drop_column("ai_marketplace_feature", "product_features", schema="core")
    op.drop_column("ai_marketplace_feature", "tier_benefits", schema="core")
    op.drop_column("ai_feature", "tier_benefits", schema="core")
