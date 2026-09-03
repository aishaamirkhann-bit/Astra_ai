"""
EmailService
------------
Delivers transactional HTML email through the first configured provider:

  1. Resend   — set RESEND_API_KEY (stdlib urllib, no SDK needed)
  2. SMTP     — set SMTP_HOST + SMTP_USERNAME (or SMTP_USER) + SMTP_PASSWORD
  3. Dev log  — nothing configured: codes are printed to the console when
                OTP_DEBUG_LOG=true so local dev keeps working.

Fill credentials in .env — it is covered by .gitignore, never commit them.
"""
import json
import logging
import smtplib
import socket
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("astra.email")


def _smtp_username() -> str:
    return settings.SMTP_USERNAME or settings.SMTP_USER


def send_html_email(to_email: str, subject: str, text: str, html: str) -> None:
    """Provider chain: Resend -> SMTP -> dev console log."""
    if settings.OTP_DEBUG_LOG:
        # Dev convenience only — disable (OTP_DEBUG_LOG=false) in production
        # so sensitive codes never land in logs.
        logger.info("[DEV EMAIL] %s | %s", to_email, subject)
        print(f"[DEV EMAIL] {to_email} | {subject}", flush=True)

    if settings.RESEND_API_KEY:
        payload = json.dumps({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html,
            "text": text,
        }).encode("utf-8")
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status >= 300:
                    raise RuntimeError(f"Resend delivery failed with status {response.status}")
        except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as cause:
            logger.warning("Resend failed, falling back: %s", str(cause)[:120])
        else:
            return

    if settings.SMTP_HOST and _smtp_username():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(_smtp_username(), settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
        return

    if not settings.OTP_DEBUG_LOG:
        raise RuntimeError("No email provider configured and OTP_DEBUG_LOG is off — cannot deliver email.")


def _code_template(name: str, code: str, purpose: str, minutes: int) -> tuple[str, str]:
    text = (
        f"Hi {name},\n\n"
        f"{purpose}: {code}\n"
        f"This code expires in {minutes} minutes.\n\n"
        "Agar yeh aap nahi thay, is email ko ignore karein.\n\n"
        "— ASTRA AI"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#0b0f19;padding:32px;color:#e5e7eb">
      <div style="max-width:420px;margin:0 auto;background:#111827;border-radius:16px;padding:28px;">
        <p style="font-size:13px;color:#9ca3af;margin:0 0 4px">ASTRA AI · {purpose}</p>
        <p style="font-size:14px;margin:0 0 20px">Hi {name}, use this code to continue:</p>
        <div style="font-size:32px;font-weight:700;letter-spacing:6px;color:#a78bfa;
                    background:#1f2937;border-radius:12px;padding:16px;text-align:center;">
          {code}
        </div>
        <p style="font-size:12px;color:#6b7280;margin-top:20px">
          Expires in {minutes} minutes. Agar yeh aap nahi thay, ignore kar dein.
        </p>
      </div>
    </div>
    """
    return text, html


def send_otp_email(to_email: str, name: str, code: str) -> None:
    text, html = _code_template(name, code, "Your ASTRA AI login verification code", settings.OTP_EXPIRE_MINUTES)
    send_html_email(to_email, f"Your ASTRA AI verification code: {code}", text, html)


def send_password_reset_email(to_email: str, name: str, code: str) -> None:
    text, html = _code_template(name, code, "Your ASTRA AI password reset code", settings.OTP_EXPIRE_MINUTES)
    send_html_email(to_email, f"ASTRA AI password reset code: {code}", text, html)
