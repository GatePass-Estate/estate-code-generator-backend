"""currency conversion to integer

Revision ID: ff55f753b8a4
Revises: e3f8d38f0643
Create Date: 2026-10-20 22:22:26.162661

Convert all monetary columns from Numeric(18,2) (major-unit decimals) to
BigInteger (smallest-currency-unit integers, e.g. kobo).  Existing data is
multiplied by 100 before the column type is altered.

Also converts monetary values inside the pricing_snapshot JSONB column on
payment_checkout_session.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "ff55f753b8a4"
down_revision: Union[str, None] = "e3f8d38f0643"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Top-level monetary keys inside pricing_snapshot that need * 100
_SNAPSHOT_MONEY_KEYS = [
    "price_per_seat",
    "ai_price_per_month",
    "monthly_subtotal",
    "subtotal",
    "vat_amount",
    "client_total",
    "administrative_fee",
    "sum_of_included_features",
    "old_price_per_seat",
    "new_price_per_seat",
    "tier_diff_per_seat",
    "old_ai_monthly",
    "new_ai_monthly",
    "prorated_charge",
    "daily_seat_rate",
    "period_seat_price",
    "ai_prorated_charge",
]


def upgrade() -> None:
    # ── 1. Multiply existing monetary data by 100 (while still Numeric) ──
    op.execute(
        "UPDATE core.feature_unit_price "
        "SET feature_unit_price = feature_unit_price * 100"
    )
    op.execute(
        "UPDATE core.payment_checkout_session " "SET amount = amount * 100"
    )
    op.execute("UPDATE core.payment_transaction " "SET amount = amount * 100")

    # ── 2. Alter column types to bigint ──
    op.execute(
        "ALTER TABLE core.feature_unit_price "
        "ALTER COLUMN feature_unit_price "
        "TYPE bigint USING feature_unit_price::bigint"
    )
    op.execute(
        "ALTER TABLE core.payment_checkout_session "
        "ALTER COLUMN amount "
        "TYPE bigint USING amount::bigint"
    )
    op.execute(
        "ALTER TABLE core.payment_transaction "
        "ALTER COLUMN amount "
        "TYPE bigint USING amount::bigint"
    )

    # ── 3. Convert pricing_snapshot JSONB monetary fields (* 100) ──
    # Top-level keys — single UPDATE using || merge
    _set_exprs = ", ".join(
        f"'{k}', to_jsonb(((pricing_snapshot->>'{k}')::numeric * 100)::bigint)"
        for k in _SNAPSHOT_MONEY_KEYS
    )
    _where_keys = ", ".join(f"'{k}'" for k in _SNAPSHOT_MONEY_KEYS)
    op.execute(
        f"UPDATE core.payment_checkout_session "
        f"SET pricing_snapshot = pricing_snapshot || jsonb_build_object({_set_exprs}) "
        f"WHERE pricing_snapshot ?| ARRAY[{_where_keys}]"
    )

    # Nested: line_items[].unit_price
    op.execute("""
        UPDATE core.payment_checkout_session
        SET pricing_snapshot = jsonb_set(
            pricing_snapshot,
            '{line_items}',
            (
                SELECT COALESCE(jsonb_agg(
                    CASE
                        WHEN elem ? 'unit_price' AND elem->>'unit_price' IS NOT NULL
                        THEN jsonb_set(
                            elem,
                            '{unit_price}',
                            to_jsonb(((elem->>'unit_price')::numeric * 100)::bigint)
                        )
                        ELSE elem
                    END
                    ORDER BY idx
                ), '[]'::jsonb)
                FROM jsonb_array_elements(
                    pricing_snapshot->'line_items'
                ) WITH ORDINALITY AS t(elem, idx)
            )
        )
        WHERE pricing_snapshot ? 'line_items'
          AND jsonb_typeof(pricing_snapshot->'line_items') = 'array'
          AND jsonb_array_length(pricing_snapshot->'line_items') > 0
    """)


def downgrade() -> None:
    # ── 1. Convert pricing_snapshot JSONB monetary fields (/ 100) ──
    # Nested: line_items[].unit_price
    op.execute("""
        UPDATE core.payment_checkout_session
        SET pricing_snapshot = jsonb_set(
            pricing_snapshot,
            '{line_items}',
            (
                SELECT COALESCE(jsonb_agg(
                    CASE
                        WHEN elem ? 'unit_price' AND elem->>'unit_price' IS NOT NULL
                        THEN jsonb_set(
                            elem,
                            '{unit_price}',
                            to_jsonb((elem->>'unit_price')::numeric / 100)
                        )
                        ELSE elem
                    END
                    ORDER BY idx
                ), '[]'::jsonb)
                FROM jsonb_array_elements(
                    pricing_snapshot->'line_items'
                ) WITH ORDINALITY AS t(elem, idx)
            )
        )
        WHERE pricing_snapshot ? 'line_items'
          AND jsonb_typeof(pricing_snapshot->'line_items') = 'array'
          AND jsonb_array_length(pricing_snapshot->'line_items') > 0
    """)

    # Top-level keys — single UPDATE using || merge
    _set_exprs = ", ".join(
        f"'{k}', to_jsonb((pricing_snapshot->>'{k}')::numeric / 100)"
        for k in _SNAPSHOT_MONEY_KEYS
    )
    _where_keys = ", ".join(f"'{k}'" for k in _SNAPSHOT_MONEY_KEYS)
    op.execute(
        f"UPDATE core.payment_checkout_session "
        f"SET pricing_snapshot = pricing_snapshot || jsonb_build_object({_set_exprs}) "
        f"WHERE pricing_snapshot ?| ARRAY[{_where_keys}]"
    )

    # ── 2. Alter column types back to numeric(18,2) ──
    op.execute(
        "ALTER TABLE core.feature_unit_price "
        "ALTER COLUMN feature_unit_price "
        "TYPE numeric(18,2) USING feature_unit_price::numeric(18,2)"
    )
    op.execute(
        "ALTER TABLE core.payment_checkout_session "
        "ALTER COLUMN amount "
        "TYPE numeric(18,2) USING amount::numeric(18,2)"
    )
    op.execute(
        "ALTER TABLE core.payment_transaction "
        "ALTER COLUMN amount "
        "TYPE numeric(18,2) USING amount::numeric(18,2)"
    )

    # ── 3. Divide data by 100 to restore major units ──
    op.execute(
        "UPDATE core.feature_unit_price "
        "SET feature_unit_price = feature_unit_price / 100"
    )
    op.execute(
        "UPDATE core.payment_checkout_session " "SET amount = amount / 100"
    )
    op.execute("UPDATE core.payment_transaction " "SET amount = amount / 100")
