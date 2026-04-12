"""Validation rules on ``CodeValidationPayload``."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.schemas import CodeValidationPayload, Receiver


def _base_kwargs():
    uid = uuid4()
    return dict(
        validated_user_id=uid,
        security_id=uid,
        user_id=uid,
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


def test_valid_visitor_payload():
    lid = uuid4()
    uid = uuid4()
    p = CodeValidationPayload(
        validated_user_id=uid,
        security_id=uid,
        user_id=uid,
        estate_id=uid,
        hashed_code="h",
        valid_until="2099-01-01T00:00:00Z",
        is_expired=False,
        receiver=Receiver.VISITOR,
        visitor_log_id=lid,
        resident_log_id=None,
    )
    assert p.visitor_log_id == lid
