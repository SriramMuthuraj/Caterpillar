import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:                                    # imported as a package from repo root
    from .config import SMTPConfig
except ImportError:                     # run as a script from inside alert/
    from config import SMTPConfig


class EmailClient:

    def __init__(self, enabled=None):
        self.server = SMTPConfig.SERVER
        self.port = SMTPConfig.PORT
        self.username = SMTPConfig.EMAIL
        self.password = SMTPConfig.PASSWORD
        self.use_tls = SMTPConfig.TLS
        # None means "follow the env"; pass True/False to override per client.
        self.enabled = SMTPConfig.ENABLED if enabled is None else enabled

    def build_message(self, receiver, subject, html=None, text=None):
        message = MIMEMultipart("alternative")
        message["From"] = self.username
        message["To"] = receiver
        message["Subject"] = subject

        if text:
            message.attach(MIMEText(text, "plain"))
        if html:
            message.attach(MIMEText(html, "html"))

        return message

    def send_email(self, receiver, subject, html=None, text=None):
        """Send one message. Returns a dict describing what happened.

        Dry-run unless ``ALERTS_ENABLED`` is set (or ``enabled=True`` was passed
        to the constructor). A dry run builds the message and reports success
        without opening a socket, so callers can be exercised offline and the
        demo never blocks on an SMTP handshake.
        """
        message = self.build_message(receiver, subject, html=html, text=text)

        if not self.enabled:
            return {"sent": False, "reason": "dry_run",
                    "receiver": receiver, "subject": subject}

        if not SMTPConfig.is_configured():
            return {"sent": False, "reason": "smtp_not_configured",
                    "receiver": receiver, "subject": subject}

        try:
            with smtplib.SMTP(self.server, self.port, timeout=10) as smtp:
                if self.use_tls:
                    smtp.starttls()
                smtp.login(self.username, self.password)
                smtp.send_message(message)
        except Exception as exc:
            # A failed alert must not take down the request that triggered it.
            return {"sent": False, "reason": f"{type(exc).__name__}: {exc}",
                    "receiver": receiver, "subject": subject}

        return {"sent": True, "reason": "delivered",
                "receiver": receiver, "subject": subject}
