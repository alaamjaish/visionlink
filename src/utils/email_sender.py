"""
Email Sender (Gmail SMTP)

Sends plain text emails for:
- Maintenance reports
- Supervisor notifications
- Parts requests
"""

import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent.parent))

import config
from src.utils.logger import get_logger

logger = get_logger("email")


class EmailSender:
    """Sends emails via Gmail SMTP."""

    def setup(self) -> bool:
        """Verify email configuration."""
        if not config.SMTP_EMAIL or not config.SMTP_APP_PASSWORD:
            logger.warning("Email credentials not configured")
            return False
        logger.info("Email sender configured")
        return True

    def send(self, to: str, subject: str, body: str) -> bool:
        """Send a plain text email."""
        if not config.SMTP_EMAIL or not config.SMTP_APP_PASSWORD:
            logger.error("Email not configured")
            return False

        try:
            start = time.time()

            msg = MIMEMultipart()
            msg["From"] = config.SMTP_EMAIL
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_EMAIL, config.SMTP_APP_PASSWORD)
                server.send_message(msg)

            elapsed = time.time() - start
            logger.info(f"Email sent to {to}: '{subject}' ({elapsed:.2f}s)")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}", exc_info=True)
            return False

    def notify_supervisor(self, message: str) -> bool:
        """Send notification to supervisor."""
        return self.send(
            to=config.SUPERVISOR_EMAIL,
            subject="VisionLink - Worker Notification",
            body=message
        )

    def send_maintenance_report(self, report: str) -> bool:
        """Send maintenance report to supervisor."""
        return self.send(
            to=config.SUPERVISOR_EMAIL,
            subject="VisionLink - Maintenance Report",
            body=report
        )

    def send_parts_request(self, parts_info: str) -> bool:
        """Send parts request to supervisor."""
        return self.send(
            to=config.SUPERVISOR_EMAIL,
            subject="VisionLink - Parts Request",
            body=parts_info
        )
