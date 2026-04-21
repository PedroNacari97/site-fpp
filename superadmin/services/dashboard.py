"""
Servico agregador do dashboard principal /ncadm/.

Consolida em um unico modulo todos os KPIs operacionais+financeiros+fiscais
que o painel /ncadm/ exibe. Cada bloco e isolado em funcao propria para
permitir cache parcial e recuperacao graciosa em caso de falha.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from gestao.models import Empresa
from portal.models import (
    ArtigoEstudo,
    ComentarioArtigo,
    JobExecucao,
    LeadAlertaEmail,
    LeadPlataforma,
    NoticiaPublicada,
    PortalMetricDaily,
    PortalUser,
)

from superadmin.models import CustoOperacional, ObrigacaoFiscal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Health strip — alertas operacionais em vermelho
# ---------------------------------------------------------------------------

def _health_strip(agora) -> dict:
    """Indicadores que so aparecem se houver algo a fazer."""
    ultimas_24h = agora - timedelta(hours=24)

    jobs = JobExecucao.objects.filter(horario__gte=ultimas_24h).aggregate(
        falhas=Count("id", filter=Q(status="failed")),
        parciais=Count("id", filter=Q(status="partial")),
        total=Count("id"),
    )

    # Monitor de passagens: ha job de monitor rodando nas ultimas 2h?
    monitor_ok = JobExecucao.objects.filter(
        job_name__icontains="monitor",
        horario__gte=agora - timedelta(hours=2),
        status__in=("success", "running", "partial"),
    ).exists()

    coment_pendentes = ComentarioArtigo.objects.filter(
        status=ComentarioArtigo.STATUS_OCULTO_ADMIN,
    ).count()

    return {
        "jobs_falhas_24h": jobs["falhas"] or 0,
        "jobs_parciais_24h": jobs["parciais"] or 0,
        "jobs_total_24h": jobs["total"] or 0,
        "monitor_passagens_ok": monitor_ok,
        "comentarios_ocultos": coment_pendentes,
        "tem_alerta": bool(
            (jobs["falhas"] or 0) > 0
            or not monitor_ok
            or coment_pendentes > 0
        ),
    }


# ---------------------------------------------------------------------------
# Crescimento — funil B2C + B2B em UMA consulta por dominio
# ---------------------------------------------------------------------------

def _crescimento(agora) -> dict:
    ultimas_24h = agora - timedelta(hours=24)
    ultimos_7d = agora - timedelta(days=7)
    ultimos_30d = agora - timedelta(days=30)

    portal_users = PortalUser.objects.aggregate(
        total=Count("id"),
        ativos=Count("id", filter=Q(ativo=True)),
        novos_24h=Count("id", filter=Q(criado_em__gte=ultimas_24h)),
        novos_7d=Count("id", filter=Q(criado_em__gte=ultimos_7d)),
        com_google=Count("id", filter=Q(google_sub__gt="")),
    )

    comentarios = ComentarioArtigo.objects.aggregate(
        total=Count("id"),
        publicados=Count("id", filter=Q(status=ComentarioArtigo.STATUS_PUBLICADO)),
        novos_24h=Count("id", filter=Q(criado_em__gte=ultimas_24h)),
        novos_7d=Count("id", filter=Q(criado_em__gte=ultimos_7d)),
    )

    leads_plat = LeadPlataforma.objects.aggregate(
        total=Count("id"),
        novos=Count("id", filter=Q(status="novo")),
        qualificados=Count("id", filter=Q(status="qualificado")),
        recentes_30d=Count("id", filter=Q(criado_em__gte=ultimos_30d)),
    )
    total_pipeline = max((leads_plat["recentes_30d"] or 0), 1)
    taxa_qualificacao = round(
        (leads_plat["qualificados"] or 0) * 100 / total_pipeline, 1,
    ) if (leads_plat["recentes_30d"] or 0) > 0 else 0.0

    alertas = LeadAlertaEmail.objects.aggregate(
        total=Count("id"),
        ativos=Count("id", filter=Q(status=LeadAlertaEmail.STATUS_ATIVO)),
        novos_7d=Count(
            "id",
            filter=Q(
                status=LeadAlertaEmail.STATUS_ATIVO,
                criado_em__gte=ultimos_7d,
            ),
        ),
    )

    noticias = NoticiaPublicada.objects.aggregate(
        total=Count("id"),
        publicadas=Count("id", filter=Q(status="published")),
        rascunho=Count("id", filter=Q(status="draft")),
        publ_24h=Count(
            "id",
            filter=Q(status="published", criada_em__gte=ultimas_24h),
        ),
    )

    return {
        "portal_users": portal_users,
        "comentarios": comentarios,
        "leads_plataforma": leads_plat,
        "taxa_qualificacao_pct": taxa_qualificacao,
        "alertas_email": alertas,
        "noticias": noticias,
    }


# ---------------------------------------------------------------------------
# Trafego — PortalMetricDaily
# ---------------------------------------------------------------------------

def _trafego(agora) -> dict:
    hoje = agora.date()
    ontem = hoje - timedelta(days=1)
    ultimos_7d = hoje - timedelta(days=6)
    ultimos_30d = hoje - timedelta(days=29)

    agg_7d = PortalMetricDaily.objects.filter(
        metric_type="page_view",
        metric_date__gte=ultimos_7d,
    ).aggregate(total=Sum("total"))
    agg_30d = PortalMetricDaily.objects.filter(
        metric_type="page_view",
        metric_date__gte=ultimos_30d,
    ).aggregate(total=Sum("total"))
    agg_hoje = PortalMetricDaily.objects.filter(
        metric_type="page_view",
        metric_date=hoje,
    ).aggregate(total=Sum("total"))
    agg_ontem = PortalMetricDaily.objects.filter(
        metric_type="page_view",
        metric_date=ontem,
    ).aggregate(total=Sum("total"))

    return {
        "page_views_hoje": agg_hoje["total"] or 0,
        "page_views_ontem": agg_ontem["total"] or 0,
        "page_views_7d": agg_7d["total"] or 0,
        "page_views_30d": agg_30d["total"] or 0,
    }


# ---------------------------------------------------------------------------
# Financeiro — puxa do service existente + custos
# ---------------------------------------------------------------------------

def _financeiro_resumo(agora) -> dict:
    """Resumo financeiro para o topo do dashboard (apenas os 3-4 numeros vitais)."""
    try:
        from superadmin.services.financeiro import (
            calcular_mrr_atual,
            calcular_inadimplencia_valor,
        )
        from onboarding.models import Assinatura, Pagamento

        mrr = calcular_mrr_atual()
        inadimplencia = calcular_inadimplencia_valor()
        assinaturas = Assinatura.objects.aggregate(
            ativas=Count("id", filter=Q(status="ativa")),
            trial=Count("id", filter=Q(status="trial")),
        )
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pag_mes = Pagamento.objects.filter(
            status="confirmado", criado_em__gte=inicio_mes,
        ).aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

        return {
            "mrr": mrr,
            "assinaturas_ativas": assinaturas["ativas"] or 0,
            "assinaturas_trial": assinaturas["trial"] or 0,
            "pagamentos_mes_atual": pag_mes,
            "inadimplencia_valor": inadimplencia,
            "disponivel": True,
        }
    except Exception:
        logger.exception("Falha ao calcular resumo financeiro para dashboard.")
        return {"disponivel": False}


def _custos_resumo(agora) -> dict:
    """Custos do mes + projecao anual + margem bruta quando houver receita."""
    hoje = agora.date()
    mes_atual = hoje.replace(day=1)
    mes_anterior = (mes_atual - timedelta(days=1)).replace(day=1)

    agg_atual = CustoOperacional.objects.filter(
        mes_referencia=mes_atual,
    ).aggregate(
        total=Sum("valor_brl"),
        iof=Sum("iof"),
        infra=Sum("valor_brl", filter=Q(categoria=CustoOperacional.CATEGORIA_INFRA)),
        ia=Sum("valor_brl", filter=Q(categoria=CustoOperacional.CATEGORIA_IA)),
    )
    agg_anterior = CustoOperacional.objects.filter(
        mes_referencia=mes_anterior,
    ).aggregate(total=Sum("valor_brl"))

    total_atual = agg_atual["total"] or Decimal("0.00")
    total_anterior = agg_anterior["total"] or Decimal("0.00")
    delta = total_atual - total_anterior

    # Acumulado no ano corrente
    jan_1 = date(hoje.year, 1, 1)
    acumulado = CustoOperacional.objects.filter(
        mes_referencia__gte=jan_1,
    ).aggregate(total=Sum("valor_brl"))["total"] or Decimal("0.00")

    return {
        "mes_atual": total_atual,
        "mes_anterior": total_anterior,
        "delta": delta,
        "iof_mes": agg_atual["iof"] or Decimal("0.00"),
        "infra_mes": agg_atual["infra"] or Decimal("0.00"),
        "ia_mes": agg_atual["ia"] or Decimal("0.00"),
        "acumulado_ano": acumulado,
    }


def _fiscal_resumo(agora) -> dict:
    """Obrigacoes vencendo nos proximos 30d + atrasadas."""
    hoje = agora.date()
    em_30d = hoje + timedelta(days=30)
    qs = (
        ObrigacaoFiscal.objects.exclude(status=ObrigacaoFiscal.STATUS_PAGA)
        .filter(vencimento__lte=em_30d)
        .order_by("vencimento")
    )
    proximas = list(qs[:5])
    atrasadas = [o for o in proximas if o.vencimento < hoje]
    return {
        "proximas": proximas,
        "total_atrasadas": sum(1 for _ in atrasadas),
        "total_a_vencer": len(proximas) - len(atrasadas),
    }


# ---------------------------------------------------------------------------
# Listas: ultimas noticias/jobs/comentarios
# ---------------------------------------------------------------------------

def _listas(agora) -> dict:
    ultimas_noticias = list(
        NoticiaPublicada.objects.select_related("fonte")
        .order_by("-criada_em")[:5]
    )
    ultimos_jobs = list(JobExecucao.objects.order_by("-horario")[:5])
    comentarios_recentes = list(
        ComentarioArtigo.objects.filter(
            status=ComentarioArtigo.STATUS_PUBLICADO,
        )
        .select_related("artigo", "artigo__modulo")
        .order_by("-criado_em")[:5]
    )
    return {
        "ultimas_noticias": ultimas_noticias,
        "ultimos_jobs": ultimos_jobs,
        "comentarios_recentes": comentarios_recentes,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def build_dashboard_context() -> dict:
    """Monta o contexto completo do /ncadm/ em uma unica chamada.

    Cada bloco e isolado em try/except para que falha parcial nao quebre
    o painel inteiro.
    """
    agora = timezone.now()
    context = {"menu_ativo": "dashboard", "agora": agora}

    # Cada bloco roda isolado — falha num nao derruba os outros
    for key, func in (
        ("health", _health_strip),
        ("crescimento", _crescimento),
        ("trafego", _trafego),
        ("financeiro", _financeiro_resumo),
        ("custos", _custos_resumo),
        ("fiscal", _fiscal_resumo),
        ("listas", _listas),
    ):
        try:
            context[key] = func(agora)
        except Exception:
            logger.exception("Falha ao calcular bloco %s do dashboard /ncadm/", key)
            context[key] = {"erro": True}

    # Atalho para o template (evita .health.tem_alerta em todo lugar)
    health = context.get("health") or {}
    context["tem_alerta_operacional"] = bool(health.get("tem_alerta"))

    return context
