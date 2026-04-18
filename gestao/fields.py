"""
Campos Django com criptografia Fernet para dados sensiveis em repouso.

A chave e lida de ``settings.FIELD_ENCRYPTION_KEY`` (variavel de ambiente).
Em dev, se nao configurada e DEBUG=True, usa uma chave fixa (apenas para dev).
"""
import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or os.environ.get("FIELD_ENCRYPTION_KEY", "")
    if not key:
        if settings.DEBUG:
            key = base64.urlsafe_b64encode(b"dev-only-key-32bytes!!!!!!!!!!!!").decode()
        else:
            raise ValueError(
                "FIELD_ENCRYPTION_KEY deve ser configurada em producao. "
                'Gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


class EncryptedCharField(models.CharField):
    """CharField que cifra o valor antes de salvar e decifra ao ler."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 500)
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return value
        f = _get_fernet()
        return f.encrypt(value.encode("utf-8")).decode("utf-8")

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            f = _get_fernet()
            return f.decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, Exception):
            return value

    def value_from_object(self, obj):
        """Retorna o valor decifrado (usado por serializers e forms)."""
        return getattr(obj, self.attname)
