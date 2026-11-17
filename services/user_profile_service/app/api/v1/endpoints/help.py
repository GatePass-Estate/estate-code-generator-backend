import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_feedback
from app.repositories.estate import EstateRepository
from app.schemas.help import FeedbackRequest
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/feedback", status_code=202)
async def send_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """
    Submit user feedback (suggestion or issue) to the GatePass team.

    Resolves the user's name, email, and estate name from the auth token,
    then forwards everything to the notification service which emails the
    GatePass team at info@gatepassng.com.
    """
    estate_repo = EstateRepository(ahttp_client)

    estate_name = "Unknown Estate"
    try:
        estate = await estate_repo.get_estate_by_id(
            str(current_user["estate_id"])
        )
        if estate and estate.name:
            estate_name = estate.name
    except Exception:
        logger.warning(
            "Could not fetch estate for user %s during feedback submission",
            current_user["id"],
        )

    payload = {
        "feedback_type": request.feedback_type,
        "user_name": (
            f"{current_user.get('first_name', '')} "
            f"{current_user.get('last_name', '')}"
        ).strip(),
        "user_email": current_user.get("email", ""),
        "estate_name": estate_name,
        "rating": request.rating,
        "liked": request.liked,
        "improvement": request.improvement,
        "description": request.description,
        "attachment_url": request.attachment_url,
    }

    background_tasks.add_task(fire_feedback, payload)
    return {"status": "accepted"}
