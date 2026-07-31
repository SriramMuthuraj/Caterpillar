import os

from dotenv import load_dotenv

# load_dotenv() with no argument resolves .env against the *current working
# directory*, so it only found the file when you happened to run from inside
# alert/. Point it at the file next to this module instead, so importing the
# package from the repo root picks up the same settings.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


class SMTPConfig:

    SERVER = os.getenv("SMTP_SERVER")

    # int(os.getenv("SMTP_PORT")) raised TypeError at *import* time whenever the
    # variable was unset, which took down anything that merely imported this
    # module. 587 is the submission port for STARTTLS.
    PORT = int(os.getenv("SMTP_PORT") or 587)

    EMAIL = os.getenv("SMTP_EMAIL")
    PASSWORD = os.getenv("SMTP_PASSWORD")

    TLS = os.getenv("SMTP_TLS", "True") == "True"

    # Sending is opt-in. The demo has to run with the network disabled, and a
    # blocking SMTP handshake on a request thread is the kind of thing that
    # hangs a live demo. Set ALERTS_ENABLED=true to actually deliver.
    ENABLED = os.getenv("ALERTS_ENABLED", "false").lower() in ("1", "true", "yes")

    @classmethod
    def is_configured(cls):
        """True when there is enough here to attempt a real send."""
        return bool(cls.SERVER and cls.EMAIL and cls.PASSWORD)
