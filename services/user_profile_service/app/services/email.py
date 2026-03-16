# from urllib.parse import urlencode
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings

_conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

_BRAND_COLOR = "#2E7D32"
_BTN_COLOR = "#2E7D32"


def _base_template(content: str) -> str:
    """Wraps email content in a shared branded shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body style="margin:0;padding:0;background-color:#f0f2f5;
font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
  style="background-color:#f0f2f5;padding:40px 0;">
    <tr>
      <td align="center">
        <!-- Header -->
        <table width="560" cellpadding="0" cellspacing="0"
               style="background-color:{_BRAND_COLOR};
               border-radius:8px 8px 0 0;">
          <tr>
            <td align="center" style="padding:28px 40px;">
              <span style="font-size:26px;font-weight:bold;color:#ffffff;
                           letter-spacing:1px;">GatePass</span>
            </td>
          </tr>
        </table>
        <!-- Card -->
        <table width="560" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:0 0 8px 8px;
                      box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <tr>
            <td style="padding:40px 48px 32px;">
              {content}
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:0 48px 32px;">
              <hr style="border:none;border-top:1px solid #eeeeee;
              margin:0 0 20px;"/>
              <p style="margin:0;font-size:12px;color:#999999;
              line-height:1.6;">
                You received this email because an action was performed on your
                GatePass account. If you did not request this, you can safely
                ignore this email.
              </p>
              <p style="margin:12px 0 0;font-size:12px;color:#bbbbbb;">
                &copy; 2025 GatePass. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def send_verification_email(email: str, token: str) -> None:
    """
    Sends an email verification link to the user.
    """
    # base_url = settings.BASE_URL
    # query = urlencode({"token": token})
    # verify_link = f"{base_url}api/v1/users/verify/email?{query}"
    # Temporary placeholder until we have a real frontend URL to link to
    # @TODO: Update this to point to the actual frontend email verification
    # page once it's implemented
    verify_link = "https://www.google.com"  # Temporary placeholder

    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1a1a1a;">
        Verify your Email Address
      </h2>
      <p style="margin:0 0 24px;font-size:15px;color:#555555;line-height:1.6;">
        Thanks for signing up for GatePass! Please confirm your email address
        by clicking the button below. This helps us keep your account secure.
      </p>
      <table cellpadding="0" cellspacing="0" style="margin:0 0 28px;">
        <tr>
          <td align="center"
              style="background-color:{_BTN_COLOR};border-radius:6px;">
            <a href="{verify_link}"
               style="display:inline-block;padding:14px 36px;font-size:15px;
                      font-weight:bold;color:#ffffff;text-decoration:none;">
              Verify Email Address
            </a>
          </td>
        </tr>
      </table>
      <p style="margin:0 0 6px;font-size:13px;color:#888888;">
        Or copy this link into your browser:
      </p>
      <p style="margin:0 0 24px;font-size:12px;word-break:break-all;">
        <a href="{verify_link}" style="color:{_BRAND_COLOR};">{verify_link}</a>
      </p>
      <p style="margin:0;font-size:13px;color:#aaaaaa;">
        This link expires in <strong>24 hours</strong>.
      </p>
    """

    body = _base_template(content)

    message = MessageSchema(
        subject="Verify your GatePass email address",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    await FastMail(_conf).send_message(message)


async def send_welcome_email(email: str, first_name: str) -> None:
    """
    Sends a welcome email after a user activates their account.
    """
    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1a1a1a;">
        Welcome to GatePass, {first_name}! &#127881;
      </h2>
      <p style="margin:0 0 20px;font-size:15px;color:#555555;line-height:1.6;">
        Your account has been verified and activated. You are now part of the
        GatePass community &mdash; a smarter way to manage estate access and
        keep your home secure.
      </p>
      <p style="margin:0 0 24px;font-size:15px;color:#555555;line-height:1.6;">
        Here&rsquo;s what you can do with GatePass:
      </p>
      <table cellpadding="0" cellspacing="0" width="100%"
             style="margin:0 0 28px;">
        <tr>
          <td style="padding:8px 0;font-size:14px;color:#444444;">
            &#9989;&nbsp; Manage guest access and invitations
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;font-size:14px;color:#444444;">
            &#9989;&nbsp; Track visitor arrivals in real time
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0;font-size:14px;color:#444444;">
            &#9989;&nbsp; Communicate with estate security staff
          </td>
        </tr>
      </table>
      <p style="margin:0 0 24px;font-size:15px;color:#555555;line-height:1.6;">
        Log in to your account to get started.
      </p>
      <p style="margin:0;font-size:13px;color:#aaaaaa;">
        If you have any questions, reply to this email or contact our support
        team at <a href="mailto:info@gatepassng.com"
        style="color:{_BRAND_COLOR};">info@gatepassng.com</a>.
      </p>
    """

    body = _base_template(content)

    message = MessageSchema(
        subject="Welcome to GatePass — you're all set!",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    await FastMail(_conf).send_message(message)


async def send_password_reset_email(email: str, token: str) -> None:
    """
    Sends a password reset link to the user.
    """
    # base_url = settings.BASE_URL
    # query = urlencode({"token": token})
    # reset_link = f"{base_url}api/v1/users/verify/password-reset?{query}"
    # Temporary placeholder until we have a real frontend URL to link to
    # @TODO: Update this to point to the actual frontend email verification
    # page once it's implemented
    reset_link = "https://www.google.com"  # Temporary placeholder

    content = f"""
      <h2 style="margin:0 0 8px;font-size:22px;color:#1a1a1a;">
        Reset your Password
      </h2>
      <p style="margin:0 0 24px;font-size:15px;color:#555555;line-height:1.6;">
        We received a request to reset the password for your GatePass account.
        Click the button below to choose a new password.
      </p>
      <table cellpadding="0" cellspacing="0" style="margin:0 0 28px;">
        <tr>
          <td align="center"
              style="background-color:{_BTN_COLOR};border-radius:6px;">
            <a href="{reset_link}"
               style="display:inline-block;padding:14px 36px;font-size:15px;
                      font-weight:bold;color:#ffffff;text-decoration:none;">
              Reset Password
            </a>
          </td>
        </tr>
      </table>
      <p style="margin:0 0 6px;font-size:13px;color:#888888;">
        Or copy this link into your browser:
      </p>
      <p style="margin:0 0 24px;font-size:12px;word-break:break-all;">
        <a href="{reset_link}" style="color:{_BRAND_COLOR};">{reset_link}</a>
      </p>
      <p style="margin:0;font-size:13px;color:#aaaaaa;">
        This link expires in <strong>24 hours</strong>. If you did not request
        a password reset, no action is needed.
      </p>
    """

    body = _base_template(content)

    message = MessageSchema(
        subject="Reset your GatePass password",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    await FastMail(_conf).send_message(message)
