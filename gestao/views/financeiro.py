"""
Views do painel /adm/financeiro/ — lado agencia.

A agencia logada ve sua propria assinatura, historico de pagamentos,
download de contrato aceito e (placeholder) download de NF-e.

Isolamento multi-tenant: todos os querysets filtram por
assinatura.empresa == request.user.cliente_gestao.empresa.
Nunca confie em ID de URL.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from onboarding.models import Assinatura, Pagamento

from .permissions import get_request_empresa, require_admin_or_operator

logger = logging.getLogger(__name__)


def _get_assinatura_da_empresa(request):
    """
    Retorna a Assinatura da empresa do usuario logado, ou None.
    Sempre filtra por empresa — nunca aceita ID da URL.
    """
    empresa = get_request_empresa(request)
    if empresa is None:
        return None
    return (
        Assinatura.objects.select_related("plano", "empresa")
        .filter(empresa=empresa)
        .first()
    )


@login_required
def financeiro_empresa(request):
    if (denied := require_admin_or_operator(request)):
        return denied

    empresa = get_request_empresa(request)
    assinatura = _get_assinatura_da_empresa(request)

    if assinatura is None:
        context = {
            "menu_ativo": "financeiro",
            "empresa": empresa,
            "assinatura": None,
        }
        return render(request, "admin_custom/financeiro.html", context)

    ultimos_pagamentos = (
        Pagamento.objects.select_related("assinatura__empresa")
        .filter(assinatura__empresa=empresa)
        .order_by("-criado_em")[:3]
    )

    total_pago_empresa = (
        Pagamento.objects.filter(
            assinatura__empresa=empresa, status="confirmado"
        ).aggregate(total=Sum("valor"))["total"]
        or Decimal("0.00")
    )

    agora = timezone.now()
    dias_trial = assinatura.dias_restantes_trial if assinatura.status == "trial" else 0

    context = {
        "menu_ativo": "financeiro",
        "empresa": empresa,
        "assinatura": assinatura,
        "ultimos_pagamentos": ultimos_pagamentos,
        "total_pago_empresa": total_pago_empresa,
        "dias_trial": dias_trial,
        "now": agora,
    }
    return render(request, "admin_custom/financeiro.html", context)


@login_required
def financeiro_empresa_pagamentos(request):
    if (denied := require_admin_or_operator(request)):
        return denied

    empresa = get_request_empresa(request)
    if empresa is None:
        raise Http404("Empresa nao encontrada para o usuario.")

    doze_meses = timezone.now() - timedelta(days=365)
    qs = (
        Pagamento.objects.select_related("assinatura__plano", "assinatura__empresa")
        .filter(assinatura__empresa=empresa, criado_em__gte=doze_meses)
        .order_by("-criado_em")
    )

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "menu_ativo": "financeiro",
        "empresa": empresa,
        "page_obj": page_obj,
        "total_registros": qs.count(),
    }
    return render(request, "admin_custom/financeiro_pagamentos.html", context)


@login_required
def financeiro_empresa_contrato(request):
    """
    Placeholder seguro para download de contrato.

    Hoje o sistema ainda nao tem modelo AceiteContrato persistido;
    quando existir, basta validar empresa == request.user.empresa
    antes de entregar o arquivo. Ate la, retorna 404 gracioso.
    """
    if (denied := require_admin_or_operator(request)):
        return denied

    empresa = get_request_empresa(request)
    if empresa is None:
        raise Http404("Empresa nao encontrada para o usuario.")

    # Futuro: buscar AceiteContrato filtrado por empresa
    # aceite = AceiteContrato.objects.filter(empresa=empresa).first()
    # if aceite and aceite.arquivo:
    #     logger.info(
    #         "Download de contrato LGPD audit: user=%s empresa=%s ts=%s",
    #         request.user.email, empresa.nome, timezone.now().isoformat(),
    #     )
    #     return FileResponse(aceite.arquivo.open("rb"), as_attachment=True)

    logger.info(
        "Tentativa de download de contrato: user=%s empresa=%s (ainda nao disponivel)",
        request.user.email, empresa.nome,
    )
    messages.info(
        request,
        "Seu contrato ainda nao esta disponivel para download. "
        "Solicite uma via ao suporte em financeiro@ncfly.com.br.",
    )
    return redirect(reverse("admin_financeiro"))
