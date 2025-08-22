"""Repositories for data access in the Painel do Cliente."""

from django.shortcuts import get_object_or_404
from gestao.models import ContaFidelidade, EmissaoPassagem, EmissaoHotel


def get_contas_by_user(user):
    """Return fidelity accounts related to a user."""
    return ContaFidelidade.objects.filter(cliente__usuario=user).select_related(
        "programa"
    )


def get_emissoes_passagem_by_user(user):
    """Return flight emissions for the given user."""
    return EmissaoPassagem.objects.filter(cliente__usuario=user)


def get_emissoes_hotel_by_user(user):
    """Return hotel emissions for the given user."""
    return EmissaoHotel.objects.filter(cliente__usuario=user)


def get_conta_by_id_for_user(conta_id, user):
    """Return a specific account ensuring ownership by user."""
    return get_object_or_404(ContaFidelidade, id=conta_id, cliente__usuario=user)


def get_emissao_passagem_for_user(emissao_id, user):
    """Return a specific flight emission for the user."""
    return get_object_or_404(EmissaoPassagem, id=emissao_id, cliente__usuario=user)
