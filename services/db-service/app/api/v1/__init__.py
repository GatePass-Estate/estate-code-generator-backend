from fastapi import APIRouter

from app.api.v1.endpoints.code_service.access_code import (
    router as accesscode_router,
)
from app.api.v1.endpoints.code_service.visitor_log import (
    router as visitorlog_router,
)

from app.api.v1.endpoints.user_profile.users import router as users_router

from app.api.v1.endpoints.user_profile.estates import router as estates_router

from app.api.v1.endpoints.user_profile.role_permission import (
    router as rolepermission_router,
)

from app.api.v1.endpoints.user_profile.resident_departure_log import (
    router as residentdeparturelog_router,
)

from app.api.v1.endpoints.user_profile.household import (
    router as household_router,
)

from app.api.v1.endpoints.user_profile.admin_management import (
    router as adminmanagement_router,
)

from app.api.v1.endpoints.user_profile.guests import (
    router as guests_router,
)

from app.api.v1.endpoints.user_profile.broadcasts import (
    router as broadcasts_router,
)

from app.api.v1.endpoints.user_profile.requests import (
    router as requests_router,
)

api_router = APIRouter()

api_router.include_router(
    accesscode_router,
    prefix="/codeservice/accesscode",
    tags=["AccessCode"],
)

api_router.include_router(
    visitorlog_router,
    prefix="/codeservice/visitorlog",
    tags=["VisitorLog"],
)

api_router.include_router(
    users_router,
    prefix="/userprofile/users",
    tags=["Users"],
)

api_router.include_router(
    estates_router,
    prefix="/userprofile/estates",
    tags=["Estates"],
)

api_router.include_router(
    rolepermission_router,
    prefix="/userprofile/rolepermission",
    tags=["RolePermission"],
)

api_router.include_router(
    residentdeparturelog_router,
    prefix="/userprofile/residentdeparturelog",
    tags=["ResidentDepartureLog"],
)

api_router.include_router(
    household_router,
    prefix="/userprofile/household",
    tags=["Household"],
)

api_router.include_router(
    adminmanagement_router,
    prefix="/userprofile/adminmanagement",
    tags=["AdminManagement"],
)

api_router.include_router(
    guests_router,
    prefix="/userprofile/guests",
    tags=["Guests"],
)

api_router.include_router(
    broadcasts_router,
    prefix="/userprofile/broadcasts",
    tags=["Broadcasts"],
)

api_router.include_router(
    requests_router,
    prefix="/userprofile/requests",
    tags=["Requests"],
)
