import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits  # 36 characters
_CODE_LENGTH = 6
_MAX_ATTEMPTS = 10


def generate_unique_code(
    existing_codes: set[str] | None = None, **_kwargs
) -> str:
    """Generate a random 6-character alphanumeric code (A-Z, 0-9)."""
    for _ in range(_MAX_ATTEMPTS):
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
        if existing_codes is None or code not in existing_codes:
            return code
    return code
