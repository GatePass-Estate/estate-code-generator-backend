"""Shared RBAC and membership checks for GatePass services."""

from gatepass_rbac.documents import can_download, can_upload, can_view
from gatepass_rbac.identity import estate_id, is_owner, same_estate, user_id
from gatepass_rbac.logs import can_view_logs, resolve_estate_log_scope
from gatepass_rbac.membership import (
    require_estate_membership,
    require_owner,
    require_owner_or_roles,
    require_same_estate,
)
from gatepass_rbac.permissions import check_permission, get_role_permissions
from gatepass_rbac.roles import (
    ADMIN_ROLES,
    ROLE_RANK,
    can_act_on_role,
    check_status,
    deny_roles,
    is_admin,
    require_admin,
    require_higher_rank,
    require_roles,
)

__all__ = [
    "ADMIN_ROLES",
    "ROLE_RANK",
    "can_act_on_role",
    "can_download",
    "can_upload",
    "can_view",
    "can_view_logs",
    "check_permission",
    "check_status",
    "deny_roles",
    "estate_id",
    "get_role_permissions",
    "is_admin",
    "is_owner",
    "require_admin",
    "require_estate_membership",
    "require_higher_rank",
    "require_owner",
    "require_owner_or_roles",
    "require_roles",
    "require_same_estate",
    "resolve_estate_log_scope",
    "same_estate",
    "user_id",
]
