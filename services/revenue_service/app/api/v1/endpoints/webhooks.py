"""Payment provider webhook stubs."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/paystack")
async def paystack_webhook():
    """Stub: handle Paystack webhook events (Phase 2)."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "status": "stubbed",
            "message": "Paystack webhooks not implemented yet",
        },
    )
