import logging

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.core.config import settings
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)

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

_LOGO_URL = (
    "https://res.cloudinary.com/dcozenahn/image/upload"
    "/v1773876604/gatepass_ng_Gate_Pass_so5mc2.png"
)
_BTN_COLOR = "#113e55"
_TEXT_COLOR = "#172024"
_HEADING_COLOR = "#113e55"
_FRONTEND_BASE_URL = settings.FRONTEND_BASE_URL


def _build_email(
    heading: str,
    first_name: str,
    instruction: str,
    button_label: str | None = None,
    button_href: str | None = None,
) -> str:
    """Builds a full email HTML string using the GatePass branded template."""
    button_row = ""
    if button_label and button_href:
        button_row = f"""
          <!-- CTA Button -->
          <tr>
            <td
              align="left"
              class="button-cell content-group"
              style="padding-bottom: 71px; padding-left: 36px; width: 100%"
            >
              <a
                href="{button_href}"
                class="button"
                style="
                  display: inline-block;
                  width: 100%;
                  max-width: 526px;
                  padding: 20px 32px;
                  box-sizing: border-box;
                  background-color: {_BTN_COLOR};
                  color: #ffffff;
                  font-size: 16px;
                  font-weight: 600;
                  text-decoration: none;
                  border-radius: 8px;
                  text-align: center;
                "
              >
                {button_label}
              </a>
            </td>
          </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap"
    rel="stylesheet"
  />
  <link
    href="https://fonts.googleapis.com/css2?family=Ubuntu+Sans:wght@400;600&display=swap"
    rel="stylesheet"
  />
  <style>
    @media only screen and (max-width: 620px) {{
      .wrapper {{
        padding: 80px 31px 16px 31px !important;
      }}
      .content {{
        max-width: 100% !important;
      }}
      .logo {{
        padding-bottom: 17px !important;
      }}
      .logo img {{
        width: 166px !important;
        height: 68px !important;
        max-width: 166px !important;
      }}
      .heading {{
        font-size: 21px !important;
      }}
      .heading-cell {{
        padding-left: 16px !important;
        padding-right: 16px !important;
        padding-bottom: 33px !important;
      }}
      .button {{
        width: 100% !important;
        max-width: 100% !important;
        padding: 8px 16px !important;
        font-size: 14px !important;
        box-sizing: border-box !important;
      }}
      .body-text {{
        font-size: 12px !important;
      }}
      .body-text.instruction-text {{
        margin-bottom: 27px !important;
        line-height: 20px !important;
      }}
      .content-group {{
        padding-left: 16px !important;
      }}
      .content-group .body-text {{
        font-weight: 500 !important;
      }}
      .button-cell {{
        padding-bottom: 27px !important;
      }}
    }}
  </style>
</head>
<body
  style="
    margin: 0;
    padding: 0;
    background-color: #ffffff;
    font-family:
      'Ubuntu Sans',
      Ubuntu,
      -apple-system,
      BlinkMacSystemFont,
      'Segoe UI',
      sans-serif;
  "
>
  <table
    role="presentation"
    cellpadding="0"
    cellspacing="0"
    width="100%"
    style="background-color: #ffffff"
  >
    <tr>
      <td align="center" class="wrapper" style="padding: 164px 20px">
        <table
          role="presentation"
          cellpadding="0"
          cellspacing="0"
          width="100%"
          class="content"
          style="max-width: 600px; margin: 0 auto"
        >
          <!-- Logo -->
          <tr>
            <td align="left" class="logo" style="padding-bottom: 27px">
              <img
                src="{_LOGO_URL}"
                width="254"
                height="104"
                alt="Gate Pass"
                style="display: block; max-width: 100%; height: auto"
              />
            </td>
          </tr>
          <!-- Main Heading -->
          <tr>
            <td
              align="left"
              class="heading-cell"
              style="
                padding-bottom: 27px;
                padding-left: 30px;
                padding-right: 30px;
              "
            >
              <h1
                class="heading"
                style="
                  margin: 0;
                  font-size: 50px;
                  font-weight: 600;
                  color: {_HEADING_COLOR};
                  font-family:
                    'Ubuntu Sans',
                    Ubuntu,
                    -apple-system,
                    BlinkMacSystemFont,
                    'Segoe UI',
                    sans-serif;
                "
              >
                {heading}
              </h1>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td
              class="content-group"
              style="
                padding: 0 16px 0px 16px;
                padding-left: 36px;
                font-family:
                  'Inter',
                  -apple-system,
                  BlinkMacSystemFont,
                  sans-serif;
              "
            >
              <p
                class="body-text"
                style="
                  margin: 0;
                  font-size: 16px;
                  line-height: 1.8;
                  color: {_TEXT_COLOR};
                  text-align: left;
                "
              >
                Hi {first_name},
              </p>
              <p
                class="body-text instruction-text"
                style="
                  margin: 27px 0 62px 0;
                  font-size: 16px;
                  line-height: 24px;
                  color: {_TEXT_COLOR};
                  text-align: left;
                "
              >
                {instruction}
              </p>
            </td>
          </tr>
          {button_row}
          <!-- Closing -->
          <tr>
            <td class="content-group" style="padding-left: 36px">
              <p
                class="body-text"
                style="
                  margin: 0;
                  font-size: 16px;
                  line-height: 1.8;
                  color: {_TEXT_COLOR};
                  text-align: left;
                "
              >
                Thanks,<br />
                GatePass Team
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


async def _send(subject: str, recipient: str, body: str) -> None:
    if settings.MAIL_DEV_MODE:
        logger.info(
            "MAIL_DEV_MODE — suppressed email" " to=%s subject=%r",
            recipient,
            subject,
        )
        return
    if not settings.MAIL_USERNAME:
        logger.warning("SMTP not configured — skipping email to %s", recipient)
        return
    try:
        message = MessageSchema(
            subject=subject,
            recipients=[recipient],
            body=body,
            subtype=MessageType.html,
        )
        await FastMail(_conf).send_message(message)
    except Exception:
        logger.exception("Failed to send email to %s", recipient)


async def send_login_new_device_email(
    email: str, first_name: str, ip_address: str, device_name: str
) -> None:
    body = _build_email(
        heading="New Sign-In Detected",
        first_name=first_name,
        instruction=(
            f"We noticed a new sign-in to your GatePass account from "
            f"device '{device_name}' at IP {ip_address}. "
            "If this was you, no action is needed. "
            "If you don't recognise this activity, please change your "
            "password immediately and contact your administrator."
        ),
        button_label="Secure My Account",
        button_href=f"{_FRONTEND_BASE_URL}/settings/security",
    )
    await _send("New sign-in to your GatePass account", email, body)


async def send_password_changed_email(email: str, first_name: str) -> None:
    body = _build_email(
        heading="Password Changed",
        first_name=first_name,
        instruction=(
            "Your GatePass password was successfully changed. "
            "If you did not make this change, contact your administrator immediately."
        ),
    )
    await _send("Your GatePass password was changed", email, body)


async def send_two_fa_enabled_email(email: str, first_name: str) -> None:
    body = _build_email(
        heading="Two-Factor Authentication Enabled",
        first_name=first_name,
        instruction=(
            "Two-factor authentication has been enabled on your GatePass "
            "account. Your account is now more secure. "
            "If you did not make this change, please contact your administrator immediately."
        ),
    )
    await _send("Two-factor authentication enabled", email, body)


async def send_two_fa_disabled_email(email: str, first_name: str) -> None:
    body = _build_email(
        heading="Two-Factor Authentication Disabled",
        first_name=first_name,
        instruction=(
            "Two-factor authentication has been disabled on your GatePass "
            "account. If you did not make this change, please contact your "
            "administrator immediately and re-enable 2FA."
        ),
    )
    await _send("Two-factor authentication disabled", email, body)


async def send_two_fa_recovery_used_email(email: str, first_name: str) -> None:
    body = _build_email(
        heading="Recovery Code Used",
        first_name=first_name,
        instruction=(
            "A recovery code was used to access your GatePass account. "
            "Two-factor authentication has been disabled as a result. "
            "If this was not you, your account may be compromised — "
            "please change your password immediately. "
            "Otherwise, re-enable 2FA from your security settings."
        ),
        button_label="Manage Security",
        button_href=f"{_FRONTEND_BASE_URL}/settings/security",
    )
    await _send("A recovery code was used on your account", email, body)


async def send_role_promoted_email(
    email: str, first_name: str, new_role: str, estate_name: str
) -> None:
    body = _build_email(
        heading="You've Been Promoted",
        first_name=first_name,
        instruction=(
            f"Your role on '{estate_name}' has been updated to "
            f"{new_role.replace('_', ' ').title()}. "
            "Log in to access your new permissions."
        ),
        button_label="Log In",
        button_href=f"{_FRONTEND_BASE_URL}/auth/login",
    )
    await _send(
        f"You've been promoted to {new_role} on {estate_name}", email, body
    )


async def send_role_demoted_email(
    email: str, first_name: str, new_role: str, estate_name: str
) -> None:
    body = _build_email(
        heading="Role Updated",
        first_name=first_name,
        instruction=(
            f"Your role on '{estate_name}' has been updated to "
            f"{new_role.replace('_', ' ').title()}."
        ),
    )
    await _send(f"Your role on {estate_name} has been updated", email, body)


async def send_household_transferred_email(
    email: str, first_name: str, group_label: str = "household"
) -> None:
    label = group_label.lower()
    body = _build_email(
        heading=f"{label.capitalize()} Updated",
        first_name=first_name,
        instruction=(
            f"You have been moved to a new {label} by your administrator. "
            f"Log in to see your updated {label} details."
        ),
    )
    await _send(f"You've been moved to a new {label}", email, body)


async def send_incident_report_email(
    email: str,
    first_name: str,
    incident_title: str,
    estate_name: str,
) -> None:
    body = _build_email(
        heading="New Incident Report",
        first_name=first_name,
        instruction=(
            f"A new incident report titled '{incident_title}' has been "
            f"filed in '{estate_name}'. Please log in to review it."
        ),
        button_label="View Report",
        button_href=f"{_FRONTEND_BASE_URL}/incidents",
    )
    await _send(f"New incident report in {estate_name}", email, body)


async def send_edit_request_reviewed_email(
    email: str,
    first_name: str,
    request_type: str,
    review_status: str,
) -> None:
    status_word = review_status.capitalize()
    body = _build_email(
        heading=f"Edit Request {status_word}",
        first_name=first_name,
        instruction=(
            f"Your request to change your "
            f"{request_type.replace('_', ' ').lower()} "
            f"has been {status_word.lower()} by your administrator."
        ),
    )
    await _send(
        f"Your edit request has been {status_word.lower()}", email, body
    )


async def send_forgot_password_email(
    email: str, first_name: str, reset_url: str
) -> None:
    body = _build_email(
        heading="Reset Your Password",
        first_name=first_name,
        instruction=(
            "We received a request to reset your GatePass password. "
            "Click the button below to set a new password. "
            "This link expires in 24 hours. "
            "If you did not request a password reset, "
            "you can safely ignore this email."
        ),
        button_label="Reset Password",
        button_href=reset_url,
    )
    await _send("Reset your GatePass password", email, body)


async def send_email_verification_email(
    email: str, first_name: str, verification_url: str
) -> None:
    body = _build_email(
        heading="Activate Your Account",
        first_name=first_name,
        instruction=(
            "You're almost there! Confirm your email address "
            "by clicking below, "
            "and we'll guide you through setting your password to unlock "
            "your GatePass account. If you did not create a GatePass "
            "account, you can safely ignore this email."
        ),
        button_label="Activate Your Account",
        button_href=verification_url,
    )
    await _send("Activate your GatePass account", email, body)


async def send_welcome_email(email: str, first_name: str) -> None:
    body = _build_email(
        heading="Welcome to GatePass",
        first_name=first_name,
        instruction=(
            "Your account has been successfully activated. "
            "You are now part of the GatePass community — "
            "a smarter way to manage access and keep your community "
            "secure. Log in to get started."
        ),
        button_label="Log In to GatePass",
        button_href=f"{_FRONTEND_BASE_URL}/auth/login",
    )
    await _send("Welcome to GatePass — you're all set!", email, body)


async def send_password_reset_confirmed_email(
    email: str, first_name: str
) -> None:
    body = _build_email(
        heading="Password Reset",
        first_name=first_name,
        instruction=(
            "Your GatePass password has been successfully reset. "
            "Log in with your new password to continue accessing "
            "your account. "
            "If you did not make this change, please contact your administrator immediately."
        ),
    )
    await _send("Your GatePass password has been reset", email, body)


async def send_account_closed_email(email: str, first_name: str) -> None:
    body = _build_email(
        heading="Account Closed",
        first_name=first_name,
        instruction=(
            "Your GatePass account has been successfully closed. "
            "We're sorry to see you go. If you ever change your mind, "
            "you're welcome to create a new account at any time. "
            "If you did not request this, please contact your administrator immediately."
        ),
    )
    await _send("Your GatePass account has been closed", email, body)


async def send_account_deactivated_email(email: str, first_name: str) -> None:
    body = _build_email(
        heading="Account Closed",
        first_name=first_name,
        instruction=(
            "Your GatePass account has been closed by your administrator. "
            "You will no longer be able to log in. "
            "For more information, please contact your administrator directly."
        ),
    )
    await _send(
        "Your GatePass account has been closed",
        email,
        body,
    )


async def send_account_deactivation_scheduled_email(
    email: str, first_name: str, close_date: str
) -> None:
    body = _build_email(
        heading="Account Closure Scheduled",
        first_name=first_name,
        instruction=(
            f"Your GatePass account is scheduled to be closed on "
            f"{close_date}. After this date you will no longer be able to "
            "log in. For more information, please contact your administrator."
        ),
    )
    await _send("Your GatePass account is scheduled for closure", email, body)


async def send_community_deactivated_email(
    email: str, first_name: str, community_label: str = "community"
) -> None:
    label = community_label.lower()
    body = _build_email(
        heading=f"{label.capitalize()} Deactivated",
        first_name=first_name,
        instruction=(
            f"Your {label} has been deactivated by the GatePass platform. "
            "All logins and GatePass activity are currently suspended. "
            "Please contact GatePass support for further information."
        ),
    )
    await _send(f"Your {label} has been deactivated", email, body)


async def send_community_deactivation_scheduled_email(
    email: str,
    first_name: str,
    deactivate_date: str,
    community_label: str = "community",
) -> None:
    label = community_label.lower()
    body = _build_email(
        heading=f"{label.capitalize()} Deactivation Scheduled",
        first_name=first_name,
        instruction=(
            f"Your {label} is scheduled to be deactivated on "
            f"{deactivate_date}. After this date all logins and GatePass "
            "activity will be suspended. Please contact GatePass support "
            "if you have any questions."
        ),
    )
    await _send(f"Your {label} is scheduled for deactivation", email, body)


async def send_community_reactivated_email(
    email: str, first_name: str, community_label: str = "community"
) -> None:
    label = community_label.lower()
    body = _build_email(
        heading=f"{label.capitalize()} Reactivated",
        first_name=first_name,
        instruction=(
            f"Your {label} has been reactivated. "
            "All logins and GatePass activity are now restored."
        ),
        button_label="Log In",
        button_href=f"{_FRONTEND_BASE_URL}/auth/login",
    )
    await _send(f"Your {label} has been reactivated", email, body)


async def dispatch_email(
    notification_type: NotificationType,
    email: str,
    first_name: str,
    metadata: dict,
) -> None:
    """Route a notification type to the right email sender function."""
    if notification_type == NotificationType.LOGIN_NEW_DEVICE:
        await send_login_new_device_email(
            email=email,
            first_name=first_name,
            ip_address=metadata.get("ip_address", "unknown"),
            device_name=metadata.get("device_name", "unknown device"),
        )
    elif notification_type == NotificationType.PASSWORD_CHANGED:
        await send_password_changed_email(email=email, first_name=first_name)
    elif notification_type == NotificationType.TWO_FA_ENABLED:
        await send_two_fa_enabled_email(email=email, first_name=first_name)
    elif notification_type == NotificationType.TWO_FA_DISABLED:
        await send_two_fa_disabled_email(email=email, first_name=first_name)
    elif notification_type == NotificationType.TWO_FA_RECOVERY_USED:
        await send_two_fa_recovery_used_email(
            email=email, first_name=first_name
        )
    elif notification_type == NotificationType.ROLE_PROMOTED:
        await send_role_promoted_email(
            email=email,
            first_name=first_name,
            new_role=metadata.get("new_role", ""),
            estate_name=metadata.get("estate_name", "your community"),
        )
    elif notification_type == NotificationType.ROLE_DEMOTED:
        await send_role_demoted_email(
            email=email,
            first_name=first_name,
            new_role=metadata.get("new_role", ""),
            estate_name=metadata.get("estate_name", "your community"),
        )
    elif notification_type == NotificationType.HOUSEHOLD_TRANSFERRED:
        await send_household_transferred_email(
            email=email,
            first_name=first_name,
            group_label=metadata.get("group_label", "household"),
        )
    elif notification_type == NotificationType.INCIDENT_REPORT_FILED:
        await send_incident_report_email(
            email=email,
            first_name=first_name,
            incident_title=metadata.get("title", "Incident"),
            estate_name=metadata.get("estate_name", "your community"),
        )
    elif notification_type == NotificationType.EDIT_REQUEST_REVIEWED:
        await send_edit_request_reviewed_email(
            email=email,
            first_name=first_name,
            request_type=metadata.get("request_type", "field"),
            review_status=metadata.get("review_status", "reviewed"),
        )
    elif notification_type == NotificationType.FORGOT_PASSWORD:
        await send_forgot_password_email(
            email=email,
            first_name=first_name,
            reset_url=metadata.get("reset_url", _FRONTEND_BASE_URL),
        )
    elif notification_type == NotificationType.EMAIL_VERIFICATION:
        await send_email_verification_email(
            email=email,
            first_name=first_name,
            verification_url=metadata.get(
                "verification_url", _FRONTEND_BASE_URL
            ),
        )
    elif notification_type == NotificationType.WELCOME:
        await send_welcome_email(email=email, first_name=first_name)
    elif notification_type == NotificationType.PASSWORD_RESET_CONFIRMED:
        await send_password_reset_confirmed_email(
            email=email, first_name=first_name
        )
    elif notification_type == NotificationType.ACCOUNT_CLOSED:
        await send_account_closed_email(email=email, first_name=first_name)
    elif notification_type == NotificationType.ACCOUNT_DEACTIVATED:
        await send_account_deactivated_email(
            email=email, first_name=first_name
        )
    elif notification_type == NotificationType.ACCOUNT_DEACTIVATION_SCHEDULED:
        await send_account_deactivation_scheduled_email(
            email=email,
            first_name=first_name,
            close_date=metadata.get("close_at", "a scheduled date"),
        )
    elif notification_type == NotificationType.ESTATE_DEACTIVATED:
        await send_community_deactivated_email(
            email=email,
            first_name=first_name,
            community_label=metadata.get("community_label", "community"),
        )
    elif notification_type == NotificationType.ESTATE_DEACTIVATION_SCHEDULED:
        await send_community_deactivation_scheduled_email(
            email=email,
            first_name=first_name,
            deactivate_date=metadata.get("deactivate_at", "a scheduled date"),
            community_label=metadata.get("community_label", "community"),
        )
    elif notification_type == NotificationType.ESTATE_REACTIVATED:
        await send_community_reactivated_email(
            email=email,
            first_name=first_name,
            community_label=metadata.get("community_label", "community"),
        )
