"""Email service: send real SMTP emails or fall back to console logging + dev outbox."""
from __future__ import annotations

import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# In-memory dev outbox
_outbox: list[dict] = []


def _send_smtp(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(settings.smtp_from, [to], msg.as_string())


def send_email(to: str, subject: str, html: str) -> None:
    if settings.smtp_host and settings.smtp_user:
        try:
            _send_smtp(to, subject, html)
            return
        except Exception as exc:
            logger.warning("SMTP failed (%s); falling back to dev outbox", exc)

    # Dev mode: log to console and store in outbox
    logger.info(
        "\n" + "=" * 60 +
        f"\n📧  DEV EMAIL\n  To: {to}\n  Subject: {subject}\n\n{html}\n" +
        "=" * 60
    )
    _outbox.append({
        "id": len(_outbox) + 1,
        "to": to,
        "subject": subject,
        "html": html,
        "sent_at": datetime.utcnow().isoformat(),
    })


def get_outbox() -> list[dict]:
    return list(reversed(_outbox))


def send_password_reset(to: str, reset_url: str, name: str) -> None:
    html = f"""
    <h2>Password Reset — Brightloop</h2>
    <p>Hi {name},</p>
    <p>Click the link below to reset your password. This link expires in 30 minutes and can only be used once.</p>
    <p><a href="{reset_url}" style="padding:10px 20px;background:#6366f1;color:white;border-radius:6px;text-decoration:none;">
       Reset Password
    </a></p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    <p><strong>Reset link:</strong> <code>{reset_url}</code></p>
    """
    send_email(to, "Reset your Brightloop password", html)


def send_invoice_email(to: str, customer_name: str, invoice_number: str) -> None:
    html = f"""
    <h2>Invoice {invoice_number} — Brightloop Software</h2>
    <p>Hi {customer_name},</p>
    <p>Your invoice <strong>{invoice_number}</strong> has been issued. Please log in to your portal to view and pay.</p>
    <p><a href="{settings.frontend_url}/portal/invoices" style="padding:10px 20px;background:#6366f1;color:white;border-radius:6px;text-decoration:none;">
       View Invoice
    </a></p>
    """
    send_email(to, f"Invoice {invoice_number} from Brightloop Software", html)
