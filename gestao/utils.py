import re
from uuid import uuid4

from django.contrib.auth import get_user_model


def normalize_cpf(cpf: str) -> str:
    """Remove caracteres não numéricos e retorna apenas os 11 dígitos."""

    return re.sub(r"\D", "", cpf or "")


def generate_unique_username(prefix: str = "user") -> str:
    """Gera um username técnico único usando UUID."""

    UserModel = get_user_model()
    while True:
        candidate = f"{prefix}_{uuid4().hex[:10]}"
        if not UserModel.objects.filter(username=candidate).exists():
            return candidate
