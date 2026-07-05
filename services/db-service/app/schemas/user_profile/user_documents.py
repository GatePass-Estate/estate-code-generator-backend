from enum import StrEnum

__all__ = ["DocumentType"]


class DocumentType(StrEnum):
    """Supported user document types stored in GCS."""

    PROFILE_PICTURE = "profile_picture"
    ID_CARD = "id_card"
