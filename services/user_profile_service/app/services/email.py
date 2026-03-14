from urllib.parse import urlencode
from app.core.config import settings


def send_verification_email(email: str, token: str) -> None:
    """
    Prints the email verification link. Placeholder for real email logic.
    """
    base_url = settings.BASE_URL
    query = urlencode({"token": token})
    verify_link = f"{base_url}api/v1/users/verify/email?{query}"

    print(f"📩 Verification email for {email}:\n👉 {verify_link}")


def send_password_reset_email(email: str, token: str) -> None:
    """
    Prints the password reset link. Placeholder for real email logic.
    """
    base_url = settings.BASE_URL
    query = urlencode({"token": token})
    reset_link = f"{base_url}api/v1/users/verify/password-reset?{query}"

    print(f"📩 Password reset email for {email}:\n👉 {reset_link}")
