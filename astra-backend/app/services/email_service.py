"""
EmailService
------------
Sends the 2FA OTP code over real SMTP (stdlib smtplib — no extra dependency
needed). Fill SMTP_* in .env with your provider's credentials:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USERNAME=you@gmail.com
    SMTP_PASSWORD=your-app-password        # Gmail: use an "App Password", not your normal password
    SMTP_FROM_EMAIL=you@gmail.com
    SMTP_FROM_NAME=ASTRA AI
    SMTP_USE_TLS=true

Never commit real values in .env — it's already covered by .gitignore.
If SMTP_HOST is left empty (e.g. fresh dev checkout), sending is skipped and
the code is only logged to the console when OTP_DEBUG_LOG=true, so local
dev keeps working without real credentials.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("astra.email")


def _build_otp_email(to_email: str, name: str, code: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your ASTRA AI verification code: {code}"
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    text = (
        f"Hi {name},\n\n"
        f"Your ASTRA AI login verification code is: {code}\n"
        f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.\n\n"
        "Agar yeh aap nahi thay, is email ko ignore karein.\n\n"
        "— ASTRA AI"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#0b0f19;padding:32px;color:#e5e7eb">
      <div style="max-width:420px;margin:0 auto;background:#111827;border-radius:16px;padding:28px;">
        <p style="font-size:13px;color:#9ca3af;margin:0 0 4px">ASTRA AI · Verification code</p>
        <p style="font-size:14px;margin:0 0 20px">Hi {name}, use this code to finish signing in:</p>
        <div style="font-size:32px;font-weight:700;letter-spacing:6px;color:#a78bfa;
                    background:#1f2937;border-radius:12px;padding:16px;text-align:center;">
          {code}
        </div>
        <p style="font-size:12px;color:#6b7280;margin-top:20px">
          Expires in {settings.OTP_EXPIRE_MINUTES} minutes. Agar yeh aap nahi thay, ignore kar dein.
        </p>
      </div>
    </div>
    """
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_otp_email(to_email: str, name: str, code: str) -> None:
    if settings.OTP_DEBUG_LOG:
        # Dev convenience only — remove/disable (OTP_DEBUG_LOG=false) in production
        # so codes never land in logs. Uses print() (not just logger.info) so it
        # shows up even when uvicorn's default logging config filters INFO
        # from app-level loggers.
        logger.info("[DEV OTP] %s -> code=%s (expires in %sm)", to_email, code, settings.OTP_EXPIRE_MINUTES)
        print(f"[DEV OTP] {to_email} -> code={code} (expires in {settings.OTP_EXPIRE_MINUTES}m)", flush=True)

    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        # No SMTP configured yet — dev mode falls back to console-only above.
        if not settings.OTP_DEBUG_LOG:
            raise RuntimeError("SMTP is not configured and OTP_DEBUG_LOG is off — cannot deliver OTP.")
        return

    msg = _build_otp_email(to_email, name, code)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
