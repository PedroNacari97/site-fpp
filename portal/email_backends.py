import base64
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    """Django email backend backed by the Resend HTTPS API."""

    api_url = "https://api.resend.com/emails"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = str(getattr(settings, "RESEND_API_KEY", "") or "").strip()
        self.timeout = int(getattr(settings, "RESEND_REQUEST_TIMEOUT", 15) or 15)
        self.session = None

    def open(self):
        if self.session is not None:
            return False
        if not self.api_key:
            if self.fail_silently:
                return False
            raise ImproperlyConfigured("Defina RESEND_API_KEY para usar o backend Resend.")

        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
        )
        self.session = session
        return True

    def close(self):
        if self.session is None:
            return
        self.session.close()
        self.session = None

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        try:
            self.open()
        except Exception:
            if not self.fail_silently:
                raise
            return 0
        if self.session is None:
            return 0

        sent_messages = 0
        try:
            for message in email_messages:
                if not message.recipients():
                    continue
                try:
                    self._send(message)
                except Exception:
                    if not self.fail_silently:
                        raise
                    continue
                sent_messages += 1
        finally:
            self.close()
        return sent_messages

    def _send(self, message):
        payload = self._build_payload(message)
        response = self.session.post(
            getattr(settings, "RESEND_API_URL", self.api_url),
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

    def _build_payload(self, message) -> dict[str, Any]:
        html_body = ""
        for alternative in getattr(message, "alternatives", []) or []:
            if getattr(alternative, "mimetype", "") == "text/html":
                html_body = alternative.content
                break
            if isinstance(alternative, (list, tuple)) and len(alternative) >= 2 and alternative[1] == "text/html":
                html_body = alternative[0]
                break

        payload: dict[str, Any] = {
            "from": str(message.from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip(),
            "to": list(message.to or []),
            "subject": str(message.subject or ""),
            "text": str(message.body or ""),
        }
        if html_body:
            payload["html"] = html_body
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)
        if message.extra_headers:
            payload["headers"] = {
                str(key): str(value)
                for key, value in message.extra_headers.items()
                if value is not None
            }
        attachments = self._build_attachments(message)
        if attachments:
            payload["attachments"] = attachments
        return payload

    def _build_attachments(self, message) -> list[dict[str, str]]:
        attachments = []
        for attachment in getattr(message, "attachments", []) or []:
            if isinstance(attachment, tuple):
                filename, content = (
                    attachment[0],
                    attachment[1],
                )
            else:
                filename = getattr(attachment, "name", "")
                content = getattr(attachment, "content", b"")

            if isinstance(content, bytes):
                content = base64.b64encode(content).decode("ascii")
            attachments.append(
                {
                    "filename": str(filename),
                    "content": str(content),
                }
            )
        return attachments
