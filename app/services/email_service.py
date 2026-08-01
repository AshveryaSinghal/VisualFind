"""
Outgoing email - currently just the "reset your password" link.

Deliberately tiny: plain smtplib, no extra dependency. If SMTP isn't
configured (local dev with no .env changes), we log the link instead of
sending it, so the forgot-password flow is fully testable without ever
touching a real mailbox. See app/config.py for the SMTP_* / FRONTEND_BASE_URL
settings (Gmail works fine here with an "App Password").
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)

def _smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_username and settings.smtp_password)

def send_password_reset_email(to_email: str, reset_token: str) -> None:
    reset_link = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={reset_token}"

    if not _smtp_configured():

        logger.warning(
            "SMTP is not configured (see SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD in .env). "
            "Password reset link for %s: %s",
            to_email,
            reset_link,
        )
        return

    message = EmailMessage()
    message["Subject"] = "Reset your VisualFind password"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email

    message.set_content(
        "We received a request to reset your VisualFind password.\n\n"
        f"Reset it here: {reset_link}\n\n"
        f"This link expires in {settings.password_reset_token_expire_minutes} minutes. "
        "If you didn't request this, you can safely ignore this email."
    )
    message.add_alternative(
        f"""\
<html>
  <body style="font-family: sans-serif; color: #111;">
    <h2>Reset your VisualFind password</h2>
    <p>We received a request to reset the password for this account.</p>
    <p>
      <a href="{reset_link}"
         style="display:inline-block;padding:10px 20px;background:#4f46e5;color:#fff;
                border-radius:6px;text-decoration:none;">
        Reset password
      </a>
    </p>
    <p>Or copy this link into your browser:<br>{reset_link}</p>
    <p style="color:#666;font-size:13px;">
      This link expires in {settings.password_reset_token_expire_minutes} minutes.
      If you didn't request this, you can safely ignore this email.
    </p>
  </body>
</html>
""",
        subtype="html",
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except Exception:

        logger.exception("Failed to send password reset email to %s", to_email)
