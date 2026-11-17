"""GatePass free (GPF) features — included on every subscription tier."""

from typing import TypedDict


class FreePlatformFeature(TypedDict):
    service_key: str
    label: str


# Service Catalog.xlsx — Free Features (GPF*). Not stored in service_catalog.
FREE_PLATFORM_FEATURES: tuple[FreePlatformFeature, ...] = (
    {
        "service_key": "visitor_access_code",
        "label": "Visitor's Access Code",
    },
    {
        "service_key": "resident_access_code",
        "label": "Resident's Access Code",
    },
    {
        "service_key": "basic_historical_records",
        "label": "Recent Historical Records",
    },
    {
        "service_key": "household_department_managmt",
        "label": "Household/Department Management",
    },
    {
        "service_key": "kyc_id_verification",
        "label": "KYC Identity Verification",
    },
)

EXCLUDED_SERVICE_CATALOG_KEYS = frozenset({"administrative_fee", "vat"})
