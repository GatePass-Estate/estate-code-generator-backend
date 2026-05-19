"""Validation rules on ``CodeValidationPayload``."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.anomaly_schema import CodeValidationPayload, Receiver


def _base_kwargs():
    uid = uuid4()
    return dict(
        user_id=uid,
        security_id=uid,
        estate_id=uid,
        hashed_code="h",
        valid_until="2099-01-01T00:00:00Z",
        is_expired=False,
    )


def test_exactly_one_log_id_required():
    with pytest.raises(ValidationError):
        CodeValidationPayload(
            **_base_kwargs(),
            receiver=Receiver.VISITOR,
            visitor_log_id=None,
            resident_log_id=None,
        )


def test_visitor_log_requires_visitor_receiver():
    lid = uuid4()
    with pytest.raises(ValidationError):
        CodeValidationPayload(
            **_base_kwargs(),
            receiver=Receiver.RESIDENT,
            visitor_log_id=lid,
            resident_log_id=None,
        )


def test_validated_user_id_json_alias():
    """Code-service shape may send ``validated_user_id`` instead of ``user_id``."""
    uid = uuid4()
    sid = uuid4()
    eid = uuid4()
    lid = uuid4()
    p = CodeValidationPayload.model_validate(
        {
            "validated_user_id": str(uid),
            "security_id": str(sid),
            "estate_id": str(eid),
            "hashed_code": "h",
            "valid_until": "2099-01-01T00:00:00Z",
            "is_expired": False,
            "receiver": "visitor",
            "visitor_log_id": str(lid),
            "resident_log_id": None,
        }
    )
    assert p.user_id == uid


def test_valid_visitor_payload():
    lid = uuid4()
    uid = uuid4()
    p = CodeValidationPayload(
        user_id=uid,
        security_id=uid,
        estate_id=uid,
        hashed_code="h",
        valid_until="2099-01-01T00:00:00Z",
        is_expired=False,
        receiver=Receiver.VISITOR,
        visitor_log_id=lid,
        resident_log_id=None,
    )
    assert p.visitor_log_id == lid
