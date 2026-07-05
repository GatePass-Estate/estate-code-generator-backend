"""RBAC matrix tests for document_permissions helpers."""

from __future__ import annotations

import pytest

from app.libs.document_permissions import can_download, can_upload, can_view

_SAME_ESTATE = "estate-a"
_OTHER_ESTATE = "estate-b"


def _user(user_id: str, estate_id: str | None = _SAME_ESTATE) -> dict:
    return {"id": user_id, "estate_id": estate_id}


def _permissions(**kwargs: bool) -> dict[str, bool]:
    defaults = {
        "can_view_other_user_documents": False,
        "can_view_other_user_documents_in_other_estate": False,
        "can_download_other_user_documents": False,
        "can_download_other_user_documents_in_other_estate": False,
    }
    defaults.update(kwargs)
    return defaults


@pytest.mark.parametrize(
    "requester,target,permissions,expected",
    [
        (_user("u1"), _user("u1"), _permissions(), True),
        (
            _user("u1"),
            _user("u2"),
            _permissions(can_view_other_user_documents=True),
            True,
        ),
        (_user("u1"), _user("u2"), _permissions(), False),
        (
            _user("u1"),
            _user("u2", _OTHER_ESTATE),
            _permissions(
                can_view_other_user_documents=True,
                can_view_other_user_documents_in_other_estate=True,
            ),
            True,
        ),
        (
            _user("u1"),
            _user("u2", _OTHER_ESTATE),
            _permissions(can_view_other_user_documents=True),
            False,
        ),
        (
            _user("u1", _OTHER_ESTATE),
            _user("u2"),
            _permissions(
                can_view_other_user_documents=True,
                can_view_other_user_documents_in_other_estate=True,
            ),
            True,
        ),
    ],
)
def test_can_view_matrix(requester, target, permissions, expected):
    assert can_view(requester, target, permissions) is expected


@pytest.mark.parametrize(
    "requester,target,permissions,expected",
    [
        (_user("u1"), _user("u1"), _permissions(), True),
        (
            _user("u1"),
            _user("u2"),
            _permissions(can_download_other_user_documents=True),
            True,
        ),
        (_user("u1"), _user("u2"), _permissions(), False),
        (
            _user("u1"),
            _user("u2", _OTHER_ESTATE),
            _permissions(
                can_download_other_user_documents=True,
                can_download_other_user_documents_in_other_estate=True,
            ),
            True,
        ),
        (
            _user("u1"),
            _user("u2", _OTHER_ESTATE),
            _permissions(can_download_other_user_documents=True),
            False,
        ),
    ],
)
def test_can_download_matrix(requester, target, permissions, expected):
    assert can_download(requester, target, permissions) is expected


def test_can_upload_always_true():
    assert can_upload(_user("u1")) is True
