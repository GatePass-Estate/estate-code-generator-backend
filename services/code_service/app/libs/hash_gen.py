import hashlib
from datetime import datetime, timezone

from app.schemas.code_service import Receiver


def _utc_timestamp_token(now: datetime) -> str:
    """Normalize ``now`` to UTC and stringify for stable hash input."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    return now.isoformat().replace("+00:00", "Z")


def generate_unique_code(
    user_id: str,
    estate_id: str,
    *,
    now: datetime,
    visitor_fullname: str = None,
    relationship_with_resident: str = None,
    receiver: Receiver = None,
    validity_period: dict | None = None,
) -> str:
    """
    Generate a unique 6-character alphanumeric code based on input details.

    Arguments:
        user_id: The unique identifier for the user (e.g., a UUID).
        estate_id: The estate the code belongs to.
        now: UTC-aware generation timestamp (microsecond precision preserved).
        visitor_fullname: The name of the visitor.
        relationship_with_resident: The relationship of the visitor to the user.
        receiver: Whether the code is for a visitor or resident.
        validity_period: Optional visitor validity bounds with ``start`` and
            ``end`` UTC datetimes. Included in the hash for visitors only.

    Returns:
        A 6-character alphanumeric code that uniquely represents the
        combination of the input values.
    """
    timestamp = _utc_timestamp_token(now)

    if receiver == Receiver.VISITOR:
        raw_period = validity_period or {}
        if isinstance(raw_period, dict):
            period_start = raw_period.get("start") or ""
            period_end = raw_period.get("end") or ""
        else:
            period_start = getattr(raw_period, "start", None) or ""
            period_end = getattr(raw_period, "end", None) or ""
        combined = (
            f"{user_id}|{estate_id}|{visitor_fullname}|"
            f"{relationship_with_resident}|{timestamp}|"
            f"{period_start}|{period_end}"
        )
    else:
        combined = f"{user_id}|{estate_id}|{timestamp}"

    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    hash_int = int(hash_obj.hexdigest(), 16)
    mod_value = hash_int % (36**6)

    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code = ""
    for _ in range(6):
        mod_value, i = divmod(mod_value, len(alphabet))
        code = alphabet[i] + code

    return code


if __name__ == "__main__":
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    estate_id = "123e4567-e89b-12d3-a456-426614174000"
    visitor_fullname = "Michael"
    relationship_with_resident = "friend"
    now = datetime(2025, 4, 6, 14, 30, 45, 123456, tzinfo=timezone.utc)
    print(
        generate_unique_code(
            user_id,
            estate_id,
            now=now,
            visitor_fullname=visitor_fullname,
            relationship_with_resident=relationship_with_resident,
            receiver=Receiver.VISITOR,
            validity_period={
                "start": "2025-04-06 14:00:00.000+0000",
                "end": "2025-04-06 18:00:00.000+0000",
            },
        )
    )
