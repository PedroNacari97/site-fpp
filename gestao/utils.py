import re
from datetime import datetime
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.sessions.models import Session
from django.utils import timezone


def normalize_cpf(cpf: str) -> str:
    """Remove caracteres não numéricos e retorna apenas os 11 dígitos."""

    return re.sub(r"\D", "", cpf or "")


def validate_cpf_digits(cpf: str, *, field_label: str = "CPF") -> str:
    """
    Normaliza o CPF e valida se possui exatamente 11 dígitos.

    Levanta ``ValidationError`` com uma mensagem amigável em caso de falha.
    """

    normalized = normalize_cpf(cpf)
    if not normalized:
        raise ValidationError(f"{field_label} é obrigatório.")
    if len(normalized) != 11:
        raise ValidationError(f"{field_label} deve conter exatamente 11 dígitos numéricos.")
    return normalized


def generate_unique_username(prefix: str = "user") -> str:
    """Gera um username técnico único usando UUID."""

    UserModel = get_user_model()
    while True:
        candidate = f"{prefix}_{uuid4().hex[:10]}"
        if not UserModel.objects.filter(username=candidate).exists():
            return candidate


def parse_br_date(value, *, field_label: str = "Data"):
    """Converte datas no formato ``DD/MM/AAAA`` ou ISO (``YYYY-MM-DD``).

    Retorna ``None`` para entradas vazias e lança ``ValidationError`` para
    formatos inválidos.
    """

    if not value:
        return None

    if hasattr(value, "isoformat"):
        return value

    value_str = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value_str, fmt).date()
        except (TypeError, ValueError):
            continue
    raise ValidationError(f"{field_label} deve estar no formato DD/MM/AAAA.")


def revoke_user_sessions(user):
    """Remove todas as sessões ativas do usuário."""

    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    for session in sessions:
        data = session.get_decoded()
        if data.get("_auth_user_id") == str(user.id):
            session.delete()


def sync_cliente_activation(cliente, *, revoke_sessions: bool = True):
    """
    Mantém ``User.is_active`` alinhado ao campo ``Cliente.ativo`` e encerra sessões.
    """

    user = cliente.usuario
    desired_active = bool(cliente.ativo)
    if user.is_active != desired_active:
        user.is_active = desired_active
        user.save(update_fields=["is_active"])
    if not desired_active and revoke_sessions:
        revoke_user_sessions(user)
