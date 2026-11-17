"""search indexes

Revision ID: c8d4e2a91b70
Revises: be313a279c8c
Create Date: 2026-11-14 11:16:00.000000

Indexes for repository search, join, and sort predicates that were
scanning unindexed columns. Expression indexes use lower(column) so they
match the case-insensitive equality filters. Trigram indexes serve
leading-wildcard ILIKE on names and emails.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c8d4e2a91b70"
down_revision: Union[str, None] = "be313a279c8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (index name, CREATE INDEX body after the name)
_INDEXES: tuple[tuple[str, str], ...] = (
    # Access codes and logs
    (
        "ix_core_accesscode_hashed_code_lower",
        "ON core.accesscode (lower(hashed_code)) " "WHERE is_deleted = false",
    ),
    (
        "ix_core_visitorlog_hashed_code_lower",
        "ON core.visitorlog (lower(hashed_code)) " "WHERE is_deleted = false",
    ),
    (
        "ix_core_residentlog_hashed_code_lower",
        "ON core.residentlog (lower(hashed_code)) " "WHERE is_deleted = false",
    ),
    (
        "ix_core_accesscode_estate_created",
        "ON core.accesscode (estate_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_accesscode_user_created",
        "ON core.accesscode (user_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_visitorlog_estate_created",
        "ON core.visitorlog (estate_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_visitorlog_user_created",
        "ON core.visitorlog (user_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_residentlog_estate_access_time",
        "ON core.residentlog (estate_id, access_time DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_residentlog_user_access_time",
        "ON core.residentlog (user_id, access_time DESC) "
        "WHERE is_deleted = false",
    ),
    # Prediction joins
    (
        "ix_core_predictionresult_visitor_log_id",
        "ON core.predictionresult (visitor_log_id) "
        "WHERE is_deleted = false AND visitor_log_id IS NOT NULL",
    ),
    (
        "ix_core_predictionresult_resident_log_id",
        "ON core.predictionresult (resident_log_id) "
        "WHERE is_deleted = false AND resident_log_id IS NOT NULL",
    ),
    (
        "ix_core_predictionresult_created_at",
        "ON core.predictionresult (created_at DESC) "
        "WHERE is_deleted = false",
    ),
    # Users and profile lists
    (
        "ix_core_users_email_trgm",
        "ON core.users USING gin ((email::text) gin_trgm_ops)",
    ),
    (
        "ix_core_users_first_name_trgm",
        "ON core.users USING gin ((first_name::text) gin_trgm_ops)",
    ),
    (
        "ix_core_users_last_name_trgm",
        "ON core.users USING gin ((last_name::text) gin_trgm_ops)",
    ),
    (
        "ix_core_users_estate_created",
        "ON core.users (estate_id, created_at DESC) "
        "WHERE is_deleted = false AND estate_id IS NOT NULL",
    ),
    (
        "ix_core_users_household_id",
        "ON core.users (household_id) "
        "WHERE is_deleted = false AND household_id IS NOT NULL",
    ),
    (
        "ix_core_users_phone_number_lower",
        "ON core.users (lower(phone_number)) "
        "WHERE is_deleted = false AND phone_number IS NOT NULL",
    ),
    (
        "ix_core_device_tokens_user_active",
        "ON core.device_tokens (user_id) "
        "WHERE is_deleted = false AND is_active = true",
    ),
    (
        "ix_core_totp_recovery_codes_user_id",
        "ON core.totp_recovery_codes (user_id) WHERE is_deleted = false",
    ),
    (
        "ix_core_guests_resident_created",
        "ON core.guests (resident_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_guests_guest_name_lower",
        "ON core.guests (lower(guest_name)) WHERE is_deleted = false",
    ),
    (
        "ix_core_requests_estate_status_created",
        "ON core.requests (estate_id, status, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_requests_resident_created",
        "ON core.requests (resident_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_broadcasts_estate_status_created",
        "ON core.broadcasts (estate_id, status, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_broadcasts_audience",
        "ON core.broadcasts USING gin (audience)",
    ),
    (
        "ix_core_admin_management_estate_primary",
        "ON core.admin_management (estate_id, is_primary) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_admin_management_user_id",
        "ON core.admin_management (user_id) WHERE is_deleted = false",
    ),
    (
        "ix_core_resident_departure_estate_created",
        "ON core.resident_departure_log (estate_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_resident_departure_user_id",
        "ON core.resident_departure_log (user_id) " "WHERE is_deleted = false",
    ),
    (
        "ix_core_household_head_user_id",
        "ON core.household (head_user_id) "
        "WHERE is_deleted = false AND head_user_id IS NOT NULL",
    ),
    (
        "ix_core_household_name_trgm",
        "ON core.household USING gin ((name::text) gin_trgm_ops)",
    ),
    (
        "ix_core_estates_primary_admin_id",
        "ON core.estates (primary_admin_id) "
        "WHERE is_deleted = false AND primary_admin_id IS NOT NULL",
    ),
    (
        "ix_core_estates_name_trgm",
        "ON core.estates USING gin ((name::text) gin_trgm_ops)",
    ),
    (
        "ix_core_estates_location_trgm",
        "ON core.estates USING gin ((location::text) gin_trgm_ops)",
    ),
    (
        "ix_core_estates_city_trgm",
        "ON core.estates USING gin ((city::text) gin_trgm_ops)",
    ),
    (
        "ix_core_estates_lga_trgm",
        "ON core.estates USING gin ((lga::text) gin_trgm_ops)",
    ),
    (
        "ix_core_estates_state_trgm",
        "ON core.estates USING gin ((state::text) gin_trgm_ops)",
    ),
    (
        "ix_core_estates_country_trgm",
        "ON core.estates USING gin ((country::text) gin_trgm_ops)",
    ),
    (
        "ix_core_estates_postal_code_trgm",
        "ON core.estates USING gin ((postal_code::text) gin_trgm_ops)",
    ),
    (
        "ix_core_incidentreport_estate_created",
        "ON core.incidentreport (estate_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_incidentreport_category",
        "ON core.incidentreport USING gin (category)",
    ),
    # Payments and subscriptions
    (
        "ix_core_estate_sub_paystack_sub_code",
        "ON core.estate_subscription (lower(paystack_subscription_code)) "
        "WHERE is_deleted = false "
        "AND paystack_subscription_code IS NOT NULL",
    ),
    (
        "ix_core_estate_sub_paystack_cust_code",
        "ON core.estate_subscription (lower(paystack_customer_code)) "
        "WHERE is_deleted = false AND paystack_customer_code IS NOT NULL",
    ),
    (
        "ix_core_estate_subscription_status_period",
        "ON core.estate_subscription (status, period_end) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_estate_subscription_estate_id",
        "ON core.estate_subscription (estate_id) WHERE is_deleted = false",
    ),
    (
        "ix_core_estate_ai_paystack_sub_code",
        "ON core.estate_ai_feature (lower(paystack_subscription_code)) "
        "WHERE is_deleted = false "
        "AND paystack_subscription_code IS NOT NULL",
    ),
    (
        "ix_core_estate_ai_feature_status_expires",
        "ON core.estate_ai_feature (status, expires_at) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_checkout_paystack_reference_lower",
        "ON core.payment_checkout_session (lower(paystack_reference)) "
        "WHERE is_deleted = false AND paystack_reference IS NOT NULL",
    ),
    (
        "ix_core_checkout_estate_created",
        "ON core.payment_checkout_session (estate_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_payment_tx_provider_ref_lower",
        "ON core.payment_transaction (lower(provider_reference)) "
        "WHERE is_deleted = false AND provider_reference IS NOT NULL",
    ),
    (
        "ix_core_payment_tx_estate_created",
        "ON core.payment_transaction (estate_id, created_at DESC) "
        "WHERE is_deleted = false",
    ),
    (
        "ix_core_payment_tx_checkout_session",
        "ON core.payment_transaction (checkout_session_id) "
        "WHERE is_deleted = false AND checkout_session_id IS NOT NULL",
    ),
)


def upgrade() -> None:
    """Add search indexes. pg_trgm backs the ILIKE indexes."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, body in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} {body}")


def downgrade() -> None:
    """Drop the search indexes. Leaves pg_trgm installed."""
    for name, _body in reversed(_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS core.{name}")
