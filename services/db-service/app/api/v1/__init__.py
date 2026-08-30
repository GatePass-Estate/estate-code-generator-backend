from fastapi import APIRouter

from app.api.v1.endpoints.code_service.access_code import (
    router as accesscode_router,
)
from app.api.v1.endpoints.user_profile.incident_report import (
    router as incidentreport_router,
)
from app.api.v1.endpoints.code_service.log_feature_engineering import (
    router as logfeatureengineering_router,
)
from app.api.v1.endpoints.code_service.prediction_result import (
    router as predictionresult_router,
)
from app.api.v1.endpoints.code_service.resident_log import (
    router as residentlog_router,
)
from app.api.v1.endpoints.code_service.visitor_log import (
    router as visitorlog_router,
)
from app.api.v1.endpoints.user_profile.admin_management import (
    router as adminmanagement_router,
)
from app.api.v1.endpoints.user_profile.broadcast_reads import (
    router as broadcast_reads_router,
)
from app.api.v1.endpoints.user_profile.broadcasts import (
    router as broadcasts_router,
)
from app.api.v1.endpoints.user_profile.estates import router as estates_router
from app.api.v1.endpoints.user_profile.guests import (
    router as guests_router,
)
from app.api.v1.endpoints.user_profile.household import (
    router as household_router,
)
from app.api.v1.endpoints.user_profile.notifications import (
    router as notifications_router,
)
from app.api.v1.endpoints.user_profile.requests import (
    router as requests_router,
)
from app.api.v1.endpoints.user_profile.resident_departure_log import (
    router as residentdeparturelog_router,
)
from app.api.v1.endpoints.user_profile.role_permission import (
    router as rolepermission_router,
)
from app.api.v1.endpoints.user_profile.sessions import (
    router as sessions_router,
)
from app.api.v1.endpoints.user_profile.totp_recovery_codes import (
    router as totprecoverycodes_router,
)
from app.api.v1.endpoints.user_profile.user_documents import (
    router as userdocuments_router,
)
from app.api.v1.endpoints.user_profile.users import router as users_router
from app.api.v1.endpoints.revenue.service_catalog import (
    router as servicecatalog_router,
)
from app.api.v1.endpoints.revenue.ai_feature import (
    router as aifeature_router,
)
from app.api.v1.endpoints.revenue.ai_marketplace_feature import (
    router as aimarketplacefeature_router,
)
from app.api.v1.endpoints.revenue.ai_marketplace_feature_rating import (
    router as aimarketplacefeaturerating_router,
)
from app.api.v1.endpoints.revenue.feature_unit_price import (
    router as featureunitprice_router,
)
from app.api.v1.endpoints.revenue.subscription_tier import (
    router as subscriptiontier_router,
)
from app.api.v1.endpoints.revenue.estate_subscription import (
    router as estatesubscription_router,
)
from app.api.v1.endpoints.revenue.estate_ai_feature import (
    router as estateaifeature_router,
)
from app.api.v1.endpoints.revenue.payment_checkout_session import (
    router as paymentcheckoutsession_router,
)
from app.api.v1.endpoints.revenue.payment_event import (
    router as paymentevent_router,
)
from app.api.v1.endpoints.revenue.payment_transaction import (
    router as paymenttransaction_router,
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
    logfeatureengineering_router,
    prefix="/codeservice/logfeatureengineering",
    tags=["LogFeatureEngineering"],
)

api_router.include_router(
    predictionresult_router,
    prefix="/codeservice/predictionresult",
    tags=["PredictionResult"],
)

api_router.include_router(
    residentlog_router,
    prefix="/codeservice/residentlog",
    tags=["ResidentLog"],
)

api_router.include_router(
    incidentreport_router,
    prefix="/userprofile/incidentreport",
    tags=["IncidentReport"],
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
    broadcast_reads_router,
    prefix="/userprofile/broadcast_reads",
    tags=["BroadcastReads"],
)

api_router.include_router(
    requests_router,
    prefix="/userprofile/requests",
    tags=["Requests"],
)

api_router.include_router(
    sessions_router,
    prefix="/userprofile/sessions",
    tags=["Sessions"],
)

api_router.include_router(
    totprecoverycodes_router,
    prefix="/userprofile/totprecoverycodes",
    tags=["TotpRecoveryCodes"],
)

api_router.include_router(
    userdocuments_router,
    prefix="/userprofile/userdocuments",
    tags=["UserDocuments"],
)

api_router.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["Notifications"],
)

api_router.include_router(
    servicecatalog_router,
    prefix="/revenue/servicecatalog",
    tags=["ServiceCatalog"],
)

api_router.include_router(
    aifeature_router,
    prefix="/revenue/aifeature",
    tags=["AiFeature"],
)

api_router.include_router(
    aimarketplacefeature_router,
    prefix="/revenue/aimarketplacefeature",
    tags=["AiMarketplaceFeature"],
)

api_router.include_router(
    aimarketplacefeaturerating_router,
    prefix="/revenue/aimarketplacefeaturerating",
    tags=["AiMarketplaceFeatureRating"],
)

api_router.include_router(
    featureunitprice_router,
    prefix="/revenue/featureunitprice",
    tags=["FeatureUnitPrice"],
)

api_router.include_router(
    subscriptiontier_router,
    prefix="/revenue/subscriptiontier",
    tags=["SubscriptionTier"],
)

api_router.include_router(
    estatesubscription_router,
    prefix="/revenue/estatesubscription",
    tags=["EstateSubscription"],
)

api_router.include_router(
    estateaifeature_router,
    prefix="/revenue/estateaifeature",
    tags=["EstateAiFeature"],
)

api_router.include_router(
    paymentcheckoutsession_router,
    prefix="/revenue/paymentcheckoutsession",
    tags=["PaymentCheckoutSession"],
)

api_router.include_router(
    paymentevent_router,
    prefix="/revenue/paymentevent",
    tags=["PaymentEvent"],
)

api_router.include_router(
    paymenttransaction_router,
    prefix="/revenue/paymenttransaction",
    tags=["PaymentTransaction"],
)
