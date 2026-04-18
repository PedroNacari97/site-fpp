"""
Servicos de calculo de KPIs financeiros do SaaS NCfly.

Todos os KPIs aqui sao apresentados ao superadmin em /ncadm/financeiro/.
As queries usam select_related para evitar N+1 quando necessario.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from onboarding.models import Assinatura, Pagamento


STATUS_ASSINATURA_ATIVA = ("trial", "ativa")


def _start_of_month(ref: date) -> date:
    return ref.replace(day=1)


def _end_of_month(ref: date) -> date:
    if ref.month == 12:
        return ref.replace(day=31)
    return ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)


def _months_back(ref: date, n: int) -> date:
    year = ref.year
    month = ref.month - n
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def calcular_mrr_atual() -> Decimal:
    """MRR contratado: soma do preco_mensal das assinaturas ativas ou em trial."""
    total = (
        Assinatura.objects.filter(status__in=STATUS_ASSINATURA_ATIVA)
        .select_related("plano")
        .aggregate(mrr=Sum("plano__preco_mensal"))
    )["mrr"]
    return total or Decimal("0.00")


def calcular_churn_mes(ref: date | None = None) -> dict:
    """
    Churn rate do mes de referencia.
    Formula: canceladas no mes / ativas no inicio do mes.
    Retorna {"canceladas": int, "base_inicial": int, "taxa_pct": Decimal}.
    """
    if ref is None:
        ref = timezone.now().date()
    inicio_mes = _start_of_month(ref)
    fim_mes = _end_of_month(ref)

    canceladas = Assinatura.objects.filter(
        status="cancelada",
        cancelada_em__date__gte=inicio_mes,
        cancelada_em__date__lte=fim_mes,
    ).count()

    # Base inicial: assinaturas que estavam ativas no inicio do mes.
    # Aproximacao: criadas antes do inicio do mes e nao canceladas antes do inicio do mes.
    base_inicial = Assinatura.objects.filter(
        criado_em__date__lt=inicio_mes,
    ).exclude(
        status="cancelada",
        cancelada_em__date__lt=inicio_mes,
    ).count()

    if base_inicial == 0:
        taxa = Decimal("0.00")
    else:
        taxa = (Decimal(canceladas) / Decimal(base_inicial) * Decimal("100")).quantize(Decimal("0.01"))

    return {"canceladas": canceladas, "base_inicial": base_inicial, "taxa_pct": taxa}


def calcular_lifetime_value_medio() -> Decimal:
    """
    LTV medio (aproximacao): total pago confirmado / clientes unicos que ja pagaram.
    Nao e o LTV teorico (1/churn * ARPU), e o realizado ate hoje.
    """
    agregado = Pagamento.objects.filter(status="confirmado").aggregate(
        total=Sum("valor"),
        clientes=Count("assinatura__empresa", distinct=True),
    )
    total = agregado.get("total") or Decimal("0.00")
    clientes = agregado.get("clientes") or 0
    if clientes == 0:
        return Decimal("0.00")
    return (total / Decimal(clientes)).quantize(Decimal("0.01"))


def calcular_inadimplencia_valor(dias: int = 7) -> Decimal:
    """Soma de pagamentos pendentes ha mais de N dias."""
    limite = timezone.now() - timedelta(days=dias)
    total = Pagamento.objects.filter(
        status="pendente", criado_em__lte=limite
    ).aggregate(total=Sum("valor"))["total"]
    return total or Decimal("0.00")


def serie_mrr_6m(ref: date | None = None) -> list[dict]:
    """
    Serie historica do MRR nos ultimos 6 meses.
    Aproximacao: para cada mes, considera as assinaturas que estavam
    ativas/trial no ultimo dia daquele mes.
    """
    if ref is None:
        ref = timezone.now().date()
    serie: list[dict] = []
    for n in range(5, -1, -1):
        base = _months_back(ref, n)
        fim = _end_of_month(base)
        qs = Assinatura.objects.filter(
            criado_em__date__lte=fim,
            status__in=STATUS_ASSINATURA_ATIVA,
        ).exclude(
            cancelada_em__date__lte=fim,
        ).select_related("plano")
        mrr = qs.aggregate(total=Sum("plano__preco_mensal"))["total"] or Decimal("0.00")
        serie.append({"mes": f"{base.year:04d}-{base.month:02d}", "mrr": mrr})
    return serie


def serie_pagamentos_6m(ref: date | None = None) -> list[dict]:
    """Serie de pagamentos confirmados por mes nos ultimos 6 meses."""
    if ref is None:
        ref = timezone.now().date()
    serie: list[dict] = []
    for n in range(5, -1, -1):
        base = _months_back(ref, n)
        inicio = _start_of_month(base)
        fim = _end_of_month(base)
        total = Pagamento.objects.filter(
            status="confirmado",
            criado_em__date__gte=inicio,
            criado_em__date__lte=fim,
        ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")
        serie.append({"mes": f"{base.year:04d}-{base.month:02d}", "total": total})
    return serie


def build_financeiro_dashboard_context() -> dict:
    """Monta o contexto completo do dashboard financeiro do superadmin."""
    agora = timezone.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    proximos_7d = agora + timedelta(days=7)

    totais_status = Assinatura.objects.values("status").annotate(total=Count("id"))
    status_map = {item["status"]: item["total"] for item in totais_status}

    mrr = calcular_mrr_atual()

    pagamentos_confirmados_mes = Pagamento.objects.filter(
        status="confirmado", criado_em__gte=inicio_mes
    ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    pagamentos_pendentes = Pagamento.objects.filter(status="pendente").count()

    trials_expirando = Assinatura.objects.filter(
        status="trial",
        trial_fim__isnull=False,
        trial_fim__gte=agora,
        trial_fim__lte=proximos_7d,
    ).select_related("empresa", "plano").order_by("trial_fim")

    ultimos_pagamentos = Pagamento.objects.select_related(
        "assinatura__empresa", "assinatura__plano"
    ).order_by("-criado_em")[:10]

    churn = calcular_churn_mes()
    ltv = calcular_lifetime_value_medio()
    inadimplencia_valor = calcular_inadimplencia_valor()
    mrr_6m = serie_mrr_6m()
    pagamentos_6m = serie_pagamentos_6m()

    # Normalizacao para o grafico SVG: maiores valores dos dois series.
    max_mrr = max((item["mrr"] for item in mrr_6m), default=Decimal("0.00")) or Decimal("1.00")
    max_pag = max((item["total"] for item in pagamentos_6m), default=Decimal("0.00")) or Decimal("1.00")
    for item in mrr_6m:
        item["pct"] = float((item["mrr"] / max_mrr) * Decimal("100"))
    for item in pagamentos_6m:
        item["pct"] = float((item["total"] / max_pag) * Decimal("100"))

    return {
        "menu_ativo": "financeiro",
        "total_assinaturas": sum(status_map.values()),
        "total_trial": status_map.get("trial", 0),
        "total_ativa": status_map.get("ativa", 0),
        "total_inadimplente": status_map.get("inadimplente", 0),
        "total_suspensa": status_map.get("suspensa", 0),
        "total_cancelada": status_map.get("cancelada", 0),
        "mrr": mrr,
        "pagamentos_confirmados_mes": pagamentos_confirmados_mes,
        "pagamentos_pendentes": pagamentos_pendentes,
        "trials_expirando": trials_expirando,
        "ultimos_pagamentos": ultimos_pagamentos,
        "churn_rate_mes": churn["taxa_pct"],
        "churn_canceladas": churn["canceladas"],
        "churn_base": churn["base_inicial"],
        "lifetime_value_medio": ltv,
        "inadimplencia_valor": inadimplencia_valor,
        "mrr_serie_6m": mrr_6m,
        "pagamentos_serie_6m": pagamentos_6m,
    }
