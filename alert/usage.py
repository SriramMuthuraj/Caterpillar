"""Manual smoke test for the email client.

This used to send a real email at *import* time, so merely importing the module
delivered a message. It is now behind a __main__ guard and dry-runs by default::

    python -m alert.usage                       # builds the message, sends nothing
    ALERTS_ENABLED=true python -m alert.usage   # actually delivers
"""

try:
    from .email_client import EmailClient
except ImportError:
    from email_client import EmailClient


if __name__ == "__main__":
    client = EmailClient()
    result = client.send_email(
        receiver="laravindakrishnan@gmail.com",
        subject="Welcome",
        html="<h1>Hello</h1>",
    )
    print(result)
