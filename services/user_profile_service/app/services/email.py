from urllib.parse import urlencode
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

_LOGO_URL = (
    "https://res.cloudinary.com/dcozenahn/image/upload"
    "/v1773876604/gatepass_ng_Gate_Pass_so5mc2.png"
)
_BTN_COLOR = "#113e55"
_TEXT_COLOR = "#172024"
_HEADING_COLOR = "#113e55"


def _build_email(
    heading: str,
    first_name: str,
    instruction: str,
    button_label: str,
    button_href: str,
) -> str:
    """Builds a full email HTML string using the GatePass branded template."""
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
                  font-family:
                    'Inter',
                    -apple-system,
                    BlinkMacSystemFont,
                    sans-serif !important;
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
                  font-family:
                    'Inter',
                    -apple-system,
                    BlinkMacSystemFont,
                    sans-serif !important;
                "
              >
                {instruction}
              </p>
            </td>
          </tr>
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
                  font-family:
                    &quot;Ubuntu Sans&quot;,
                      Ubuntu,
                      -apple-system,
                      BlinkMacSystemFont,
                      &quot;Segoe UI&quot;,
                      sans-serif;
                  text-align: center;
                "
              >
                {button_label}
              </a>
            </td>
          </tr>
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
                  font-family:
                    'Inter',
                    -apple-system,
                    BlinkMacSystemFont,
                    sans-serif !important;
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


async def send_verification_email(
    email: str, first_name: str, token: str
) -> None:
    """Sends an account activation / email verification link to the user."""
    query = urlencode({"token": token})
    verify_link = f"https://app.gatepassng.com/activate?{query}"
    # @TO-DO: Replace with your frontend account activation URL once available

    body = _build_email(
        heading="Activate Your Account",
        first_name=first_name,
        instruction=(
            "You're almost there! Confirm your email address "
            "by clicking below, "
            "and we'll guide you through setting your password to unlock your "
            "GatePass account. If you did not create a GatePass account, "
            "you can safely ignore this email."
        ),
        button_label="Activate Your Account",
        button_href=verify_link,
    )

    message = MessageSchema(
        subject="Activate your GatePass account",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    await FastMail(_conf).send_message(message)


async def send_welcome_email(email: str, first_name: str) -> None:
    """Sends a welcome email after a user successfully
    activates their account."""
    # @TODO: Replace with your frontend login/dashboard URL once available
    login_link = "https://app.gatepassng.com/login"

    body = _build_email(
        heading="Welcome to GatePass",
        first_name=first_name,
        instruction=(
            "Your account has been successfully activated. "
            "You are now part of the GatePass community — "
            "a smarter way to manage estate access and keep your home secure. "
            "Log in to get started."
        ),
        button_label="Log In to GatePass",
        button_href=login_link,
    )

    message = MessageSchema(
        subject="Welcome to GatePass — you're all set!",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    await FastMail(_conf).send_message(message)


async def send_password_reset_email(
    email: str, first_name: str, token: str
) -> None:
    """Sends a password reset link to the user."""
    query = urlencode({"token": token})
    reset_link = f"https://app.gatepassng.com/password-reset?{query}"
    # @TO-DO: Replace with your frontend password reset URL once available

    body = _build_email(
        heading="Reset Your Password",
        first_name=first_name,
        instruction=(
            "We received a request to reset your GatePass password. "
            "Click the button below to set a new password. "
            "This link expires in 24 hours. "
            "If you did not request a password reset,"
            " you can safely ignore this email."
        ),
        button_label="Reset Password",
        button_href=reset_link,
    )

    message = MessageSchema(
        subject="Reset your GatePass password",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    await FastMail(_conf).send_message(message)


async def send_password_reset_confirmation_email(
    email: str, first_name: str
) -> None:
    """Sends a security notification after a password reset is completed."""
    body = _build_email(
        heading="Password Reset",
        first_name=first_name,
        instruction=(
            "Your GatePass password has been successfully reset. "
            "Log in with your new password to continue accessing "
            "your account. "
            "If you did not make this change, please contact your estate "
            "administrator immediately."
        ),
        button_label="Log In",
        button_href="https://app.gatepassng.com/login",
    )

    message = MessageSchema(
        subject="Your GatePass password has been reset",
        recipients=[email],
        body=body,
        subtype=MessageType.html,
    )

    await FastMail(_conf).send_message(message)
