import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_notify, fire_notify_critical
from app.repositories.admin_management import AdminRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.schedule import (
    SCHEDULED_ESTATE_DEACTIVATIONS_KEY,
    SCHEDULED_USER_CLOSURES_KEY,
    ScheduleRepository as ScheduleRepo,
)
from app.repositories.user import UserRepository
from app.services.estate import EstateService
from app.services.user import UserService

logger = logging.getLogger(__name__)

router = APIRouter()

_internal_key_scheme = APIKeyHeader(name="X-Internal-Key", auto_error=False)


def _verify_internal_key(
    key: str = Depends(_internal_key_scheme),
) -> None:
    if not key or key != settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing internal API key",
        )


def _get_user_service(ahttp_client: AsyncHttpHandler) -> UserService:
    return UserService(
        UserRepository(ahttp_client),
        EstateRepository(ahttp_client),
        HouseholdRepository(ahttp_client),
        AdminRepository(ahttp_client),
    )


def _get_estate_service(ahttp_client: AsyncHttpHandler) -> EstateService:
    return EstateService(
        estate_repository=EstateRepository(ahttp_client),
        user_repository=UserRepository(ahttp_client),
    )


@router.post(
    "/cron/daily",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_verify_internal_key)],
)
async def run_daily_cron(
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """
    Process all deferred tasks that are due now or in the past.

    Handles:
    - scheduled_user_closures: permanently close user accounts
    - scheduled_estate_deactivations: deactivate estates

    Failures are logged individually and do not block remaining tasks.
    """
    user_service = _get_user_service(ahttp_client)
    estate_service = _get_estate_service(ahttp_client)
    schedule_repo = ScheduleRepo(ahttp_client)

    processed_users = 0
    failed_users = 0
    processed_estates = 0
    failed_estates = 0

    # ── User closures ────────────────────────────────────────────────────────
    due_users = await schedule_repo.get_due(SCHEDULED_USER_CLOSURES_KEY)
    for member in due_users:
        task: dict = {}
        try:
            task = json.loads(member)
            user_id = task["user_id"]

            # Capture estate_id before deletion for admin fan-out
            estate_id = None
            try:
                estate_id = await user_service.get_estate_id_by_user_id(
                    user_id
                )
            except Exception:
                pass

            await user_service.admin_close_account(
                user_id=user_id,
                actor_user_id=task["actor_user_id"],
                actor_role=task["actor_role"],
            )
            await schedule_repo.remove(SCHEDULED_USER_CLOSURES_KEY, member)
            background_tasks.add_task(
                fire_notify_critical,
                {
                    "type": "ACCOUNT_DEACTIVATED",
                    "title": "Your account has been closed",
                    "body": "Your GatePass account has been closed.",
                    "recipient_user_ids": [user_id],
                },
            )
            if estate_id:
                background_tasks.add_task(
                    fire_notify,
                    {
                        "type": "ACCOUNT_DEACTIVATED",
                        "title": "Account closed",
                        "body": ("An account in your estate has been closed."),
                        "fan_out": {
                            "estate_id": estate_id,
                            "roles": ["admin", "primary_admin"],
                        },
                    },
                )
            processed_users += 1
        except Exception:
            logger.exception(
                "Cron: failed to close account user_id=%s",
                task.get("user_id"),
            )
            failed_users += 1

    # ── Estate deactivations ─────────────────────────────────────────────────
    due_estates = await schedule_repo.get_due(
        SCHEDULED_ESTATE_DEACTIVATIONS_KEY
    )
    for member in due_estates:
        task = {}
        try:
            task = json.loads(member)
            estate_id = task["estate_id"]
            actor_user_id = task["actor_user_id"]

            await estate_service.deactivate_estate(estate_id, actor_user_id)
            await schedule_repo.remove(
                SCHEDULED_ESTATE_DEACTIVATIONS_KEY, member
            )

            community_label = "community"
            try:
                estate = await estate_service.get_estate(estate_id)
                community_label = {
                    "housing": "estate",
                    "corporate": "organisation",
                }.get(
                    estate.estate_type.value if estate.estate_type else "",
                    "community",
                )
            except Exception:
                pass

            background_tasks.add_task(
                fire_notify,
                {
                    "type": "ESTATE_DEACTIVATED",
                    "title": (f"{community_label.capitalize()} deactivated"),
                    "body": (
                        f"Your {community_label} has been deactivated"
                        " by the platform."
                    ),
                    "fan_out": {
                        "estate_id": estate_id,
                        "roles": ["admin", "primary_admin"],
                    },
                    "metadata": {"community_label": community_label},
                },
            )

            processed_estates += 1
        except Exception:
            logger.exception(
                "Cron: failed to deactivate estate estate_id=%s",
                task.get("estate_id"),
            )
            failed_estates += 1

    logger.info(
        "Daily cron completed users_processed=%s users_failed=%s "
        "estates_processed=%s estates_failed=%s",
        processed_users,
        failed_users,
        processed_estates,
        failed_estates,
    )
    return {
        "users_processed": processed_users,
        "users_failed": failed_users,
        "estates_processed": processed_estates,
        "estates_failed": failed_estates,
    }
