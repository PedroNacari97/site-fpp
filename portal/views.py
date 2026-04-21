import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.security import get_client_ip, get_request_url, get_user_agent
from .forms import AlertEmailLeadForm, AlertEmailUnsubscribeForm, PlataformaLeadForm, PlataformaQuickLeadForm
from .models import NoticiaPublicada
from .models import LeadAlertaEmail, LeadPlataforma
from .services.alert_email_broadcasts import (
    get_alert_email_lead_by_unsubscribe_token,
    get_email_from_unsubscribe_token,
    has_active_alert_subscription_for_token,
    unsubscribe_alert_email_by_token,
)
from .services.lead_notifications import notify_alert_email_lead, notify_platform_lead
from .services.metrics import get_request_site_context, track_click_event, track_page_view
from .services.public_alerts import (
    PUBLIC_HOME_ALERT_MAX_AGE_DAYS,
    build_public_alert_cards,
    build_public_alert_detail,
    build_similar_alert_cards,
    list_visible_public_alerts,
)
from .templatetags.portal_extras import repair_portuguese_text
from gestao.services.documentos_plataforma import (
    get_documento_platform_url,
    get_documento_por_tipo,
    get_pendencias_aceite_empresa,
    registrar_aceites_empresa,
)
from gestao.models import AlertaViagem, DocumentoPlataforma


CATEGORY_CONFIGS = {
    "milhas-e-pontos": {
        "label": "Milhas e Pontos",
        "hero_title": "Milhas e Pontos",
        "hero_description": "Tudo sobre programas de fidelidade, acúmulo de milhas, transferências e as melhores estratégias para viajar mais pagando menos.",
        "hero_class": "portal-category-hero--miles",
        "icon_variant": "miles",
        "card_class": "news-category-card--blue",
        "aliases": ("milhas e pontos", "milhas", "pontos", "fidelidade"),
        "load_more_label": "Carregar mais notícias",
        "cta_title": "Conheça a Plataforma NC Fly",
        "cta_description": "Gerencie programas, acompanhe transferências e emita passagens com mais controle e agilidade.",
        "cta_button": "Conhecer a plataforma",
    },
    "cartoes-credito": {
        "label": "Cartões de Crédito",
        "hero_title": "Cartões de Crédito",
        "hero_description": "Análises completas, comparativos, dicas para aprovação e tudo sobre os melhores cartões de crédito do mercado.",
        "hero_class": "portal-category-hero--cards",
        "icon_variant": "cards",
        "card_class": "news-category-card--purple",
        "aliases": ("cartoes de credito", "cartao", "cartoes", "credito", "visa", "mastercard", "amex"),
        "load_more_label": "Carregar mais notícias",
        "cta_title": "Conheça a Plataforma NC Fly",
        "cta_description": "A Plataforma NC Fly centraliza seus programas e facilita o controle das suas emissões.",
        "cta_button": "Conhecer a plataforma",
    },
    "hoteis-resorts": {
        "label": "Hotéis e Resorts",
        "hero_title": "Hotéis e Resorts",
        "hero_description": "Descubra os melhores hotéis e resorts que aceitam pontos, com dicas de hospedagem e reviews completos dos melhores destinos.",
        "hero_class": "portal-category-hero--hotels",
        "icon_variant": "hotels",
        "card_class": "news-category-card--orange",
        "aliases": ("hoteis e resorts", "hotel", "hoteis", "resorts", "resort", "hospedagem"),
        "load_more_label": "Carregar mais notícias",
        "cta_title": "Conheça a Plataforma NC Fly",
        "cta_description": "Com a Plataforma NC Fly você acompanha oportunidades de hospedagem e emite com mais eficiência.",
        "cta_button": "Conhecer a plataforma",
    },
    "promocoes": {
        "label": "Promoções",
        "hero_title": "Promoções",
        "hero_description": "As melhores promoções de milhas, passagens, cartões e hospedagens para você aproveitar agora.",
        "hero_class": "portal-category-hero--promos",
        "icon_variant": "promos",
        "card_class": "news-category-card--orange",
        "aliases": ("promocoes", "promoções", "promocao", "promoção", "oferta", "ofertas", "desconto"),
        "load_more_label": "Carregar mais promoções",
        "cta_title": "Conheça a Plataforma NC Fly",
        "cta_description": "A Plataforma NC Fly monitora oportunidades em tempo real para você emitir na hora certa.",
        "cta_button": "Conhecer a plataforma",
    },
    "viagens": {
        "label": "Viagens",
        "hero_title": "Viagens",
        "hero_description": "Destinos, roteiros, dicas de viagem e tudo que você precisa saber para planejar sua próxima aventura.",
        "hero_class": "portal-category-hero--viagens",
        "icon_variant": "travel",
        "card_class": "news-category-card--blue",
        "aliases": ("viagens", "viagem", "turismo", "destino", "destinos", "roteiro"),
        "load_more_label": "Carregar mais notícias de viagens",
        "cta_title": "Conheça a Plataforma NC Fly",
        "cta_description": "A Plataforma NC Fly ajuda você a usar seus pontos para chegar mais longe gastando menos.",
        "cta_button": "Conhecer a plataforma",
    },
}

SEO_MAX_DESCRIPTION_LENGTH = 160
PLATFORM_LEAD_CONSENT_VERSION = "2026-04-interesse-plataforma"
ALERT_EMAIL_LEAD_CONSENT_VERSION = "2026-04-alertas-email"
ALERTS_PUBLIC_PAGE_BATCH_SIZE = 6


def _estimate_read_minutes(text):
    word_count = len((text or "").split())
    return max(1, round(word_count / 180))


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").lower().strip()


def _build_query_redirect(request, *, flag_key: str, flag_value: str, anchor: str = "") -> str:
    query = request.GET.copy()
    query[flag_key] = flag_value
    encoded = query.urlencode()
    target = request.path
    if encoded:
        target = f"{target}?{encoded}"
    if anchor:
        target = f"{target}#{anchor}"
    return target


def _handle_alert_email_lead_form(request, *, source_page: str, success_anchor: str):
    submitted = request.GET.get("alert_signup") == "ok"
    is_submission = request.method == "POST" and request.POST.get("form_kind") == "alert_email_lead"
    form = AlertEmailLeadForm(request.POST if is_submission else None)

    if is_submission and form.is_valid():
        source_environment, source_host = get_request_site_context(request)
        lead, created = form.save(
            consent_version=ALERT_EMAIL_LEAD_CONSENT_VERSION,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            url_origem=get_request_url(request),
            source_environment=source_environment,
            source_host=source_host,
            source_page=source_page,
        )
        notify_alert_email_lead(lead, created=created)
        messages.success(
            request,
            (
                "Cadastro confirmado. Você entrou na lista para receber novos alertas por e-mail."
                if created
                else "Cadastro atualizado. Seus dados de recebimento de alertas foram atualizados."
            ),
        )
        return form, submitted, redirect(
            _build_query_redirect(
                request,
                flag_key="alert_signup",
                flag_value="ok",
                anchor=success_anchor,
            )
        )

    return form, submitted, None


def _seo_text(value):
    return repair_portuguese_text(value)


def _seo_description(value, default=""):
    base = _seo_text(strip_tags(value or default or settings.PORTAL_DEFAULT_META_DESCRIPTION))
    return Truncator(base).chars(SEO_MAX_DESCRIPTION_LENGTH)


def _public_base_url(request):
    configured_base = getattr(settings, "SITE_BASE_URL", "")
    if configured_base:
        return configured_base.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _absolute_public_url(request, path_or_url):
    if not path_or_url:
        return ""
    if str(path_or_url).startswith(("http://", "https://")):
        return str(path_or_url)
    base_url = _public_base_url(request)
    path = str(path_or_url)
    if path.startswith("/"):
        return f"{base_url}{path}"
    return f"{base_url}/{path.lstrip('/')}"


def _absolute_image_url(request, image_url):
    return _absolute_public_url(request, image_url) if image_url else ""


def _request_is_same_origin(request):
    origin = request.headers.get("Origin", "").strip()
    referer = request.headers.get("Referer", "").strip()
    base_url = _public_base_url(request)

    allowed_origins = {base_url.rstrip("/")}
    request_origin = f"{request.scheme}://{request.get_host()}".rstrip("/")
    allowed_origins.add(request_origin)

    def origin_is_allowed(value):
        if not value:
            return True
        parsed_value = urlparse(value)
        value_origin = f"{parsed_value.scheme}://{parsed_value.netloc}".rstrip("/")
        return value_origin in allowed_origins

    if origin and not origin_is_allowed(origin):
        return False
    if referer and not origin_is_allowed(referer):
        return False
    return True


@lru_cache(maxsize=8)
def _local_image_dimensions(static_path: str) -> tuple[int, int] | None:
    """Lê width/height de um arquivo estático local. Usa lru_cache: lê uma vez por processo."""
    if not static_path or not static_path.startswith("/static/"):
        return None
    try:
        from django.contrib.staticfiles import finders
        relative = static_path.removeprefix("/static/")
        resolved = finders.find(relative)
        if not resolved:
            return None
        from PIL import Image
        with Image.open(Path(resolved)) as im:
            return int(im.width), int(im.height)
    except Exception:
        return None


_VALID_SOCIAL_URL_SCHEMES = ("http://", "https://")


def _valid_social_urls(urls):
    out = []
    for raw in urls or []:
        url = (raw or "").strip()
        if not url:
            continue
        if not url.startswith(_VALID_SOCIAL_URL_SCHEMES):
            continue
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                continue
        except Exception:
            continue
        out.append(url)
    return out


def _build_organization_schema(request):
    base_url = _public_base_url(request)
    schema = {
        "@type": "Organization",
        "@id": f"{base_url}#organization",
        "name": settings.PORTAL_SITE_NAME,
        "url": base_url,
    }
    logo_raw = settings.PORTAL_SITE_LOGO_URL or getattr(settings, "PORTAL_SITE_FAVICON_URL", "")
    logo_url = _absolute_image_url(request, logo_raw)
    if logo_url:
        logo_node = {
            "@type": "ImageObject",
            "url": logo_url,
            "contentUrl": logo_url,
        }
        dims = _local_image_dimensions(logo_raw)
        if dims:
            logo_node["width"], logo_node["height"] = dims
        schema["logo"] = logo_node
        schema["image"] = logo_url
    same_as = _valid_social_urls(getattr(settings, "PORTAL_SOCIAL_PROFILES", []))
    if same_as:
        schema["sameAs"] = same_as
    contact_points = []
    if settings.PORTAL_CONTACT_EMAIL:
        contact_points.append(
            {
                "@type": "ContactPoint",
                "contactType": "customer support",
                "email": settings.PORTAL_CONTACT_EMAIL,
                "availableLanguage": ["pt-BR"],
            }
        )
    if settings.PORTAL_DPO_EMAIL and settings.PORTAL_DPO_EMAIL != settings.PORTAL_CONTACT_EMAIL:
        contact_points.append(
            {
                "@type": "ContactPoint",
                "contactType": "data protection officer",
                "email": settings.PORTAL_DPO_EMAIL,
                "availableLanguage": ["pt-BR"],
            }
        )
    if contact_points:
        schema["contactPoint"] = contact_points
    return schema


def _build_website_schema(request):
    home_url = _absolute_public_url(request, reverse("portal_home"))
    return {
        "@type": "WebSite",
        "@id": f"{home_url}#website",
        "name": settings.PORTAL_SITE_NAME,
        "url": home_url,
        "inLanguage": "pt-BR",
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{home_url}?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }


def _build_breadcrumb_schema(items):
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": _seo_text(item["name"]),
                "item": item["url"],
            }
            for position, item in enumerate(items, start=1)
        ],
    }


def _build_item_list_schema(list_id, name, items):
    normalized_items = [item for item in items if item.get("name") and item.get("url")]
    if not normalized_items:
        return None
    return {
        "@type": "ItemList",
        "@id": f"{list_id}#itemlist",
        "name": _seo_text(name),
        "itemListOrder": "https://schema.org/ItemListOrderAscending",
        "numberOfItems": len(normalized_items),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "name": _seo_text(item["name"]),
                "url": item["url"],
            }
            for position, item in enumerate(normalized_items, start=1)
        ],
    }


def _build_schema_graph(*nodes):
    graph_nodes = [node for node in nodes if node]
    if not graph_nodes:
        return ""
    raw = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": graph_nodes,
        },
        ensure_ascii=False,
    )
    # Previne injeção de </script> em blocos inline de JSON-LD
    return raw.replace("</", "<\\/").replace("<!--", "<\\!--")


def _build_seo_context(
    request,
    *,
    title,
    description,
    canonical_url,
    image_url="",
    og_type="website",
    robots="index,follow",
    schema_json="",
    published_time=None,
    modified_time=None,
    section="",
    keywords=None,
):
    seo_title = _seo_text(title)
    seo_keywords = [_seo_text(item) for item in (keywords or []) if item]
    return {
        "seo_title": seo_title,
        "seo_description": _seo_description(description),
        "seo_canonical_url": canonical_url,
        "seo_robots": robots,
        "seo_og_type": og_type,
        "seo_og_image": _absolute_image_url(request, image_url),
        "seo_twitter_card": "summary_large_image" if image_url else "summary",
        "seo_schema_json": schema_json,
        "seo_site_name": settings.PORTAL_SITE_NAME,
        "seo_published_time": timezone.localtime(published_time).isoformat() if published_time else "",
        "seo_modified_time": timezone.localtime(modified_time).isoformat() if modified_time else "",
        "seo_section": _seo_text(section),
        "seo_keywords": ", ".join(seo_keywords),
        "seo_tags": seo_keywords,
    }


def _build_home_seo(request, destaque=None):
    canonical_url = _absolute_public_url(request, reverse("portal_home"))
    description = settings.PORTAL_DEFAULT_META_DESCRIPTION
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "CollectionPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": settings.PORTAL_SITE_NAME,
            "description": description,
            "isPartOf": {"@id": f"{canonical_url}#website"},
            "inLanguage": "pt-BR",
        },
    )
    return _build_seo_context(
        request,
        title="NC Fly News | Milhas, promoções, cartões e viagens",
        description=description,
        canonical_url=canonical_url,
        image_url=destaque.imagem_exibicao if destaque else "",
        schema_json=schema_json,
    )


def _build_home_search_seo(request, search_query):
    canonical_url = request.build_absolute_uri()
    description = (
        f'Resultados da busca por "{search_query}" no portal NC Fly News sobre milhas, '
        "promocoes, cartoes de credito, hoteis e viagens."
    )
    return _build_seo_context(
        request,
        title=f'Busca por "{search_query}" | NC Fly News',
        description=description,
        canonical_url=canonical_url,
        robots="noindex,follow",
        schema_json=_build_schema_graph(
            _build_organization_schema(request),
            _build_website_schema(request),
            {
                "@type": "SearchResultsPage",
                "@id": f"{canonical_url}#webpage",
                "url": canonical_url,
                "name": _seo_text(f'Busca por "{search_query}" | NC Fly News'),
                "description": _seo_description(description),
                "isPartOf": {"@id": f"{_absolute_public_url(request, reverse('portal_home'))}#website"},
                "inLanguage": "pt-BR",
            },
        ),
        section="Busca",
        keywords=[search_query, "busca noticias NC Fly"],
    )


def _build_static_page_seo(request, *, route_name, title, description, robots="index,follow"):
    canonical_url = _absolute_public_url(request, reverse(route_name))
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "WebPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": _seo_text(title),
            "description": _seo_description(description),
            "isPartOf": {"@id": f"{_absolute_public_url(request, reverse('portal_home'))}#website"},
            "inLanguage": "pt-BR",
        },
        _build_breadcrumb_schema(
            [
                {"name": "Início", "url": _absolute_public_url(request, reverse("portal_home"))},
                {"name": title, "url": canonical_url},
            ]
        ),
    )
    return _build_seo_context(
        request,
        title=f"{title} | NC Fly News",
        description=description,
        canonical_url=canonical_url,
        robots=robots,
        schema_json=schema_json,
    )


def _build_saas_page_seo(request):
    canonical_url = _absolute_public_url(request, reverse("portal_plataforma_saas"))
    home_url = _absolute_public_url(request, reverse("portal_home"))
    description = (
        "Conheça a Plataforma NC Fly, produto da NC Fly para organizar cotações, "
        "emissões, clientes, alertas de passagens e contas fidelidade em um único fluxo."
    )
    faq_items = [
        {
            "@type": "Question",
            "name": "Para quem a Plataforma NC Fly foi pensada?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "A Plataforma NC Fly foi pensada para agências, consultorias e operações entre empresas "
                    "que precisam centralizar cotações, emissões, clientes, alertas e contas fidelidade."
                ),
            },
        },
        {
            "@type": "Question",
            "name": "Quais áreas a plataforma cobre hoje?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "A plataforma cobre cotações, emissões, clientes, passageiros frequentes, "
                    "contas fidelidade, alertas de passagens e interesses de viagem."
                ),
            },
        },
        {
            "@type": "Question",
            "name": "Como ela ajuda a operação no dia a dia?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": (
                    "Ela reduz retrabalho, reaproveita dados entre cotação e emissão, organiza "
                    "clientes e melhora a velocidade de resposta da equipe."
                ),
            },
        },
    ]
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "SoftwareApplication",
            "@id": f"{canonical_url}#software",
            "name": "Plataforma NC Fly",
            "url": canonical_url,
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Web",
            "description": description,
            "brand": {"@type": "Brand", "name": "NC Fly"},
            "offers": {
                "@type": "Offer",
                "availability": "https://schema.org/InStock",
                "priceCurrency": "BRL",
                "price": "0",
            },
        },
        {
            "@type": "WebPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": "Plataforma NC Fly | Produto da NC Fly",
            "description": description,
            "isPartOf": {"@id": f"{home_url}#website"},
            "inLanguage": "pt-BR",
        },
        {
            "@type": "FAQPage",
            "@id": f"{canonical_url}#faq",
            "mainEntity": faq_items,
        },
        _build_breadcrumb_schema(
            [
                {"name": "Início", "url": home_url},
                {"name": "Plataforma NC Fly", "url": canonical_url},
            ]
        ),
    )
    return _build_seo_context(
        request,
        title="Plataforma NC Fly | Produto para operação de viagens",
        description=description,
        canonical_url=canonical_url,
        schema_json=schema_json,
        section="Plataforma NC Fly",
        keywords=[
            "Plataforma NC Fly",
            "software para agência de viagens",
            "plataforma como serviço para emissões",
            "gestão de cotações e emissão",
            "operação de viagens entre empresas",
        ],
    )


def _build_saas_contact_page_seo(request):
    canonical_url = _absolute_public_url(request, reverse("portal_plataforma_contato"))
    home_url = _absolute_public_url(request, reverse("portal_home"))
    description = (
        "Página informativa de contato da Plataforma NC Fly, mantida fora da navegação principal enquanto o produto público ainda está em preparação."
    )
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "ContactPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": "Solicitar apresentação da Plataforma NC Fly",
            "description": description,
            "isPartOf": {"@id": f"{home_url}#website"},
            "inLanguage": "pt-BR",
        },
        {
            "@type": "Service",
            "@id": f"{canonical_url}#service",
            "name": "Apresentacao comercial da plataforma NC Fly",
            "provider": {"@id": f"{_public_base_url(request)}#organization"},
            "serviceType": "Plataforma como serviço para operação de viagens",
            "url": canonical_url,
            "description": description,
        },
        _build_breadcrumb_schema(
            [
                {"name": "Início", "url": home_url},
                {"name": "Plataforma NC Fly", "url": _absolute_public_url(request, reverse("portal_plataforma_saas"))},
                {"name": "Solicitar apresentação", "url": canonical_url},
            ]
        ),
    )
    return _build_seo_context(
        request,
        title="Solicitar apresentação | Plataforma NC Fly",
        description=description,
        canonical_url=canonical_url,
        schema_json=schema_json,
        section="Plataforma NC Fly",
        robots="noindex,nofollow",
        keywords=[
            "demonstracao plataforma NC Fly",
            "contato comercial software para viagens",
            "plataforma como serviço para agência de viagens",
            "gestão de cotações e emissões",
        ],
    )


def _build_alerts_list_seo(request, alert_cards=None):
    canonical_url = _absolute_public_url(request, reverse("portal_alertas"))
    home_url = _absolute_public_url(request, reverse("portal_home"))
    item_list_schema = _build_item_list_schema(
        canonical_url,
        "Alertas de passagens",
        [
            {
                "name": f"{item['origem_codigo']} para {item['destino_codigo']} - {item['miles_label']}",
                "url": _absolute_public_url(request, item["url"]),
            }
            for item in (alert_cards or [])[:12]
        ],
    )
    description = (
        "Veja alertas públicos de passagens com programas de fidelidade, quantidade de milhas, "
        "rotas, datas organizadas e acesso rápido para emissão."
    )
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "CollectionPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": "Alertas de passagens | NC Fly News",
            "description": description,
            "isPartOf": {"@id": f"{home_url}#website"},
            "inLanguage": "pt-BR",
        },
        _build_breadcrumb_schema(
            [
                {"name": "Início", "url": home_url},
                {"name": "Alertas de passagens", "url": canonical_url},
            ]
        ),
        item_list_schema,
    )
    return _build_seo_context(
        request,
        title="Alertas de passagens | NC Fly News",
        description=description,
        canonical_url=canonical_url,
        schema_json=schema_json,
        section="Alertas de passagens",
        keywords=[
            "alertas de passagens",
            "ofertas de milhas",
            "passagens com milhas",
            "oportunidades de emissão",
        ],
    )


def _build_alert_detail_seo(request, alerta, alert_content):
    canonical_url = _absolute_public_url(request, reverse("portal_alerta_detalhe", args=[alerta.id]))
    home_url = _absolute_public_url(request, reverse("portal_home"))
    headline = alert_content["hero_title"]
    if alerta.valor_milhas:
        description = (
            f"{alert_content['route_label']} no programa {alert_content['programa']} "
            f"{alert_content['miles_label']} milhas por pessoa."
        )
    else:
        description = (
            f"{alert_content['route_label']} no programa {alert_content['programa']}. "
            "Consulte a pontuação atual diretamente no programa antes de emitir."
        )
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "Article",
            "@id": f"{canonical_url}#article",
            "headline": _seo_text(headline),
            "description": _seo_description(description),
            "datePublished": timezone.localtime(alerta.criado_em).isoformat(),
            "dateModified": timezone.localtime(alerta.criado_em).isoformat(),
            "author": {"@type": "Organization", "name": "NC Fly News"},
            "publisher": {"@id": f"{_public_base_url(request)}#organization"},
            "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
            "articleSection": "Alertas de passagens",
            "keywords": [
                _seo_text(alerta.programa_fidelidade),
                _seo_text(alerta.companhia_aerea),
                _seo_text(alerta.cidade_destino),
                _seo_text(alerta.get_classe_display()),
            ],
            "inLanguage": "pt-BR",
            "url": canonical_url,
        },
        _build_breadcrumb_schema(
            [
                {"name": "Início", "url": home_url},
                {"name": "Alertas de passagens", "url": _absolute_public_url(request, reverse("portal_alertas"))},
                {"name": headline, "url": canonical_url},
            ]
        ),
    )
    return _build_seo_context(
        request,
        title=f"{headline} | NC Fly News",
        description=description,
        canonical_url=canonical_url,
        schema_json=schema_json,
        section="Alertas de passagens",
        keywords=[
            alerta.programa_fidelidade,
            alerta.companhia_aerea,
            alerta.cidade_destino,
            alerta.origem,
            alerta.destino,
        ],
    )


def _alert_filter_option_values(values):
    seen = {}
    for raw_value in values:
        label = repair_portuguese_text(raw_value or "").strip()
        if not label:
            continue
        normalized = _normalize_text(label)
        if normalized and normalized not in seen:
            seen[normalized] = label
    return [{"value": value, "label": value} for value in sorted(seen.values(), key=_normalize_text)]


def _alert_class_filter_options(alertas):
    seen = {}
    choices = dict(AlertaViagem.CLASSE_CHOICES)
    for alerta in alertas:
        raw_value = (alerta.classe or "").strip()
        if not raw_value or raw_value in seen:
            continue
        seen[raw_value] = repair_portuguese_text(choices.get(raw_value, alerta.get_classe_display() or raw_value))
    return [{"value": value, "label": label} for value, label in sorted(seen.items(), key=lambda item: _normalize_text(item[1]))]


def _filter_public_alerts(alertas, aeroporto="", programa="", companhia="", classe="", origem="", destino=""):
    selected_airport = _normalize_text(aeroporto)
    selected_program = _normalize_text(programa)
    selected_airline = _normalize_text(companhia)
    selected_class = _normalize_text(classe)
    selected_origem = origem.strip().upper()
    selected_destino = destino.strip().upper()

    filtered = []
    for alerta in alertas:
        airport_search_values = [
            alerta.get("origem_codigo", ""),
            alerta.get("destino_codigo", ""),
            alerta.get("origem_display", ""),
            alerta.get("destino_display", ""),
            alerta.get("origem_name", ""),
            alerta.get("destino_name", ""),
            alerta.get("origem_label", ""),
            alerta.get("destino_label", ""),
            alerta.get("origem_cidade", ""),
            alerta.get("destino_cidade", ""),
            alerta.get("route_label", ""),
        ]
        airport_search_text = " ".join(
            value for value in (_normalize_text(item) for item in airport_search_values) if value
        )
        if selected_airport and selected_airport not in airport_search_text:
            continue
        if selected_origem and alerta.get("origem_codigo", "").upper() != selected_origem:
            continue
        if selected_destino and alerta.get("destino_codigo", "").upper() != selected_destino:
            continue
        if selected_program and _normalize_text(alerta.get("programa")) != selected_program:
            continue
        if selected_airline and _normalize_text(alerta.get("companhia")) != selected_airline:
            continue
        if selected_class and _normalize_text(alerta.get("classe")) != selected_class:
            continue
        filtered.append(alerta)
    return filtered


def _build_platform_document_context(tipo):
    documento = get_documento_por_tipo(tipo)
    return {
        "documento_info": documento,
        "documento_versao": getattr(documento, "versao_atual", ""),
        "documento_vigencia": getattr(documento, "data_vigencia", None),
    }


def _build_category_seo(
    request,
    categoria_slug,
    categoria_config,
    featured=None,
    selected_topic=None,
    listed_items=None,
):
    canonical_url = _absolute_public_url(
        request, reverse("portal_categoria", kwargs={"categoria_slug": categoria_slug})
    )
    item_list_schema = _build_item_list_schema(
        canonical_url,
        categoria_config["label"],
        [
            {
                "name": item.titulo,
                "url": _absolute_public_url(request, item.get_absolute_url()),
            }
            for item in (listed_items or [])[:12]
            if item
        ],
    )
    description = categoria_config["hero_description"]
    title = f"{categoria_config['label']} | NC Fly News"
    robots = "index,follow"
    if selected_topic:
        title = f"{selected_topic['label']} em {categoria_config['label']} | NC Fly News"
        description = (
            f"Notícias e análises sobre {selected_topic['label']} dentro da categoria "
            f"{categoria_config['label']} no portal NC Fly News."
        )
        robots = "noindex,follow"
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "CollectionPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": _seo_text(title),
            "description": _seo_description(description),
            "isPartOf": {"@id": f"{_absolute_public_url(request, reverse('portal_home'))}#website"},
            "inLanguage": "pt-BR",
        },
        _build_breadcrumb_schema(
            [
                {"name": "Início", "url": _absolute_public_url(request, reverse("portal_home"))},
                {"name": categoria_config["label"], "url": canonical_url},
            ]
        ),
        item_list_schema,
    )
    return _build_seo_context(
        request,
        title=title,
        description=description,
        canonical_url=canonical_url,
        image_url=featured.imagem_exibicao if featured else "",
        robots=robots,
        schema_json=schema_json,
        section=categoria_config["label"],
        keywords=[categoria_config["label"], selected_topic["label"] if selected_topic else ""],
    )


def _build_article_seo(request, noticia, categoria_slug):
    canonical_url = _absolute_public_url(request, noticia.get_absolute_url())
    base_url = _public_base_url(request)
    image_url = _absolute_image_url(request, noticia.imagem_exibicao)
    seo_metadata = (noticia.metadata_json or {}).get("seo", {})
    description = seo_metadata.get("meta_description") or noticia.resumo or noticia.titulo
    headline = seo_metadata.get("title") or noticia.titulo
    category_url = (
        _absolute_public_url(request, reverse("portal_categoria", kwargs={"categoria_slug": categoria_slug}))
        if categoria_slug
        else ""
    )
    body_text = strip_tags(noticia.conteudo or "")
    word_count = len(body_text.split())
    article_schema = {
        "@type": "NewsArticle",
        "@id": f"{canonical_url}#article",
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "headline": _seo_text(headline),
        "description": _seo_description(description),
        "datePublished": timezone.localtime(noticia.publicada_em).isoformat(),
        "dateModified": timezone.localtime(noticia.atualizada_em).isoformat(),
        "author": {"@type": "Organization", "name": "Redação NC Fly"},
        "publisher": {"@id": f"{base_url}#organization"},
        "url": canonical_url,
        "inLanguage": "pt-BR",
        "wordCount": word_count,
    }
    if image_url:
        article_schema["image"] = [image_url]
        article_schema["thumbnailUrl"] = image_url
    if noticia.categoria:
        article_schema["articleSection"] = _seo_text(noticia.categoria)
    if noticia.tags_exibicao:
        article_schema["keywords"] = [_seo_text(tag) for tag in noticia.tags_exibicao]
        article_schema["about"] = [{"@type": "Thing", "name": _seo_text(tag)} for tag in noticia.tags_exibicao[:5]]

    breadcrumb_items = [{"name": "Início", "url": _absolute_public_url(request, reverse("portal_home"))}]
    if categoria_slug and category_url:
        breadcrumb_items.append({"name": noticia.categoria or "Categoria", "url": category_url})
    breadcrumb_items.append({"name": noticia.titulo, "url": canonical_url})

    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        article_schema,
        _build_breadcrumb_schema(breadcrumb_items),
    )
    return _build_seo_context(
        request,
        title=f"{headline} | NC Fly News",
        description=description,
        canonical_url=canonical_url,
        image_url=noticia.imagem_exibicao,
        og_type="article",
        schema_json=schema_json,
        published_time=noticia.publicada_em,
        modified_time=noticia.atualizada_em,
        section=noticia.categoria,
        keywords=noticia.tags_exibicao,
    )


def _get_published_news():
    cached = cache.get("portal_published_news")
    if cached is not None:
        return cached
    result = list(
        NoticiaPublicada.objects.filter(status="published")
        .select_related("fonte")
        .order_by("-publicada_em")
    )
    cache.set("portal_published_news", result, 72000)
    return result


def invalidate_news_cache():
    cache.delete("portal_published_news")


def _filter_news_by_query(noticias, search_query):
    normalized_query = _normalize_text(search_query)
    search_terms = [term for term in normalized_query.split() if term]
    if not search_terms:
        return noticias

    filtered = []
    for noticia in noticias:
        haystack = _normalize_text(
            " ".join(
                [
                    noticia.titulo,
                    noticia.resumo,
                    noticia.conteudo,
                    noticia.categoria,
                    noticia.topico,
                    " ".join(str(tag) for tag in (noticia.tags_json or []) if tag),
                ]
            )
        )
        if all(term in haystack for term in search_terms):
            filtered.append(noticia)
    return filtered


def _build_explore_categories():
    return [
        {
            "label": config["label"],
            "slug": slug,
            "css_class": config["card_class"],
            "icon_variant": config["icon_variant"],
        }
        for slug, config in CATEGORY_CONFIGS.items()
    ]


def _category_config_from_slug(categoria_slug):
    config = CATEGORY_CONFIGS.get(categoria_slug)
    if not config:
        raise Http404("Categoria não encontrada.")
    return config


def _category_slug_from_label(label):
    normalized_label = _normalize_text(label)
    for slug, config in CATEGORY_CONFIGS.items():
        if normalized_label == _normalize_text(config["label"]):
            return slug
        if any(alias == normalized_label for alias in config["aliases"]):
            return slug
    return None


def _news_matches_category(noticia, config, categoria_slug):
    if _category_slug_from_label(noticia.categoria) == categoria_slug:
        return True
    combined = " ".join(
        filter(
            None,
            [
                noticia.categoria,
                noticia.topico,
                " ".join(noticia.tags_exibicao),
                noticia.titulo,
                noticia.resumo,
                noticia.conteudo[:240] if noticia.conteudo else "",
            ],
        )
    )
    haystack = _normalize_text(combined)
    return any(alias in haystack for alias in config["aliases"])


def _pick_articles(primary, fallback_pool, total):
    chosen = []
    chosen_ids = set()
    for item in list(primary) + list(fallback_pool):
        if item.id in chosen_ids:
            continue
        chosen.append(item)
        chosen_ids.add(item.id)
        if len(chosen) >= total:
            break
    return chosen


def _build_topic_groups(noticias):
    grouped = {}
    for noticia in noticias:
        topic_label = noticia.topico or noticia.categoria or "Destaques"
        grouped.setdefault(topic_label, []).append(noticia)

    ordered_groups = sorted(
        grouped.items(),
        key=lambda item: (
            -len(item[1]),
            -(item[1][0].publicada_em.timestamp()) if item[1] else 0,
        ),
    )
    return [
        {
            "label": label,
            "slug": slugify(label),
            "count": len(items),
            "items": items,
        }
        for label, items in ordered_groups
    ]


def _build_category_page_context(categoria_slug, selected_topic_slug=""):
    config = _category_config_from_slug(categoria_slug)
    noticias = _get_published_news()
    matching = [noticia for noticia in noticias if _news_matches_category(noticia, config, categoria_slug)]
    fallback = [noticia for noticia in noticias if noticia not in matching]
    topicos_disponiveis = _build_topic_groups(matching)

    selected_topic = None
    if selected_topic_slug:
        for topic_group in topicos_disponiveis:
            if topic_group["slug"] == selected_topic_slug:
                selected_topic = topic_group
                break

    active_pool = selected_topic["items"] if selected_topic else matching
    ordered = active_pool[:10] if selected_topic else _pick_articles(matching, fallback, 10)
    active_total = len(active_pool) if selected_topic else len(matching)
    featured = ordered[0] if ordered else None
    sidebar_cards = ordered[1:2]
    grid_cards = ordered[2:10]
    visible_count = (1 if featured else 0) + len(sidebar_cards) + len(grid_cards)
    hidden_cards = active_pool[visible_count:] if selected_topic else matching[visible_count:]
    remaining_count = max(active_total - visible_count, 0)
    outras_noticias = fallback[:8]
    return {
        "categoria_slug": categoria_slug,
        "categoria_config": config,
        "featured": featured,
        "sidebar_cards": sidebar_cards,
        "grid_cards": grid_cards,
        "hidden_cards": hidden_cards,
        "news_total": len(matching) if matching else len(ordered),
        "topicos_disponiveis": topicos_disponiveis,
        "topico_ativo": selected_topic,
        "remaining_count": remaining_count,
        "show_load_more": remaining_count > 0,
        "outras_noticias": outras_noticias,
    }


def home_publica(request):
    alert_email_lead_form, alert_email_lead_submitted, alert_email_lead_redirect = _handle_alert_email_lead_form(
        request,
        source_page=LeadAlertaEmail.ORIGEM_HOME,
        success_anchor="home-alertas-email",
    )
    if alert_email_lead_redirect:
        return alert_email_lead_redirect

    search_query = (request.GET.get("q") or "").strip()
    noticias = _filter_news_by_query(_get_published_news(), search_query)
    is_searching = bool(search_query)
    HOME_INITIAL = 8
    HOME_BATCH = 8
    HOME_MOBILE_INITIAL = 3
    visible = noticias[:HOME_INITIAL]
    hidden = noticias[HOME_INITIAL:]

    # --- Modulos de estudo com gating por login (Portal B2C) ---
    from .auth import get_portal_user
    from .models import ModuloEstudo
    from .services.progresso import anotar_progresso_em_modulos

    portal_user = get_portal_user(request)
    all_modulos = list(
        ModuloEstudo.objects.filter(ativo=True)
        .order_by("-destaque_home", "ordem", "titulo")
    )
    # Anota `.total_artigos` e `.progresso` (dict) em cada modulo sem N+1
    anotar_progresso_em_modulos(portal_user, all_modulos)

    if portal_user is not None:
        modulo_amostra = all_modulos[0] if all_modulos else None
        modulos_bloqueados = []
        modulos_liberados = all_modulos[1:] if all_modulos else []
    else:
        # publico — so 1 modulo de amostra aberto, demais bloqueados com CTA login
        modulo_amostra = next(
            (m for m in all_modulos if m.destaque_home),
            all_modulos[0] if all_modulos else None,
        )
        modulos_bloqueados = [m for m in all_modulos if m is not modulo_amostra]
        modulos_liberados = []

    alertas_home = [] if is_searching else build_public_alert_cards(
        list_visible_public_alerts(limit=15, max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS)
    )

    context = {
        "noticias_visiveis": visible,
        "noticias_ocultas": hidden,
        "alertas_home": alertas_home,
        "explore_categories": _build_explore_categories(),
        "publicadas_ate": timezone.localtime(),
        "search_query": search_query,
        "is_searching": is_searching,
        "search_results_total": len(noticias),
        "home_batch": HOME_BATCH,
        "alert_email_lead_form": alert_email_lead_form,
        "alert_email_lead_submitted": alert_email_lead_submitted,
        "alert_email_lead_consent_version": ALERT_EMAIL_LEAD_CONSENT_VERSION,
        "alert_email_lead_section_id": "home-alertas-email",
        "modulo_amostra": modulo_amostra,
        "modulos_bloqueados": modulos_bloqueados,
        "modulos_liberados": modulos_liberados,
        "portal_user_is_authenticated": portal_user is not None,
    }
    if is_searching:
        context.update(_build_home_search_seo(request, search_query))
    else:
        context.update(_build_home_seo(request, visible[0] if visible else None))
    track_page_view(
        request.path,
        request=request,
        section="home_search" if is_searching else "home",
        article_topic=search_query if is_searching else "",
    )
    return render(request, "portal/home.html", context)


def alertas_publicos(request):
    alert_email_lead_form, alert_email_lead_submitted, alert_email_lead_redirect = _handle_alert_email_lead_form(
        request,
        source_page=LeadAlertaEmail.ORIGEM_ALERTAS,
        success_anchor="alertas-email-lead",
    )
    if alert_email_lead_redirect:
        return alert_email_lead_redirect

    visible_alerts = list_visible_public_alerts(max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS)
    selected_filters = {
        "aeroporto": (request.GET.get("aeroporto") or "").strip(),
        "programa": (request.GET.get("programa") or "").strip(),
        "companhia": (request.GET.get("companhia") or "").strip(),
        "classe": (request.GET.get("classe") or "").strip(),
        "origem": (request.GET.get("origem") or "").strip().upper(),
        "destino": (request.GET.get("destino") or "").strip().upper(),
    }
    visible_alert_cards = build_public_alert_cards(visible_alerts)
    alert_cards = _filter_public_alerts(
        visible_alert_cards,
        aeroporto=selected_filters["aeroporto"],
        programa=selected_filters["programa"],
        companhia=selected_filters["companhia"],
        classe=selected_filters["classe"],
        origem=selected_filters["origem"],
        destino=selected_filters["destino"],
    )
    filters_active = any(selected_filters.values())

    # Build origem/destino dropdown options from ALL visible cards (unfiltered)
    # Formato padronizado: "Cidade (IATA)" — evita repetição e fallback só-IATA
    def _airport_dropdown_label(cidade: str, codigo: str) -> str:
        cidade = (cidade or "").strip()
        if cidade and cidade.upper() != codigo.upper():
            return f"{cidade} ({codigo})"
        return codigo

    origens_seen = {}
    for card in visible_alert_cards:
        cod = card.get("origem_codigo", "")
        if cod and cod not in origens_seen:
            origens_seen[cod] = _airport_dropdown_label(card.get("origem_cidade", ""), cod)
    origens = [{"value": k, "label": v} for k, v in sorted(origens_seen.items(), key=lambda x: x[1])]

    destinos_por_origem = {}
    for card in visible_alert_cards:
        orig = card.get("origem_codigo", "")
        dest = card.get("destino_codigo", "")
        if orig and dest:
            if orig not in destinos_por_origem:
                destinos_por_origem[orig] = {}
            destinos_por_origem[orig][dest] = _airport_dropdown_label(card.get("destino_cidade", ""), dest)

    destinos_all_seen = {}
    for card in visible_alert_cards:
        cod = card.get("destino_codigo", "")
        if cod and cod not in destinos_all_seen:
            destinos_all_seen[cod] = _airport_dropdown_label(card.get("destino_cidade", ""), cod)
    destinos_all = [{"value": k, "label": v} for k, v in sorted(destinos_all_seen.items(), key=lambda x: x[1])]

    destinos_por_origem_json = json.dumps(
        {k: [{"value": d, "label": l} for d, l in sorted(v.items())] for k, v in destinos_por_origem.items()},
        ensure_ascii=False,
    )

    context = {
        "page_title": "Alertas de passagens",
        "page_eyebrow": "Alertas NC Fly",
        "page_intro": (
            "Acompanhe oportunidades de emissão com programas de fidelidade, rotas selecionadas "
            "e datas organizadas para consultar a disponibilidade com mais rapidez."
        ),
        "page_updated_at": timezone.localdate(),
        "alertas_publicos": alert_cards,
        "alerts_page_size": ALERTS_PUBLIC_PAGE_BATCH_SIZE,
        "hidden_alert_count": max(0, len(alert_cards) - ALERTS_PUBLIC_PAGE_BATCH_SIZE),
        "filters_active": filters_active,
        "selected_alert_filters": selected_filters,
        "alert_filter_options": {
            "programas": _alert_filter_option_values([alerta.programa_fidelidade for alerta in visible_alerts]),
            "companhias": _alert_filter_option_values([alerta.companhia_aerea for alerta in visible_alerts]),
            "classes": _alert_class_filter_options(visible_alerts),
            "origens": origens,
            "destinos_all": destinos_all,
            "destinos_por_origem_json": destinos_por_origem_json,
        },
        "alert_results_total": len(alert_cards),
        "alert_email_lead_form": alert_email_lead_form,
        "alert_email_lead_submitted": alert_email_lead_submitted,
        "alert_email_lead_consent_version": ALERT_EMAIL_LEAD_CONSENT_VERSION,
        "alert_email_lead_section_id": "alertas-email-lead",
        "alert_email_lead_title": "Quer receber novos alertas?",
        "alert_email_lead_compact_copy": True,
        "alertas_home": [],
    }
    context["page_intro"] = "Acompanhe oportunidades de emiss\u00e3o com programas de fidelidade"
    context.update(_build_alerts_list_seo(request, alert_cards=alert_cards))
    track_page_view(
        request.path,
        request=request,
        section="public_alerts",
        article_category=selected_filters["programa"],
        article_topic=selected_filters["aeroporto"] or selected_filters["companhia"] or selected_filters["classe"],
    )
    return render(request, "portal/alertas.html", context)


def alerta_publico_detalhe(request, alerta_id):
    alerta = get_object_or_404(AlertaViagem, id=alerta_id, ativo=True)
    if not alerta.deve_aparecer_na_vitrine(max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS):
        raise Http404("Alerta não disponível.")

    alert_content = build_public_alert_detail(alerta)
    context = {
        "alerta": alerta,
        "alert_context": alert_content,
        "similar_alerts": build_similar_alert_cards(alerta, max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS),
        "back_url": reverse("portal_alertas"),
    }
    context.update(_build_alert_detail_seo(request, alerta, alert_content))
    track_page_view(
        request.path,
        request=request,
        section="public_alert_detail",
        article_category=alerta.programa_fidelidade,
        article_topic=alerta.cidade_destino,
    )
    return render(request, "portal/alerta_detalhe.html", context)


def alerta_publico_compartilhar(request, alerta_id):
    alerta = get_object_or_404(AlertaViagem, id=alerta_id, ativo=True)
    if not alerta.deve_aparecer_na_vitrine(max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS):
        raise Http404("Alerta nao disponivel.")

    alert_content = build_public_alert_detail(alerta)
    alert_url = request.build_absolute_uri(reverse("portal_alerta_detalhe", args=[alerta.id]))
    share_title = f"Alerta NC Fly: {alert_content['hero_title']}"
    share_text = (
        f"Olha este alerta da NC Fly: {alert_content['hero_title']} "
        f"por {alert_content['miles_label']}."
    )
    share_message = f"{share_text} {alert_url}"
    encoded_url = quote(alert_url, safe="")
    encoded_text = quote(share_text, safe="")
    encoded_message = quote(share_message, safe="")
    context = {
        "alerta": alerta,
        "alert_context": alert_content,
        "alert_url": alert_url,
        "share_title": share_title,
        "share_text": share_text,
        "share_message": share_message,
        "share_links": {
            "whatsapp": f"https://wa.me/?text={encoded_message}",
            "telegram": f"https://t.me/share/url?url={encoded_url}&text={encoded_text}",
            "email": f"mailto:?subject={quote(share_title, safe='')}&body={encoded_message}",
        },
        "back_url": reverse("portal_alerta_detalhe", args=[alerta.id]),
    }
    context.update(
        {
            "seo_title": f"Compartilhar alerta {alert_content['hero_title']} | NC Fly News",
            "seo_description": f"Compartilhe o alerta {alert_content['hero_title']} da NC Fly.",
            "seo_canonical_url": request.build_absolute_uri(
                reverse("portal_alerta_compartilhar", args=[alerta.id])
            ),
            "seo_robots": "noindex,follow",
        }
    )
    track_page_view(
        request.path,
        request=request,
        section="public_alert_share",
        article_category=alerta.programa_fidelidade,
        article_topic=alerta.cidade_destino,
    )
    return render(request, "portal/alerta_compartilhar.html", context)


def plataforma_saas(request):
    quick_lead_form = PlataformaQuickLeadForm(request.POST or None)
    quick_lead_submitted = request.GET.get("lead") == "ok"

    if request.method == "POST" and quick_lead_form.is_valid():
        source_environment, source_host = get_request_site_context(request)
        lead = quick_lead_form.save(
            consent_version=PLATFORM_LEAD_CONSENT_VERSION,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            url_origem=get_request_url(request),
            source_environment=source_environment,
            source_host=source_host,
        )
        notify_platform_lead(lead, capture_label="Interesse rapido na landing da plataforma")
        return redirect(f"{reverse('portal_plataforma_saas')}?lead=ok#saas-interesse")

    context = {
        "page_title": "Plataforma NC Fly",
        "page_eyebrow": "Plataforma NC Fly",
        "page_intro": (
            "A Plataforma NC Fly foi criada para organizar cotações, emissões, clientes, alertas "
            "e fidelidade em um único fluxo operacional."
        ),
        "page_updated_at": timezone.localdate(),
        "saas_brand_name": "Plataforma NC Fly",
        "saas_brand_tagline": "Uma visão simples do produto que a NC Fly está preparando para a operação de viagens e milhas.",
        "saas_modules": [
            {
                "title": "Cotações comerciais",
                "description": "Monte cotações com leitura clara, PDF consistente e passagem de contexto para emissão sem retrabalho.",
            },
            {
                "title": "Emissões organizadas",
                "description": "Acompanhe detalhes da emissão, status, bagagem, escalas, PDF e histórico da operação em um fluxo único.",
            },
            {
                "title": "Alertas e oportunidades",
                "description": "Consolide oportunidades de passagens, reduza ruído operacional e mantenha a equipe alinhada com o que vale acionar.",
            },
            {
                "title": "Clientes e interesses de viagem",
                "description": "Cadastre perfis, passageiros frequentes, janelas de viagem e preferências para gerar match automático com alertas.",
            },
            {
                "title": "Contas fidelidade e clubes",
                "description": "Controle saldo, recorrência de clube, custo médio do milheiro e movimentações por conta ou empresa.",
            },
            {
                "title": "Histórico e padrão operacional",
                "description": "Mantenha o contexto de cada atendimento organizado para o time trabalhar com mais consistência.",
            },
        ],
        "saas_flow": [
            {
                "step": "01",
                "title": "Receba o pedido",
                "description": "A equipe transforma rapidamente a demanda em uma cotação organizada e pronta para apresentar.",
            },
            {
                "step": "02",
                "title": "Monte a proposta",
                "description": "Valores, passageiros, voo, observações e PDF comercial ficam alinhados em um único fluxo.",
            },
            {
                "step": "03",
                "title": "Execute a emissão",
                "description": "A aprovação vira emissão com dados reaproveitados, validações operacionais e visão clara do voo.",
            },
            {
                "step": "04",
                "title": "Acompanhe e evolua",
                "description": "Alertas, interesses de viagem e histórico ajudam a equipe a agir mais rápido e manter padrão ao longo do tempo.",
            },
        ],
        "saas_benefits": [
            {
                "title": "Menos retrabalho",
                "description": "Os dados atravessam a operação de forma coerente entre cotação, emissão, alertas e cliente.",
            },
            {
                "title": "Mais padrão comercial",
                "description": "PDFs, visualizações e propostas ficam com leitura clara e repetível para a equipe inteira.",
            },
            {
                "title": "Resposta mais rápida",
                "description": "Clientes, interesses, alertas e histórico ficam no mesmo ambiente, acelerando a tomada de decisão.",
            },
        ],
        "saas_outcomes": [
            "Mais rapidez para transformar pedido em proposta e proposta em emissão.",
            "Mais clareza para o cliente enxergar o valor da cotação e da entrega da sua equipe.",
            "Mais padrão interno para o time operar sem depender de memória ou processo solto.",
            "Mais contexto para aproveitar alertas e oportunidades comerciais na hora certa.",
        ],
        "saas_focus_points": [
            {
                "title": "Seu time vende melhor",
                "description": "Cotações mais claras, resposta mais rápida e uma apresentação comercial mais consistente.",
            },
            {
                "title": "Sua operação fica mais enxuta",
                "description": "Menos retrabalho entre etapas e menos perda de contexto quando o atendimento avança.",
            },
            {
                "title": "Seu relacionamento evolui",
                "description": "Clientes, interesses e oportunidades ficam organizados para a equipe agir no momento certo.",
            },
        ],
        "saas_audience": [
            {
                "title": "Agências especializadas",
                "description": "Para operações que precisam responder rápido, com proposta elegante e controle da execução.",
            },
            {
                "title": "Consultorias de milhas",
                "description": "Para times que lidam com programas, custos de milheiro, emissão e oportunidades recorrentes.",
            },
            {
                "title": "Operações de viagens sob medida",
                "description": "Para times que precisam organizar atendimento, proposta, emissão e relacionamento com mais clareza.",
            },
        ],
        "saas_faqs": [
            {
                "question": "A Plataforma NC Fly substitui a página inicial pública?",
                "answer": (
                    "Não. A página inicial pública continua como camada editorial e de aquisição. A Plataforma NC Fly é a "
                    "camada de operação para empresas que querem organizar melhor o atendimento e a execução."
                ),
            },
            {
                "question": "Para quem a Plataforma NC Fly foi pensada?",
                "answer": (
                    "Para agências, consultorias de milhas e operações de viagens que precisam "
                    "centralizar proposta, execução e relacionamento em um único sistema."
                ),
            },
            {
                "question": "O que a plataforma cobre hoje?",
                "answer": (
                    "Hoje a plataforma cobre cotações, emissões, clientes, passageiros frequentes, "
                    "contas fidelidade, alertas de passagens e interesses de viagem."
                ),
            },
            {
                "question": "Qual é o principal ganho para a operação?",
                "answer": (
                    "Mais velocidade para responder, menos retrabalho entre etapas e mais padrão "
                    "na forma como a equipe vende, emite e acompanha cada caso."
                ),
            },
        ],
        "quick_lead_submitted": quick_lead_submitted,
        "quick_lead_form": quick_lead_form,
    }
    context.update(_build_saas_page_seo(request))
    track_page_view(request.path, request=request, section="saas")
    return render(request, "portal/plataforma_saas.html", context)


def plataforma_contato(request):
    form = PlataformaLeadForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        source_environment, source_host = get_request_site_context(request)
        lead = form.save(commit=False)
        lead.aceite_versao = PLATFORM_LEAD_CONSENT_VERSION
        lead.aceito_em = timezone.now()
        lead.aceito_ip = get_client_ip(request)
        lead.aceito_user_agent = get_user_agent(request)
        lead.aceito_url_origem = get_request_url(request)
        lead.source_environment = source_environment
        lead.source_host = source_host
        lead.status = LeadPlataforma.STATUS_CHOICES[0][0]
        lead.save()
        notify_platform_lead(lead, capture_label="Formulario completo de contato da plataforma")
        messages.success(
            request,
            "Recebemos seu contato. A equipe da NC Fly vai analisar seu contexto e retornar em breve.",
        )
        return redirect("portal_plataforma_contato")

    context = {
        "page_title": "Solicitar apresentação",
        "page_eyebrow": "Contato comercial",
        "page_intro": (
            "Preencha os dados da sua operação para falar com a NC Fly sobre a plataforma "
            "e entender como organizar cotações, emissões, clientes, alertas e fidelidade."
        ),
        "page_updated_at": timezone.localdate(),
        "lead_form": form,
        "lead_consent_version": PLATFORM_LEAD_CONSENT_VERSION,
        "lead_highlights": [
            "Cotações e emissões conectadas no mesmo fluxo.",
            "Clientes, alertas e interesses organizados em uma base única.",
            "Mais padrão comercial, menos retrabalho e resposta mais rápida.",
        ],
        "lead_benefits": [
            {
                "title": "Diagnóstico rápido",
                "description": "A equipe entende seu momento atual e aponta por onde a implantação deve começar.",
            },
            {
                "title": "Fluxo mais claro",
                "description": "Mapeamos como a plataforma ajuda a organizar proposta, emissão, alertas e relacionamento.",
            },
            {
                "title": "Apresentação objetiva",
                "description": "Você recebe uma visão comercial simples do produto e de como ele pode encaixar na sua operação.",
            },
        ],
        "lead_steps": [
            {"title": "Você envia o contexto", "description": "Nome, empresa, contato e o que mais pesa hoje na sua operação."},
            {"title": "A NC Fly entra em contato", "description": "A equipe comercial retorna para entender volume, equipe e prioridades."},
            {"title": "Avaliação da aderência", "description": "Você vê onde a plataforma encaixa no seu processo e o que faz sentido para o seu momento."},
        ],
        "lead_acceptance_summary": (
            "Ao enviar, você autoriza o contato comercial da NC Fly e confirma que leu o resumo "
            "do uso deste formulário."
        ),
    }
    context.update(_build_saas_contact_page_seo(request))
    track_page_view(request.path, request=request, section="saas_contact")
    return render(request, "portal/plataforma_contato.html", context)


def _build_all_news_seo(request, featured=None, listed_items=None):
    canonical_url = _absolute_public_url(request, reverse("portal_noticias_todas"))
    home_url = _absolute_public_url(request, reverse("portal_home"))
    title = "Notícias de Milhas e Passagens | NC Fly"
    description = (
        "Acompanhe as últimas notícias sobre milhas aéreas, cartões de crédito e hotéis. "
        "Estratégias práticas para viajar gastando menos."
    )
    item_list_schema = _build_item_list_schema(
        canonical_url,
        "Notícias NC Fly",
        [
            {"name": item.titulo, "url": _absolute_public_url(request, item.get_absolute_url())}
            for item in (listed_items or [])[:12]
            if item
        ],
    )
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        {
            "@type": "CollectionPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": _seo_text(title),
            "description": _seo_description(description),
            "isPartOf": {"@id": f"{home_url}#website"},
            "inLanguage": "pt-BR",
        },
        _build_breadcrumb_schema(
            [
                {"name": "Início", "url": home_url},
                {"name": "Notícias", "url": canonical_url},
            ]
        ),
        item_list_schema,
    )
    return _build_seo_context(
        request,
        title=title,
        description=description,
        canonical_url=canonical_url,
        image_url=featured.imagem_exibicao if featured else "",
        robots="index,follow",
        schema_json=schema_json,
        section="Notícias",
        keywords=["notícias", "milhas", "passagens", "cartões de crédito", "hotéis"],
    )


def noticias_todas(request):
    alert_email_lead_form, alert_email_lead_submitted, alert_email_lead_redirect = _handle_alert_email_lead_form(
        request,
        source_page=LeadAlertaEmail.ORIGEM_ALERTAS,
        success_anchor="alertas-email-lead",
    )
    if alert_email_lead_redirect:
        return alert_email_lead_redirect

    noticias = _get_published_news()
    GRID_INITIAL = 10
    featured = noticias[0] if noticias else None
    sidebar_cards = noticias[1:2]
    grid_cards = noticias[2:GRID_INITIAL]
    visible_count = (1 if featured else 0) + len(sidebar_cards) + len(grid_cards)
    hidden_cards = noticias[visible_count:]
    remaining_count = max(len(noticias) - visible_count, 0)
    listed_items = [item for item in [featured, *sidebar_cards, *grid_cards] if item]
    context = {
        "noticias_featured": featured,
        "noticias_sidebar": sidebar_cards,
        "noticias_grid": grid_cards,
        "noticias_hidden": hidden_cards,
        "noticias_total": len(noticias),
        "remaining_count": remaining_count,
        "show_load_more": remaining_count > 0,
        "alertas_home": [],
        "alert_email_lead_form": alert_email_lead_form,
        "alert_email_lead_submitted": alert_email_lead_submitted,
        "alert_email_lead_consent_version": ALERT_EMAIL_LEAD_CONSENT_VERSION,
        "alert_email_lead_section_id": "noticias-alertas-email",
        "alert_email_lead_title": "Quer receber alertas por e-mail?",
        "alert_email_lead_compact_copy": True,
    }
    context.update(_build_all_news_seo(request, featured=featured, listed_items=listed_items))
    track_page_view(request.path, request=request, section="noticias_todas")
    return render(request, "portal/noticias.html", context)


def _first_free_artigo_id() -> int | None:
    """ID do primeiro artigo publicado do primeiro modulo ativo (preview publica)."""
    from .models import ModuloEstudo
    modulo = ModuloEstudo.objects.filter(ativo=True).order_by("ordem", "id").first()
    if not modulo:
        return None
    artigo = modulo.artigos.filter(status="published").order_by("ordem", "id").first()
    return artigo.pk if artigo else None


def _artigo_destaque_categoria():
    """Retorna o artigo destaque (primeiro livre) para exibir como card em categorias."""
    from .models import ModuloEstudo
    modulo = (
        ModuloEstudo.objects.filter(ativo=True)
        .order_by("ordem", "id")
        .prefetch_related("artigos")
        .first()
    )
    if not modulo:
        return None
    artigo = modulo.artigos.filter(status="published").order_by("ordem", "id").first()
    if not artigo:
        return None
    return {
        "artigo": artigo,
        "modulo": modulo,
    }


def artigos_lista(request):
    """Hub publico dos artigos educativos.

    Lista modulos e artigos sem exigir login — o gate e feito por artigo
    (primeiro do modulo 1 e livre; demais exigem login do portal B2C).
    """
    from .auth import get_portal_user
    from .models import ModuloEstudo, ArtigoEstudo
    from .services.progresso import (
        anotar_lido_em_artigos,
        anotar_progresso_em_modulos,
    )

    portal_user = get_portal_user(request)
    modulos = list(
        ModuloEstudo.objects.filter(ativo=True).order_by("ordem", "titulo")
    )
    # anota .total_artigos e .progresso (dict) sem N+1
    anotar_progresso_em_modulos(portal_user, modulos)

    artigos_pub = list(
        ArtigoEstudo.objects.filter(status="published")
        .select_related("modulo")
        .order_by("-publicado_em")[:15]
    )
    # anota .lido_pelo_user em cada artigo exibido
    anotar_lido_em_artigos(portal_user, artigos_pub)

    featured = artigos_pub[0] if artigos_pub else None
    sidebar = list(artigos_pub[1:3])
    grid = list(artigos_pub[3:15])
    track_page_view(request.path, request=request, section="artigos_hub")
    ctx = {
        "modulos": modulos,
        "artigos_featured": featured,
        "artigos_sidebar": sidebar,
        "artigos_grid": grid,
        "portal_user_is_authenticated": portal_user is not None,
        "artigo_livre_id": _first_free_artigo_id(),
    }
    ctx.update(_build_artigos_hub_seo(request))
    return render(request, "portal/artigos_hub.html", ctx)


def modulo_detalhe(request, slug):
    """Pagina publica do modulo com lista de artigos.

    Lista sem exigir login — ao entrar em cada artigo o gate individual decide
    (primeiro do modulo 1 e livre; demais exigem login).
    """
    from .auth import get_portal_user
    from .models import ModuloEstudo
    from .services.progresso import (
        anotar_lido_em_artigos,
        anotar_progresso_em_modulos,
        calcular_progresso_modulo,
    )

    portal_user = get_portal_user(request)
    modulo = get_object_or_404(ModuloEstudo, slug=slug, ativo=True)
    artigos = list(
        modulo.artigos.filter(status="published").order_by("ordem", "titulo")
    )
    anotar_lido_em_artigos(portal_user, artigos)

    progresso = calcular_progresso_modulo(portal_user, modulo)

    outros = list(
        ModuloEstudo.objects.filter(ativo=True)
        .exclude(pk=modulo.pk)
        .order_by("ordem", "titulo")
    )
    anotar_progresso_em_modulos(portal_user, outros)

    track_page_view(request.path, request=request, section="modulo_detalhe")
    ctx = {
        "modulo": modulo,
        "artigos": artigos,
        "outros_modulos": outros,
        "progresso_modulo": progresso,
        "portal_user_is_authenticated": portal_user is not None,
        "artigo_livre_id": _first_free_artigo_id(),
    }
    ctx.update(_build_modulo_seo(request, modulo))
    return render(request, "portal/modulo_detalhe.html", ctx)


def artigo_detalhe(request, modulo_slug, slug):
    """Pagina completa de um artigo educativo.

    Gate parcial: o primeiro artigo do primeiro modulo e livre; demais exigem
    login no portal B2C.
    """
    from .auth import get_portal_user
    from .models import ArtigoEstudo, ProgressoArtigo
    from .services.progresso import calcular_progresso_modulo

    portal_user = get_portal_user(request)
    artigo = get_object_or_404(ArtigoEstudo.objects.select_related("modulo"), slug=slug, status="published")
    if artigo.modulo.slug != modulo_slug:
        return redirect(artigo.get_absolute_url(), permanent=True)

    artigo_livre = artigo.pk == _first_free_artigo_id()

    # --- Paywall (flexible sampling) ---
    # Anonimo sem direito livre recebe preview (4 paragrafos) + paywall card.
    # Googlebot/Bingbot verificados via FCrDNS recebem corpo completo — asim o
    # conteudo e indexado, mas o usuario humano precisa se cadastrar para ler
    # tudo. Sem o redirect antigo (que bloqueava Google de indexar).
    from .services.paywall import (
        is_verified_search_bot,
        truncar_corpo_artigo,
        extrair_titulos_h2,
    )

    search_bot_verificado = False
    if portal_user is None and not artigo_livre:
        search_bot_verificado = is_verified_search_bot(
            get_client_ip(request),
            get_user_agent(request),
        )
    paywall_ativo = portal_user is None and not artigo_livre and not search_bot_verificado

    conteudo_exibido = artigo.conteudo
    paywall_titulos = []
    if paywall_ativo:
        conteudo_exibido = truncar_corpo_artigo(artigo.conteudo, paragrafos=4)
        # Extrai sumario completo do corpo original — usuario anonimo ve os temas
        # todos do artigo mesmo com paywall ativo (incentivo a cadastrar).
        paywall_titulos = extrair_titulos_h2(artigo.conteudo)

    # --- Registra visita do usuario logado (nao marca como lido automaticamente) ---
    # Decisao de produto: marcacao de "lido" e MANUAL via botao ao fim do artigo.
    # Motivos: (a) respeitar intencao do leitor, (b) evitar marcar lido por scroll
    # acidental, (c) leitor que da half-scroll volta depois e retoma do ponto certo.
    # Criamos aqui apenas a linha de "visita" com progresso 0 se ainda nao existir,
    # para permitir futuramente medir tempo/scroll sem alterar estado "lido".
    progresso_artigo = None
    if portal_user is not None:
        progresso_artigo, _ = ProgressoArtigo.objects.get_or_create(
            user=portal_user,
            artigo=artigo,
            defaults={"progresso_percentual": 0},
        )

    videos = artigo.videos.filter(ativo=True).order_by("ordem")
    irmaos = list(artigo.modulo.artigos.filter(status="published").order_by("ordem", "titulo").values_list("pk", flat=True))
    anterior = proximo = None
    if artigo.pk in irmaos:
        idx = irmaos.index(artigo.pk)
        if idx > 0:
            anterior = ArtigoEstudo.objects.select_related("modulo").get(pk=irmaos[idx - 1])
        if idx < len(irmaos) - 1:
            proximo = ArtigoEstudo.objects.select_related("modulo").get(pk=irmaos[idx + 1])
    relacionados = artigo.modulo.artigos.filter(status="published").exclude(pk=artigo.pk).select_related("modulo").order_by("ordem")[:4]

    progresso_modulo = calcular_progresso_modulo(portal_user, artigo.modulo)
    artigo_lido = bool(progresso_artigo and progresso_artigo.lido_em)

    # --- Comentarios (pagina inicial embutida; mais via AJAX) ---
    from .services import comentarios as comentarios_service
    from .models import ComentarioArtigo

    COMENT_POR_PAGINA = 10
    comentarios_items, comentarios_total = comentarios_service.listar_publicados_para_artigo(
        artigo, limit=COMENT_POR_PAGINA, offset=0,
    )
    viewer_pk = portal_user.pk if portal_user else None

    def _serializa(c):
        pode = (
            viewer_pk is not None
            and c.autor_id == viewer_pk
            and c.dentro_janela_edicao
            and c.is_publicado
        )
        return {
            "id": c.pk,
            "parent_id": c.parent_id,
            "corpo": c.corpo,
            "nome_exibicao": c.nome_exibicao,
            "inicial": c.inicial_avatar,
            "criado_em": c.criado_em,
            "editado": c.editado,
            "pode_editar": pode,
            "pode_excluir": pode,
        }

    comentarios_render = []
    for c in comentarios_items:
        item = _serializa(c)
        respostas = [
            _serializa(r)
            for r in c.respostas.all()
            if r.status == ComentarioArtigo.STATUS_PUBLICADO
        ]
        item["respostas"] = respostas
        comentarios_render.append(item)

    track_page_view(request.path, request=request, section="artigo_detalhe")
    ctx = {
        "artigo": artigo,
        "artigo_conteudo_exibido": conteudo_exibido,
        "paywall_ativo": paywall_ativo,
        "paywall_titulos": paywall_titulos,
        "videos": videos,
        "artigo_anterior": anterior,
        "artigo_proximo": proximo,
        "artigos_relacionados": relacionados,
        "progresso_modulo": progresso_modulo,
        "artigo_lido": artigo_lido,
        "artigo_livre": artigo_livre,
        "portal_user_is_authenticated": portal_user is not None,
        "portal_user_nome": (portal_user.nome or portal_user.email) if portal_user else "",
        "comentarios": comentarios_render,
        "comentarios_total": comentarios_total,
        "comentarios_tem_mais": comentarios_total > len(comentarios_render),
        "comentarios_por_pagina": COMENT_POR_PAGINA,
    }
    ctx.update(_build_artigo_seo(request, artigo))
    response = render(request, "portal/artigo_detalhe.html", ctx)
    # CDN anti-leak: artigo gated varia por autenticacao/FCrDNS. Desliga cache
    # compartilhado para nao servir preview ao Googlebot (ou vice-versa).
    response["Cache-Control"] = "private, no-cache, no-store, must-revalidate"
    response["Vary"] = "Cookie, User-Agent"
    return response


@require_POST
def artigo_marcar_lido(request, slug):
    """Marca um artigo como lido para o PortalUser logado.

    POST /home/artigo/<slug>/marcar-lido/
    Autentica via `portal_login_required` — responde JSON para AJAX ou
    redirect 303 para fluxo sem JS.

    Retorna:
        JSON: { "status": "ok", "percentual_modulo": N, "concluido": bool }
    """
    from .auth import get_portal_user
    from .models import ArtigoEstudo, ProgressoArtigo
    from .services.progresso import calcular_progresso_modulo

    portal_user = get_portal_user(request)
    if portal_user is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"status": "unauthenticated"}, status=401)
        login_url = reverse("portal_login")
        return redirect(f"{login_url}?next={request.path}")

    artigo = get_object_or_404(
        ArtigoEstudo.objects.select_related("modulo"),
        slug=slug,
        status="published",
    )
    progresso, _ = ProgressoArtigo.objects.update_or_create(
        user=portal_user,
        artigo=artigo,
        defaults={
            "lido_em": timezone.now(),
            "progresso_percentual": 100,
        },
    )

    payload = calcular_progresso_modulo(portal_user, artigo.modulo)

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )
    if wants_json:
        return JsonResponse(
            {
                "status": "ok",
                "artigo_slug": artigo.slug,
                "percentual_modulo": payload["percentual"],
                "lidos": payload["lidos"],
                "total_artigos": payload["total_artigos"],
                "status_modulo": payload["status"],
                "concluido": payload["status"] == "concluido",
            }
        )
    # Fluxo sem JS — redirect 303 para a propria pagina do artigo
    return redirect(artigo.get_absolute_url())


# -- SEO helpers artigos --
def _build_artigos_hub_seo(request):
    canonical_url = _absolute_public_url(request, reverse("portal_artigos"))
    base_url = _public_base_url(request)
    title = "Aprenda sobre Milhas e Viagens | NC Fly"
    description = (
        "Guias completos e artigos educativos para dominar o universo das milhas aéreas."
    )
    breadcrumb_items = [
        {"name": "Início", "url": _absolute_public_url(request, reverse("portal_home"))},
        {"name": "Artigos", "url": canonical_url},
    ]
    collection_schema = {
        "@type": "CollectionPage",
        "@id": f"{canonical_url}#collection",
        "url": canonical_url,
        "name": "Artigos educativos de milhas",
        "description": _seo_description(description),
        "isPartOf": {"@id": f"{base_url}#website"},
        "inLanguage": "pt-BR",
    }
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        collection_schema,
        _build_breadcrumb_schema(breadcrumb_items),
    )
    return _build_seo_context(
        request,
        title=title,
        description=description,
        canonical_url=canonical_url,
        schema_json=schema_json,
    )


def _build_modulo_seo(request, modulo):
    canonical_url = _absolute_public_url(request, modulo.get_absolute_url())
    base_url = _public_base_url(request)
    title = f"{modulo.titulo} — Artigos | NC Fly"
    description = Truncator(modulo.descricao or modulo.titulo).chars(155)
    breadcrumb_items = [
        {"name": "Início", "url": _absolute_public_url(request, reverse("portal_home"))},
        {"name": "Artigos", "url": _absolute_public_url(request, reverse("portal_artigos"))},
        {"name": modulo.titulo, "url": canonical_url},
    ]
    collection_schema = {
        "@type": "CollectionPage",
        "@id": f"{canonical_url}#collection",
        "url": canonical_url,
        "name": modulo.titulo,
        "description": _seo_description(description),
        "isPartOf": {"@id": f"{base_url}#website"},
        "inLanguage": "pt-BR",
    }
    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        collection_schema,
        _build_breadcrumb_schema(breadcrumb_items),
    )
    return _build_seo_context(
        request,
        title=title,
        description=description,
        canonical_url=canonical_url,
        schema_json=schema_json,
    )


def _build_artigo_seo(request, artigo):
    canonical_url = _absolute_public_url(request, artigo.get_absolute_url())
    base_url = _public_base_url(request)
    headline = artigo.seo_title or artigo.titulo
    description = artigo.meta_description or Truncator(artigo.resumo or artigo.titulo).chars(155)
    image_raw = artigo.imagem_exibicao or ""
    image_url = _absolute_image_url(request, image_raw)
    body_text = strip_tags(artigo.conteudo or "")
    word_count = len(body_text.split())
    modulo = artigo.modulo
    article_schema = {
        "@type": "Article",
        "@id": f"{canonical_url}#article",
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical_url},
        "headline": _seo_text(headline),
        "description": _seo_description(description),
        "author": {"@type": "Organization", "name": artigo.autor or "NC Fly"},
        "publisher": {"@id": f"{base_url}#organization"},
        "url": canonical_url,
        "inLanguage": "pt-BR",
        "wordCount": word_count,
        "isPartOf": {"@id": f"{base_url}#website"},
    }
    # Flexible sampling oficial (developers.google.com/search/docs/appearance/paywalled-content):
    # quando o artigo exige login, marca isAccessibleForFree=false e aponta a
    # parte paga via cssSelector. Googlebot verificado via FCrDNS recebe o HTML
    # completo; humanos veem apenas o preview. Sem isso = cloaking.
    if not artigo.pk == _first_free_artigo_id():
        article_schema["isAccessibleForFree"] = False
        article_schema["hasPart"] = {
            "@type": "WebPageElement",
            "isAccessibleForFree": False,
            "cssSelector": ".artigo-detalhe-corpo",
        }
    if artigo.publicado_em:
        article_schema["datePublished"] = timezone.localtime(artigo.publicado_em).isoformat()
    if artigo.atualizado_em:
        article_schema["dateModified"] = timezone.localtime(artigo.atualizado_em).isoformat()
    if image_url:
        article_schema["image"] = [image_url]
        article_schema["thumbnailUrl"] = image_url
    if modulo:
        article_schema["articleSection"] = _seo_text(modulo.titulo)
    keywords = []
    if isinstance(artigo.keywords_json, list):
        keywords = [str(kw).strip() for kw in artigo.keywords_json if str(kw).strip()]
    if keywords:
        article_schema["keywords"] = [_seo_text(kw) for kw in keywords]

    breadcrumb_items = [
        {"name": "Início", "url": _absolute_public_url(request, reverse("portal_home"))},
        {"name": "Artigos", "url": _absolute_public_url(request, reverse("portal_artigos"))},
    ]
    if modulo:
        breadcrumb_items.append(
            {"name": modulo.titulo, "url": _absolute_public_url(request, modulo.get_absolute_url())}
        )
    breadcrumb_items.append({"name": artigo.titulo, "url": canonical_url})

    schema_json = _build_schema_graph(
        _build_organization_schema(request),
        _build_website_schema(request),
        article_schema,
        _build_breadcrumb_schema(breadcrumb_items),
    )
    return _build_seo_context(
        request,
        title=f"{headline} | NC Fly",
        description=description,
        canonical_url=canonical_url,
        image_url=image_raw,
        og_type="article",
        schema_json=schema_json,
        published_time=artigo.publicado_em,
        modified_time=artigo.atualizado_em,
        section=modulo.titulo if modulo else "",
        keywords=keywords,
    )


def categoria_lista(request, categoria_slug):
    alert_email_lead_form, alert_email_lead_submitted, alert_email_lead_redirect = _handle_alert_email_lead_form(
        request,
        source_page=LeadAlertaEmail.ORIGEM_ALERTAS,
        success_anchor="alertas-email-lead",
    )
    if alert_email_lead_redirect:
        return alert_email_lead_redirect

    selected_topic_slug = slugify((request.GET.get("topico") or "").strip())
    context = _build_category_page_context(categoria_slug, selected_topic_slug)
    alertas_home = build_public_alert_cards(
        list_visible_public_alerts(limit=5, max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS)
    )
    context.update(
        {
            "alertas_home": alertas_home,
            "alert_email_lead_form": alert_email_lead_form,
            "alert_email_lead_submitted": alert_email_lead_submitted,
            "alert_email_lead_consent_version": ALERT_EMAIL_LEAD_CONSENT_VERSION,
            "alert_email_lead_section_id": f"categoria-{categoria_slug}-alertas-email",
            "alert_email_lead_compact_copy": True,
            "artigo_destaque_categoria": _artigo_destaque_categoria(),
        }
    )
    context.update(
        _build_category_seo(
            request,
            categoria_slug,
            context["categoria_config"],
            featured=context["featured"],
            selected_topic=context["topico_ativo"],
            listed_items=[
                item
                for item in [context["featured"], *context["sidebar_cards"], *context["grid_cards"]]
                if item
            ],
        )
    )
    track_page_view(
        request.path,
        request=request,
        section="category",
        article_category=context["categoria_config"]["label"],
        article_topic=(context["topico_ativo"] or {}).get("label", ""),
    )
    return render(request, "portal/categoria.html", context)


def noticia_redirect(request, slug):
    noticia = get_object_or_404(NoticiaPublicada, slug=slug)
    return redirect(noticia.get_absolute_url(), permanent=True)


def noticia_detalhe(request, categoria_slug, slug):
    noticia = get_object_or_404(
        NoticiaPublicada.objects.select_related("fonte"),
        slug=slug,
        status="published",
    )
    correct_categoria_slug = _category_slug_from_label(noticia.categoria) or "milhas-e-pontos"
    if categoria_slug != correct_categoria_slug:
        return redirect(noticia.get_absolute_url(), permanent=True)

    relacionadas_qs = (
        NoticiaPublicada.objects.filter(status="published")
        .exclude(pk=noticia.pk)
        .select_related("fonte")
    )
    if noticia.categoria and noticia.topico:
        relacionadas = relacionadas_qs.filter(categoria=noticia.categoria, topico=noticia.topico).order_by("-publicada_em")[:4]
    elif noticia.categoria:
        relacionadas = relacionadas_qs.filter(categoria=noticia.categoria).order_by("-publicada_em")[:4]
    else:
        relacionadas = []
    if not relacionadas:
        relacionadas = relacionadas_qs.order_by("-publicada_em")[:4]

    context = {
        "noticia": noticia,
        "relacionadas": relacionadas,
        "tempo_leitura_minutos": _estimate_read_minutes(noticia.conteudo),
        "breadcrumbs_categoria": noticia.categoria or "Milhas e Pontos",
        "categoria_url": reverse("portal_categoria", kwargs={"categoria_slug": categoria_slug}),
        "topico_url": (
            f"{reverse('portal_categoria', kwargs={'categoria_slug': categoria_slug})}?topico={slugify(noticia.topico)}"
            if noticia.topico
            else None
        ),
        "offer_cta": (noticia.metadata_json or {}).get("offer_cta", {}),
    }
    context.update(_build_article_seo(request, noticia, categoria_slug))
    track_page_view(
        request.path,
        request=request,
        section="article",
        article_slug=noticia.slug,
        article_category=noticia.categoria,
        article_topic=noticia.topico,
    )
    return render(request, "portal/detalhe.html", context)


def sobre_nos(request):
    context = {
        "page_title": "Sobre a empresa",
        "page_eyebrow": "Institucional",
        "page_intro": "Conheça o posicionamento editorial, os princípios de transparência e a proposta do portal público da NC Fly News.",
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_sobre",
            title="Sobre a empresa",
            description="Conheça a proposta editorial, os critérios de transparência e a forma como o portal NC Fly News organiza seu conteúdo público.",
        )
    )
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/sobre_nos.html", context)


def sobre_empresa_publica(request):
    context = {
        "page_title": "Sobre a empresa",
        "page_eyebrow": "Institucional",
        "page_intro": "Conheça a NC Fly, a forma como a empresa organiza sua atuação e o papel do portal público dentro desse ecossistema.",
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_sobre",
            title="Sobre a empresa",
            description="Conheça a NC Fly, seu posicionamento, seus princípios e a relação entre o portal público, os alertas e a plataforma.",
        )
    )
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/sobre_nos.html", context)


def fale_conosco(request):
    context = {
        "page_title": "Fale Conosco",
        "page_eyebrow": "Institucional",
        "page_intro": "Canal institucional da NC Fly para orientar o tipo de assunto e centralizar futuros meios de contato da empresa.",
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_fale_conosco",
            title="Fale Conosco",
            description="Página institucional da NC Fly para contato, assuntos comerciais, parcerias e orientações gerais sobre a empresa.",
        )
    )
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/fale_conosco.html", context)


def politica_privacidade(request):
    context = {
        "page_title": "Política de Privacidade",
        "page_eyebrow": "Privacidade",
        "page_intro": "Entenda como o portal trata dados pessoais, informações de navegação, métricas de acesso e exercício de direitos do titular.",
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_privacidade",
            title="Política de Privacidade",
            description="Política de privacidade do portal NC Fly News, com bases legais, direitos do titular, cookies, métricas de acesso e compartilhamento de dados.",
        )
    )
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/politica_privacidade.html", context)


def termos_de_uso(request):
    context = {
        "page_title": "Termos de Uso",
        "page_eyebrow": "Termos",
        "page_intro": "Regras de uso do portal, limites de responsabilidade, propriedade intelectual e links externos.",
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_termos",
            title="Termos de Uso",
            description="Termos de uso do portal NC Fly News para navegação pública, conteúdo editorial, links externos e propriedade intelectual.",
        )
    )
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/termos_uso.html", context)


def termos_alertas_email(request):
    context = {
        "page_title": "Termos de Recebimento de Alertas",
        "page_eyebrow": "Alertas por e-mail",
        "page_intro": (
            "Regras aplicáveis ao cadastro de nome, e-mail e telefone para receber alertas "
            "de passagens e comunicações associadas a esse serviço."
        ),
        "page_updated_at": timezone.localdate(),
        "alert_email_lead_consent_version": ALERT_EMAIL_LEAD_CONSENT_VERSION,
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_termos_alertas_email",
            title="Termos de Recebimento de Alertas",
            description=(
                "Termos do cadastro para receber alertas por e-mail no portal NC Fly News, "
                "com finalidade, dados coletados, registro do aceite e cancelamento."
            ),
        )
    )
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/termos_alertas_email.html", context)


def alertas_email_unsubscribe(request):
    token = (request.POST.get("token") or request.GET.get("token") or "").strip()
    token_email = get_email_from_unsubscribe_token(token) if token else None
    lead = get_alert_email_lead_by_unsubscribe_token(token) if token else None
    token_has_active_subscription = (
        has_active_alert_subscription_for_token(token) if token else False
    )
    form = AlertEmailUnsubscribeForm(request.POST or None)
    context = {
        "lead": lead,
        "token": token,
        "token_email": token_email,
        "form": form,
        "unsubscribe_success": False,
        "unsubscribe_cancelled": False,
        "already_unsubscribed": bool(token_email and not token_has_active_subscription),
    }

    if not token_email:
        return render(
            request,
            "portal/alertas_unsubscribe_result.html",
            context,
            status=400,
        )

    if request.method == "POST":
        if request.POST.get("action") == "cancel":
            context["unsubscribe_cancelled"] = True
            context["already_unsubscribed"] = False
            return render(request, "portal/alertas_unsubscribe_result.html", context)

        if form.is_valid():
            lead = unsubscribe_alert_email_by_token(token, motivo=form.cleaned_data["motivo"])
            context.update(
                {
                    "lead": lead,
                    "unsubscribe_success": True,
                    "already_unsubscribed": False,
                    "motivo_label": lead.get_motivo_cancelamento_display() if lead else "",
                }
            )
            return render(request, "portal/alertas_unsubscribe_result.html", context)

        context["already_unsubscribed"] = False

    return render(
        request,
        "portal/alertas_unsubscribe_result.html",
        context,
    )


def privacidade_plataforma(request):
    context = {
        "page_title": "Privacidade da Plataforma",
        "page_eyebrow": "Área logada",
        "page_intro": (
            "Aviso de privacidade específico para acesso autenticado, painel, administração, auditoria, "
            "operação de clientes, emissões, cotações e demais fluxos autenticados."
        ),
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_privacidade_plataforma",
            title="Privacidade da Plataforma",
            description=(
                "Aviso de privacidade da área logada da NC Fly, com tratamento de dados "
                "operacionais, registros técnicos de acesso, segurança, auditoria e execução contratual."
            ),
            robots="noindex,follow",
        )
    )
    context.update(_build_platform_document_context(DocumentoPlataforma.TIPO_PRIVACIDADE))
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/privacidade_plataforma.html", context)


def termos_plataforma(request):
    context = {
        "page_title": "Termos da Plataforma",
        "page_eyebrow": "Área logada",
        "page_intro": (
            "Regras específicas para uso da plataforma autenticada da NC Fly, incluindo "
            "credenciais, perfis de acesso, segurança, auditoria e responsabilidades operacionais."
        ),
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_termos_plataforma",
            title="Termos da Plataforma",
            description=(
                "Termos da plataforma autenticada da NC Fly para acesso, área logada, "
                "segurança, perfis, auditoria, uso operacional e responsabilidade do usuário."
            ),
            robots="noindex,follow",
        )
    )
    context.update(_build_platform_document_context(DocumentoPlataforma.TIPO_TERMOS))
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/termos_plataforma.html", context)


def dpa_plataforma(request):
    context = {
        "page_title": "Aditivo de Tratamento de Dados",
        "page_eyebrow": "Área logada",
        "page_intro": (
            "Documento-base para distribuição de papéis, instruções, suboperadores, "
            "incidentes e obrigações de proteção de dados na plataforma como serviço da NC Fly."
        ),
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_dpa_plataforma",
            title="Aditivo de Tratamento de Dados",
            description=(
                "Documento-base da plataforma NC Fly sobre controlador, operador, "
                "suboperadores, incidentes, segurança e tratamento de dados no contexto da plataforma como serviço."
            ),
            robots="noindex,follow",
        )
    )
    context.update(_build_platform_document_context(DocumentoPlataforma.TIPO_DPA))
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/dpa_plataforma.html", context)


def seguranca_plataforma(request):
    context = {
        "page_title": "Política de Segurança e Uso Aceitável",
        "page_eyebrow": "Área logada",
        "page_intro": (
            "Diretrizes de segurança, uso aceitável, proteção de credenciais, "
            "restrições técnicas e responsabilidades operacionais dos usuários autenticados."
        ),
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_seguranca_plataforma",
            title="Política de Segurança e Uso Aceitável",
            description=(
                "Regras de segurança e uso aceitável da plataforma NC Fly, "
                "com foco em credenciais, auditoria, proteção de dados e prevenção de abuso."
            ),
            robots="noindex,follow",
        )
    )
    context.update(_build_platform_document_context(DocumentoPlataforma.TIPO_SEGURANCA))
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/seguranca_plataforma.html", context)


@login_required
def aceite_documentos_plataforma(request):
    pendencias = get_pendencias_aceite_empresa(request.user)
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("admin_dashboard")

    if not pendencias:
        return redirect(next_url)

    if request.method == "POST":
        if request.POST.get("platform_accept") != "1":
            messages.error(
                request,
                "Marque o checkbox de aceite para continuar na plataforma.",
            )
        else:
            registrar_aceites_empresa(request, request.user, pendencias)
            messages.success(request, "Documentos da plataforma aceitos com sucesso.")
            return redirect(next_url)

    context = {
        "page_title": "Aceite dos documentos da plataforma",
        "page_eyebrow": "Primeiro acesso da empresa",
        "page_intro": (
            "Para continuar na área logada, confirme o pacote atual de documentos da "
            "plataforma vinculado à empresa do seu acesso."
        ),
        "page_updated_at": timezone.localdate(),
        "pendencias": [
            {
                "documento": documento,
                "url": get_documento_platform_url(documento.tipo),
            }
            for documento in pendencias
        ],
        "next_url": next_url,
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_aceite_plataforma",
            title="Aceite dos documentos da plataforma",
            description="Página de aceite dos documentos jurídicos vigentes da plataforma NC Fly.",
            robots="noindex,nofollow",
        )
    )
    return render(request, "portal/aceite_plataforma.html", context)


def ads_txt(request):
    return HttpResponse(
        "google.com, pub-8670696864452622, DIRECT, f08c47fec0942fa0",
        content_type="text/plain; charset=utf-8",
    )


def sitemap_news_xml(request):
    """Google News sitemap (namespace news:).

    Inclui apenas noticias publicadas nos ultimos 2 dias (janela recomendada
    pelo Google). Aparece no Top Stories apenas apos aprovacao no Publisher
    Center; sem isso funciona como hint opcional para o crawler.
    """
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=2)
    recent = (
        NoticiaPublicada.objects.filter(status="published", publicada_em__gte=cutoff)
        .only("slug", "titulo", "categoria", "publicada_em")
        .order_by("-publicada_em")[:1000]
    )
    base_url = _public_base_url(request)
    items = []
    for noticia in recent:
        items.append(
            {
                "loc": f"{base_url}{noticia.get_absolute_url()}",
                "title": noticia.titulo,
                "publication_date": timezone.localtime(noticia.publicada_em).isoformat(),
            }
        )
    return render(
        request,
        "sitemap_news.xml",
        {"items": items, "publication_name": settings.PORTAL_SITE_NAME},
        content_type="application/xml",
    )


def robots_txt(request):
    sitemap_url = _absolute_public_url(request, reverse("portal_sitemap"))
    private_disallow = [
        "Disallow: /adm/",
        "Disallow: /ncadm/",
        "Disallow: /login/",
        "Disallow: /painel/",
        "Disallow: /contratar/",
        "Disallow: /django/admin/",
        "Disallow: /accounts/",
        "Disallow: /webhooks/",
        "Disallow: /auth/",
        "Disallow: /assinatura/",
        "Disallow: /integracoes/",
        "Disallow: /monitoramento/",
    ]
    lines = [
        "User-agent: *",
        *private_disallow,
        "Allow: /home/",
        "Allow: /sitemap.xml",
        "Allow: /ads.txt",
        "Allow: /llms.txt",
    ]
    # AI crawlers — liberados em /home/ para ingestão do conteúdo público
    # (artigos, notícias, alertas), privados bloqueados igual ao User-agent: *.
    for ua in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Google-Extended", "CCBot", "PerplexityBot"):
        lines.append("")
        lines.append(f"User-agent: {ua}")
        lines.extend(private_disallow)
        lines.append("Allow: /home/")
    news_sitemap_url = _absolute_public_url(request, reverse("portal_sitemap_news"))
    lines.append("")
    lines.append(f"Sitemap: {sitemap_url}")
    lines.append(f"Sitemap: {news_sitemap_url}")
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def llms_txt(request):
    base_url = _public_base_url(request)
    sitemap_url = _absolute_public_url(request, reverse("portal_sitemap"))
    home_url = _absolute_public_url(request, reverse("portal_home"))
    sobre_url = _absolute_public_url(request, reverse("portal_sobre"))
    alertas_url = _absolute_public_url(request, reverse("portal_alertas"))
    plataforma_url = _absolute_public_url(request, reverse("portal_plataforma_saas"))
    noticias_url = _absolute_public_url(request, reverse("portal_noticias_todas"))
    cat_milhas_url = f"{base_url}{reverse('portal_categoria', kwargs={'categoria_slug': 'milhas-e-pontos'})}"
    cat_cartoes_url = f"{base_url}{reverse('portal_categoria', kwargs={'categoria_slug': 'cartoes-credito'})}"
    cat_hoteis_url = f"{base_url}{reverse('portal_categoria', kwargs={'categoria_slug': 'hoteis-resorts'})}"
    cat_promocoes_url = f"{base_url}{reverse('portal_categoria', kwargs={'categoria_slug': 'promocoes'})}"
    cat_viagens_url = f"{base_url}{reverse('portal_categoria', kwargs={'categoria_slug': 'viagens'})}"
    privacidade_url = _absolute_public_url(request, reverse("portal_privacidade"))
    termos_url = _absolute_public_url(request, reverse("portal_termos"))
    site_name = settings.PORTAL_SITE_NAME
    legal_name = settings.PORTAL_LEGAL_ENTITY_NAME or site_name
    contact_email = settings.PORTAL_CONTACT_EMAIL or settings.PORTAL_DPO_EMAIL or ""

    lines = [
        f"# {site_name}",
        "",
        (
            f"> {site_name} é um portal editorial brasileiro dedicado ao ecossistema de milhas aéreas, "
            "programas de fidelidade, cartões de crédito com benefícios, alertas de passagens, "
            "hotéis e resorts, e viagens em geral. O conteúdo é produzido em português do Brasil, "
            "voltado ao público brasileiro interessado em maximizar o uso de pontos e milhas. "
            "O portal também oferece a Plataforma NC Fly, um produto SaaS B2B para agências de viagens "
            "que centraliza cotações, emissões, clientes, contas fidelidade e alertas."
        ),
        "",
        "## Páginas principais",
        f"- [Início]({home_url}): página principal com os destaques editoriais mais recentes.",
        f"- [Todas as notícias]({noticias_url}): listagem completa de artigos publicados.",
        f"- [Alertas de passagens]({alertas_url}): alertas públicos de oportunidades de emissão com milhas.",
        f"- [Sobre nós]({sobre_url}): missão, equipe e propósito do portal.",
        f"- [Plataforma NC Fly]({plataforma_url}): produto SaaS B2B para operação de agências de viagens.",
        "",
        "## Categorias editoriais",
        f"- [Milhas e Pontos]({cat_milhas_url}): acúmulo, transferência e uso de milhas nos programas Smiles, Latam Pass, TudoAzul, Livelo e outros.",
        f"- [Cartões de Crédito]({cat_cartoes_url}): análises e comparativos de cartões com benefícios de viagem e acúmulo de pontos.",
        f"- [Hotéis e Resorts]({cat_hoteis_url}): hospedagem com pontos, programas de fidelidade de hotéis e promoções.",
        f"- [Promoções]({cat_promocoes_url}): passagens em promoção, erros de tarifa e oportunidades relâmpago.",
        f"- [Viagens]({cat_viagens_url}): dicas, roteiros e conteúdo geral sobre viagens.",
        "",
        "## Indexação e descoberta",
        f"- Sitemap XML: {sitemap_url}",
        f"- Idioma principal: português do Brasil (pt-BR)",
        "- Frequência de publicação: diária",
        "- Tipo de conteúdo: artigos editoriais originais, alertas e análises",
        "",
        "## Diretrizes editoriais para LLMs",
        "- O conteúdo é editorial e informativo; preços, tarifas e disponibilidade mudam — confirme na fonte original.",
        "- Milhas e pontos têm valor variável; condições dos programas de fidelidade podem ser alteradas pelas companhias aéreas.",
        "- O portal não é afiliado aos programas de fidelidade citados, salvo quando explicitamente indicado.",
        "- Ao citar este portal, use o nome oficial: NC Fly News.",
        "",
        "## Optional",
        f"- [Política de Privacidade]({privacidade_url})",
        f"- [Termos de Uso]({termos_url})",
        f"- Empresa responsável: {legal_name}",
    ]

    if contact_email:
        lines.append(f"- Contato: {contact_email}")

    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


@csrf_exempt
@require_POST
def registrar_evento_publico(request):
    if not _request_is_same_origin(request):
        return JsonResponse({"ok": False, "error": "forbidden_origin"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    accepted = track_click_event(payload, request=request)
    return JsonResponse({"ok": accepted}, status=200 if accepted else 400)
