"""Tests for document path building and approval gating."""

from app.libs.document_validation import build_object_path
from gatepass_docs import requires_admin_approval
from app.schemas.user_profile.user_documents import DocumentType


def test_build_object_path_main_folder():
    path = build_object_path(
        estate_id="e1",
        user_id="u1",
        document_type=DocumentType.PROFILE_PICTURE,
        document_id="doc-1",
        content_type="image/png",
        pending=False,
    )
    assert path == "estates/e1/users/u1/profile_picture_doc-1.png"


def test_build_object_path_temp_folder():
    path = build_object_path(
        estate_id="e1",
        user_id="u1",
        document_type=DocumentType.ID_CARD,
        document_id="doc-1",
        content_type="application/pdf",
        pending=True,
    )
    assert path == "estates/e1/users/u1/temp/id_card_doc-1.pdf"


def test_requires_admin_approval_for_resident_id_card():
    assert requires_admin_approval(DocumentType.ID_CARD, "resident") is True
    assert requires_admin_approval(DocumentType.ID_CARD, "security") is True
    assert requires_admin_approval(DocumentType.ID_CARD, "admin") is False
    assert (
        requires_admin_approval(DocumentType.PROFILE_PICTURE, "resident")
        is False
    )
