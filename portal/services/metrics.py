from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from portal.models import PortalMetricDaily


ALLOWED_CLICK_EVENTS = {
    "click_brand_publica",
    "click_login_publico",
    "click_area_logada",
    "click_categoria",
    "click_topico_categoria",
    "click_limpar_topico",
    "click_noticia_destaque",
    "click_noticia_card",
    "click_noticia_categoria_destaque",
    "click_noticia_categoria_sidebar",
    "click_noticia_categoria_grid",
    "click_noticia_relacionada",
    "click_cta_home",
    "click_cta_categoria",
    "click_saas_teaser",
    "click_cta_saas",
    "click_offer_link",
    "click_carregar_mais_noticias",
    "click_breadcrumb",
    "click_voltar_noticias",
    "click_login_comentario",
    "click_busca_publica",
}

LOCAL_SITE_HOSTS = {
    "",
    "127.0.0.1",
    "localhost",
    "0.0.0.0",
    "testserver",
}


def _clean_metric_value(value: str, limit: int) -> str:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned[:limit]


def _configured_public_host() -> str:
    try:
        return (urlparse(getattr(settings, "SITE_BASE_URL", "")).hostname or "").strip().lower()
    except Exception:
        return ""


def _request_host(request) -> str:
    if request is None:
        return ""
    try:
        return (request.get_host() or "").split(":", 1)[0].strip().lower()
    except Exception:
        return ""


def get_request_site_context(request=None) -> tuple[str, str]:
    host = _request_host(request)
    configured_host = _configured_public_host()
    default_environment = getattr(settings, "SITE_ENVIRONMENT", "local").strip().lower() or "local"

    if host in LOCAL_SITE_HOSTS or host.endswith(".local"):
        return "local", host

    if configured_host and host:
        accepted_hosts = {configured_host}
        if configured_host.startswith("www."):
            accepted_hosts.add(configured_host[4:])
        else:
            accepted_hosts.add(f"www.{configured_host}")
        if host in accepted_hosts:
            return "production", host

    return default_environment, host


def _upsert_metric(
    *,
    site_environment: str = "local",
    site_host: str = "",
    metric_type: str,
    path: str = "",
    event_name: str = "",
    section: str = "",
    article_slug: str = "",
    article_category: str = "",
    article_topic: str = "",
    metadata: dict | None = None,
) -> None:
    today = timezone.localdate()
    filters = {
        "metric_date": today,
        "site_environment": _clean_metric_value(site_environment, 20) or "local",
        "site_host": _clean_metric_value(site_host, 120),
        "metric_type": metric_type,
        "path": _clean_metric_value(path, 255),
        "event_name": _clean_metric_value(event_name, 80),
        "section": _clean_metric_value(section, 80),
        "article_slug": _clean_metric_value(article_slug, 240),
        "article_category": _clean_metric_value(article_category, 120),
        "article_topic": _clean_metric_value(article_topic, 120),
    }
    metric, created = PortalMetricDaily.objects.get_or_create(
        **filters,
        defaults={"total": 1, "metadata_json": metadata or {}},
    )
    if not created:
        PortalMetricDaily.objects.filter(pk=metric.pk).update(
            total=F("total") + 1,
            updated_at=timezone.now(),
        )


def track_page_view(
    path: str,
    *,
    request=None,
    section: str = "",
    article_slug: str = "",
    article_category: str = "",
    article_topic: str = "",
) -> None:
    site_environment, site_host = get_request_site_context(request)
    _upsert_metric(
        site_environment=site_environment,
        site_host=site_host,
        metric_type="page_view",
        path=path,
        section=section,
        article_slug=article_slug,
        article_category=article_category,
        article_topic=article_topic,
    )


def track_click_event(payload: dict, *, request=None) -> bool:
    event_name = _clean_metric_value(payload.get("event_name", ""), 80)
    if event_name not in ALLOWED_CLICK_EVENTS:
        return False

    site_environment, site_host = get_request_site_context(request)
    _upsert_metric(
        site_environment=site_environment,
        site_host=site_host,
        metric_type="click",
        path=payload.get("path", ""),
        event_name=event_name,
        section=payload.get("section", ""),
        article_slug=payload.get("article_slug", ""),
        article_category=payload.get("article_category", ""),
        article_topic=payload.get("article_topic", ""),
    )
    return True
