from django.conf import settings
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from accounts.access import user_has_admin_panel_access
from gestao.models import AlertaViagem
from portal.models import JobExecucao, LeadPlataforma, NoticiaPublicada, PortalMetricDaily
from portal.services.public_alerts import list_visible_public_alerts


SECTION_LABELS = {
    "home": "Home",
    "article": "Noticias",
    "category": "Categorias",
    "alerts": "Alertas publicos",
    "saas": "Plataforma NC Fly",
    "saas_contact": "Contato da plataforma",
    "static": "Paginas institucionais",
}

CLICK_EVENT_LABELS = {
    "click_brand_publica": "Marca do portal",
    "click_categoria": "Categoria",
    "click_topico_categoria": "Topico da categoria",
    "click_noticia_destaque": "Noticia destaque",
    "click_noticia_card": "Card de noticia",
    "click_noticia_relacionada": "Noticia relacionada",
    "click_cta_home": "CTA da home",
    "click_cta_categoria": "CTA da categoria",
    "click_saas_teaser": "Teaser da plataforma",
    "click_cta_saas": "CTA da plataforma",
    "click_offer_link": "CTA de oferta",
    "click_carregar_mais_noticias": "Carregar mais noticias",
    "click_breadcrumb": "Breadcrumb",
    "click_voltar_noticias": "Voltar para noticias",
    "click_busca_publica": "Busca publica",
}

LEAD_STATUS_TONES = {
    "novo": "operator",
    "contatado": "admin",
    "qualificado": "success",
    "arquivado": "muted",
}

JOB_STATUS_TONES = {
    "running": "operator",
    "success": "success",
    "partial": "warning",
    "failed": "danger",
}


def _require_superadmin(request):
    if not request.user.is_superuser or not user_has_admin_panel_access(request.user):
        return render(request, "sem_permissao.html")
    return None


def _parse_date_input(raw_value, fallback):
    try:
        return date.fromisoformat(str(raw_value or "").strip())
    except ValueError:
        return fallback


def _format_date_label(value):
    return value.strftime("%d/%m/%Y")


def _format_path_label(path):
    clean_path = str(path or "").strip()
    if not clean_path:
        return "Sem pagina"

    mapping = {
        "/home/": "Home",
        "/home/alertas/": "Alertas de passagens",
        "/home/plataforma/": "Plataforma NC Fly",
        "/home/plataforma/contato/": "Contato da plataforma",
        "/home/sobre-nos/": "Sobre nos",
        "/home/politica-de-privacidade/": "Politica de privacidade",
        "/home/termos-de-uso/": "Termos de uso",
    }
    if clean_path in mapping:
        return mapping[clean_path]
    if clean_path.startswith("/home/categorias/"):
        slug = clean_path.rstrip("/").split("/")[-1]
        return f"Categoria {slug.replace('-', ' ').title()}"
    if clean_path.startswith("/home/alertas/"):
        return "Detalhe de alerta"
    if clean_path.startswith("/home/") and clean_path.count("/") > 2:
        return clean_path.replace("/home/", "").strip("/").replace("-", " ").title()
    return clean_path


def _format_event_label(event_name):
    normalized = str(event_name or "").strip()
    if not normalized:
        return "Sem evento"
    if normalized in CLICK_EVENT_LABELS:
        return CLICK_EVENT_LABELS[normalized]
    return normalized.replace("click_", "").replace("_", " ").capitalize()


def _format_section_label(section):
    normalized = str(section or "").strip()
    if not normalized:
        return "Sem secao"
    return SECTION_LABELS.get(normalized, normalized.replace("_", " ").capitalize())


def _build_lead_status_items(queryset):
    status_map = dict(LeadPlataforma.STATUS_CHOICES)
    counts = {key: 0 for key, _ in LeadPlataforma.STATUS_CHOICES}
    for item in queryset.values("status").annotate(total_count=Count("id")):
        counts[item["status"]] = item["total_count"]
    return [
        {
            "label": status_map[key],
            "value": counts[key],
            "tone": LEAD_STATUS_TONES.get(key, "muted"),
        }
        for key, _ in LeadPlataforma.STATUS_CHOICES
    ]


def _build_top_pages(queryset):
    rows = (
        queryset.filter(metric_type="page_view")
        .exclude(path="")
        .values("path", "section")
        .annotate(total_sum=Sum("total"))
        .order_by("-total_sum", "path")[:8]
    )
    items = []
    for row in rows:
        path = row["path"]
        items.append(
            {
                "label": _format_path_label(path),
                "path": path,
                "section": _format_section_label(row["section"]),
                "total": row["total_sum"] or 0,
            }
        )
    return items


def _build_top_clicks(queryset):
    rows = (
        queryset.filter(metric_type="click")
        .exclude(event_name="")
        .values("event_name", "section")
        .annotate(total_sum=Sum("total"))
        .order_by("-total_sum", "event_name")[:8]
    )
    items = []
    for row in rows:
        items.append(
            {
                "label": _format_event_label(row["event_name"]),
                "section": _format_section_label(row["section"]),
                "total": row["total_sum"] or 0,
            }
        )
    return items


def _build_top_articles(queryset):
    rows = (
        queryset.filter(metric_type="page_view")
        .exclude(article_slug="")
        .values("article_slug", "article_category", "article_topic")
        .annotate(total_sum=Sum("total"))
        .order_by("-total_sum", "article_slug")[:8]
    )
    slugs = [row["article_slug"] for row in rows]
    news_map = {
        item.slug: item
        for item in NoticiaPublicada.objects.filter(slug__in=slugs).only("slug", "titulo")
    }
    items = []
    for row in rows:
        article = news_map.get(row["article_slug"])
        items.append(
            {
                "title": getattr(article, "titulo", None) or row["article_slug"].replace("-", " ").title(),
                "slug": row["article_slug"],
                "category": row["article_category"] or "-",
                "topic": row["article_topic"] or "-",
                "total": row["total_sum"] or 0,
                "url": article.get_absolute_url() if article else reverse("portal_noticia_redirect", kwargs={"slug": row["article_slug"]}),
            }
        )
    return items


@login_required
def monitoramento_site(request):
    if (permission_denied := _require_superadmin(request)):
        return permission_denied

    today = timezone.localdate()
    default_start = today - timedelta(days=29)
    period_start = _parse_date_input(request.GET.get("inicio"), default_start)
    period_end = _parse_date_input(request.GET.get("fim"), today)
    if period_start > period_end:
        period_start, period_end = period_end, period_start

    current_environment = (getattr(settings, "SITE_ENVIRONMENT", "local") or "local").strip().lower()
    metrics_period = PortalMetricDaily.objects.filter(
        metric_date__range=(period_start, period_end),
        site_environment=current_environment,
    )
    page_views_total = (
        metrics_period.filter(metric_type="page_view").aggregate(total_sum=Sum("total"))["total_sum"] or 0
    )
    clicks_total = (
        metrics_period.filter(metric_type="click").aggregate(total_sum=Sum("total"))["total_sum"] or 0
    )

    leads_period = LeadPlataforma.objects.filter(
        criado_em__date__range=(period_start, period_end),
        source_environment=current_environment,
    )
    published_news_period = NoticiaPublicada.objects.filter(
        status="published",
        publicada_em__date__range=(period_start, period_end),
    )
    jobs_period = JobExecucao.objects.filter(horario__date__range=(period_start, period_end))
    alerts_period = AlertaViagem.objects.filter(criado_em__date__range=(period_start, period_end), ativo=True)

    top_pages = _build_top_pages(metrics_period)
    top_clicks = _build_top_clicks(metrics_period)
    top_articles = _build_top_articles(metrics_period)
    lead_status_items = _build_lead_status_items(leads_period)

    section_rows = (
        metrics_period.filter(metric_type="page_view")
        .exclude(section="")
        .values("section")
        .annotate(total_sum=Sum("total"))
        .order_by("-total_sum")[:4]
    )
    section_highlights = [
        {
            "label": _format_section_label(row["section"]),
            "total": row["total_sum"] or 0,
        }
        for row in section_rows
    ]

    recent_leads = [
        {
            "nome_completo": item.nome_completo,
            "empresa": item.empresa,
            "email": item.email,
            "telefone": item.telefone,
            "criado_em": item.criado_em,
            "status": item.get_status_display(),
            "status_tone": LEAD_STATUS_TONES.get(item.status, "muted"),
        }
        for item in LeadPlataforma.objects.filter(source_environment=current_environment).order_by("-criado_em")[:8]
    ]
    recent_jobs = list(JobExecucao.objects.order_by("-horario")[:8])
    recent_news = list(NoticiaPublicada.objects.filter(status="published").order_by("-publicada_em")[:8])
    visible_alerts = list_visible_public_alerts()
    recent_alerts = []
    for alerta in visible_alerts[:8]:
        recent_alerts.append(
            {
                "id": alerta.id,
                "titulo": alerta.titulo,
                "rota": f"{(alerta.origem or '').upper()} -> {(alerta.destino or '').upper()}",
                "programa": alerta.programa_fidelidade or "-",
                "companhia": alerta.companhia_aerea or "-",
                "criado_em": alerta.criado_em,
                "url": reverse("portal_alerta_detalhe", args=[alerta.id]),
            }
        )

    top_section = section_highlights[0] if section_highlights else None
    top_click = top_clicks[0] if top_clicks else None
    jobs_failed = jobs_period.filter(status__in=["failed", "partial"]).count()
    jobs_success = jobs_period.filter(status="success").count()

    context = {
        "menu_ativo": "site_monitoramento",
        "site_environment": current_environment,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": f"{_format_date_label(period_start)} a {_format_date_label(period_end)}",
        "period_days": (period_end - period_start).days + 1,
        "kpis": [
            {
                "label": "Pageviews no periodo",
                "value": page_views_total,
                "description": "Views first-party registradas no portal publico.",
            },
            {
                "label": "Cliques no periodo",
                "value": clicks_total,
                "description": "Eventos de interacao capturados no site aberto.",
            },
            {
                "label": "Leads no periodo",
                "value": leads_period.count(),
                "description": "Interessados captados pela plataforma e paginas comerciais.",
            },
            {
                "label": "Noticias publicadas",
                "value": published_news_period.count(),
                "description": "Materias publicadas dentro do periodo filtrado.",
            },
            {
                "label": "Alertas publicos ativos",
                "value": len(visible_alerts),
                "description": "Alertas visiveis hoje na camada publica do portal.",
            },
        ],
        "overview_notes": [
            {
                "label": "Periodo analisado",
                "value": f"{(period_end - period_start).days + 1} dia(s)",
                "description": f"Janela atual: {_format_date_label(period_start)} ate {_format_date_label(period_end)}.",
            },
            {
                "label": "Secao com mais trafego",
                "value": top_section["label"] if top_section else "Sem dados",
                "description": (
                    f"{top_section['total']} view(s) acumuladas no periodo."
                    if top_section
                    else "Assim que o portal registrar acessos, o destaque aparece aqui."
                ),
            },
            {
                "label": "Clique mais forte",
                "value": top_click["label"] if top_click else "Sem dados",
                "description": (
                    f"{top_click['total']} clique(s) no periodo."
                    if top_click
                    else "Nao houve eventos first-party registrados nesta janela."
                ),
            },
            {
                "label": "Rodadas editoriais",
                "value": jobs_period.count(),
                "description": f"{jobs_success} com sucesso e {jobs_failed} com alerta ou falha no periodo.",
            },
        ],
        "lead_status_items": lead_status_items,
        "top_pages": top_pages,
        "top_clicks": top_clicks,
        "top_articles": top_articles,
        "recent_leads": recent_leads,
        "recent_jobs": [
            {
                "job_name": item.job_name,
                "status": item.get_status_display(),
                "status_tone": JOB_STATUS_TONES.get(item.status, "muted"),
                "horario": item.horario,
                "quantidade_processada": item.quantidade_processada,
                "quantidade_publicada": item.quantidade_publicada,
            }
            for item in recent_jobs
        ],
        "recent_news": recent_news,
        "recent_alerts": recent_alerts,
        "leads_total_all_time": LeadPlataforma.objects.filter(source_environment=current_environment).count(),
        "news_total_all_time": NoticiaPublicada.objects.filter(status="published").count(),
        "alerts_created_period": alerts_period.count(),
        "jobs_total_period": jobs_period.count(),
    }
    return render(request, "admin_custom/site_monitoramento.html", context)
