import json
import unicodedata

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

from accounts.security import get_client_ip, get_user_agent
from .forms import PlataformaLeadForm, PlataformaQuickLeadForm
from .models import NoticiaPublicada
from .models import LeadPlataforma
from .services.metrics import get_request_site_context, track_click_event, track_page_view
from .services.public_alerts import (
    build_public_alert_card,
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
    },
    "cartoes-credito": {
        "label": "Cartões de Crédito",
        "hero_title": "Cartões de Crédito",
        "hero_description": "Reviews completos, comparativos, dicas para aprovação e tudo sobre os melhores cartões de crédito do mercado.",
        "hero_class": "portal-category-hero--cards",
        "icon_variant": "cards",
        "card_class": "news-category-card--purple",
        "aliases": ("cartoes de credito", "cartao", "cartoes", "credito", "visa", "mastercard", "amex"),
        "load_more_label": "Carregar mais notícias",
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
    },
}

SEO_MAX_DESCRIPTION_LENGTH = 160
PLATFORM_LEAD_CONSENT_VERSION = "2026-04-lead"
ALERTS_PUBLIC_PAGE_BATCH_SIZE = 3


def _estimate_read_minutes(text):
    word_count = len((text or "").split())
    return max(1, round(word_count / 180))


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").lower().strip()


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
    if origin and not origin.startswith(base_url):
        return False
    if referer and not referer.startswith(base_url):
        return False
    return True


def _build_organization_schema(request):
    base_url = _public_base_url(request)
    schema = {
        "@type": "Organization",
        "@id": f"{base_url}#organization",
        "name": settings.PORTAL_SITE_NAME,
        "url": base_url,
    }
    logo_url = _absolute_image_url(request, settings.PORTAL_SITE_LOGO_URL)
    if logo_url:
        schema["logo"] = {
            "@type": "ImageObject",
            "url": logo_url,
        }
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


def _build_schema_graph(*nodes):
    graph_nodes = [node for node in nodes if node]
    if not graph_nodes:
        return ""
    return json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": graph_nodes,
        },
        ensure_ascii=False,
    )


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
                {"name": "Home", "url": _absolute_public_url(request, reverse("portal_home"))},
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
                    "A Plataforma NC Fly foi pensada para agências, consultorias e operações B2B "
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
                {"name": "Home", "url": home_url},
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
            "plataforma SaaS para emissões",
            "gestão de cotações e emissão",
            "operação B2B de viagens",
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
            "serviceType": "Plataforma SaaS para operação de viagens",
            "url": canonical_url,
            "description": description,
        },
        _build_breadcrumb_schema(
            [
                {"name": "Home", "url": home_url},
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
        section="Plataforma SaaS",
        robots="noindex,nofollow",
        keywords=[
            "demonstracao plataforma NC Fly",
            "contato comercial software para viagens",
            "plataforma SaaS para agencia de viagens",
            "gestão de cotações e emissões",
        ],
    )


def _build_alerts_list_seo(request):
    canonical_url = _absolute_public_url(request, reverse("portal_alertas"))
    home_url = _absolute_public_url(request, reverse("portal_home"))
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
                {"name": "Home", "url": home_url},
                {"name": "Alertas de passagens", "url": canonical_url},
            ]
        ),
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
                {"name": "Home", "url": home_url},
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


def _filter_public_alerts(alertas, aeroporto="", programa="", companhia=""):
    selected_airport = str(aeroporto or "").strip().upper()
    selected_program = _normalize_text(programa)
    selected_airline = _normalize_text(companhia)

    filtered = []
    for alerta in alertas:
        if selected_airport and selected_airport not in {
            str(alerta.origem or "").strip().upper(),
            str(alerta.destino or "").strip().upper(),
        }:
            continue
        if selected_program and _normalize_text(alerta.programa_fidelidade) != selected_program:
            continue
        if selected_airline and _normalize_text(alerta.companhia_aerea) != selected_airline:
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


def _build_category_seo(request, categoria_slug, categoria_config, featured=None, selected_topic=None):
    canonical_url = _absolute_public_url(
        request, reverse("portal_categoria", kwargs={"categoria_slug": categoria_slug})
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
                {"name": "Home", "url": _absolute_public_url(request, reverse("portal_home"))},
                {"name": categoria_config["label"], "url": canonical_url},
            ]
        ),
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

    breadcrumb_items = [{"name": "Home", "url": _absolute_public_url(request, reverse("portal_home"))}]
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
    ordered = active_pool[:8] if selected_topic else _pick_articles(matching, fallback, 8)
    active_total = len(active_pool) if selected_topic else len(matching)
    featured = ordered[0] if ordered else None
    sidebar_cards = ordered[1:2]
    grid_cards = ordered[2:8]
    visible_count = (1 if featured else 0) + len(sidebar_cards) + len(grid_cards)
    hidden_cards = active_pool[visible_count:] if selected_topic else matching[visible_count:]
    remaining_count = max(active_total - visible_count, 0)
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
    }


def home_publica(request):
    search_query = (request.GET.get("q") or "").strip()
    noticias = _filter_news_by_query(_get_published_news(), search_query)
    is_searching = bool(search_query)
    HOME_INITIAL = 6
    HOME_BATCH = 6
    HOME_MOBILE_INITIAL = 3
    visible = noticias[:HOME_INITIAL]
    hidden = noticias[HOME_INITIAL:]

    alertas_home = [] if is_searching else [build_public_alert_card(alerta) for alerta in list_visible_public_alerts(limit=15)]

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
    visible_alerts = list_visible_public_alerts()
    selected_filters = {
        "aeroporto": (request.GET.get("aeroporto") or "").strip().upper(),
        "programa": (request.GET.get("programa") or "").strip(),
        "companhia": (request.GET.get("companhia") or "").strip(),
    }
    filtered_alerts = _filter_public_alerts(
        visible_alerts,
        aeroporto=selected_filters["aeroporto"],
        programa=selected_filters["programa"],
        companhia=selected_filters["companhia"],
    )
    alert_cards = [build_public_alert_card(alerta) for alerta in filtered_alerts]
    filters_active = any(selected_filters.values())
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
        },
        "alert_results_total": len(alert_cards),
    }
    context.update(_build_alerts_list_seo(request))
    track_page_view(
        request.path,
        request=request,
        section="public_alerts",
        article_category=selected_filters["programa"],
        article_topic=selected_filters["aeroporto"] or selected_filters["companhia"],
    )
    return render(request, "portal/alertas.html", context)


def alerta_publico_detalhe(request, alerta_id):
    alerta = get_object_or_404(AlertaViagem, id=alerta_id, ativo=True)
    if not alerta.deve_aparecer_na_vitrine():
        raise Http404("Alerta não disponível.")

    alert_content = build_public_alert_detail(alerta)
    context = {
        "alerta": alerta,
        "alert_context": alert_content,
        "similar_alerts": build_similar_alert_cards(alerta),
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


def plataforma_saas(request):
    quick_lead_form = PlataformaQuickLeadForm(request.POST or None)
    quick_lead_submitted = request.GET.get("lead") == "ok"

    if request.method == "POST" and quick_lead_form.is_valid():
        source_environment, source_host = get_request_site_context(request)
        quick_lead_form.save(
            consent_version=PLATFORM_LEAD_CONSENT_VERSION,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            source_environment=source_environment,
            source_host=source_host,
        )
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
                "description": "Clientes, interesses e oportunidades ficam organizados para a equipe agir com mais timing.",
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
                "question": "A Plataforma NC Fly substitui a home pública?",
                "answer": (
                    "Não. A home continua como camada editorial e de aquisição. A Plataforma NC Fly é a "
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
        lead.source_environment = source_environment
        lead.source_host = source_host
        lead.status = LeadPlataforma.STATUS_CHOICES[0][0]
        lead.save()
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


def categoria_lista(request, categoria_slug):
    selected_topic_slug = slugify((request.GET.get("topico") or "").strip())
    context = _build_category_page_context(categoria_slug, selected_topic_slug)
    context.update(
        _build_category_seo(
            request,
            categoria_slug,
            context["categoria_config"],
            featured=context["featured"],
            selected_topic=context["topico_ativo"],
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


def noticia_detalhe(request, slug):
    noticia = get_object_or_404(
        NoticiaPublicada.objects.select_related("fonte"),
        slug=slug,
        status="published",
    )
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

    categoria_slug = _category_slug_from_label(noticia.categoria)
    context = {
        "noticia": noticia,
        "relacionadas": relacionadas,
        "tempo_leitura_minutos": _estimate_read_minutes(noticia.conteudo),
        "breadcrumbs_categoria": noticia.categoria or "Milhas e Pontos",
        "categoria_url": reverse("portal_categoria", kwargs={"categoria_slug": categoria_slug}) if categoria_slug else None,
        "topico_url": (
            f"{reverse('portal_categoria', kwargs={'categoria_slug': categoria_slug})}?topico={slugify(noticia.topico)}"
            if categoria_slug and noticia.topico
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
        "page_title": "Sobre Nós",
        "page_eyebrow": "Institucional",
        "page_intro": "Conheça o posicionamento editorial, os princípios de transparência e a proposta do portal público da NC Fly News.",
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_sobre",
            title="Sobre Nós",
            description="Conheça a proposta editorial, os critérios de transparência e a forma como o portal NC Fly News organiza seu conteúdo público.",
        )
    )
    track_page_view(request.path, request=request, section="static")
    return render(request, "portal/sobre_nos.html", context)


def politica_privacidade(request):
    context = {
        "page_title": "Política de Privacidade",
        "page_eyebrow": "Privacidade",
        "page_intro": "Entenda como o portal trata dados pessoais, informações de navegação, analytics e exercício de direitos do titular.",
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_privacidade",
            title="Política de Privacidade",
            description="Política de privacidade do portal NC Fly News, com bases legais, direitos do titular, cookies, analytics e compartilhamento de dados.",
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


def privacidade_plataforma(request):
    context = {
        "page_title": "Privacidade da Plataforma",
        "page_eyebrow": "Área logada",
        "page_intro": (
            "Aviso de privacidade específico para login, painel, administração, auditoria, "
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
                "operacionais, logs de acesso, segurança, auditoria e execução contratual."
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
                "Termos da plataforma autenticada da NC Fly para login, área logada, "
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
        "page_title": "DPA / Aditivo de Tratamento de Dados",
        "page_eyebrow": "Área logada",
        "page_intro": (
            "Documento-base para distribuição de papéis, instruções, suboperadores, "
            "incidentes e obrigações de proteção de dados na plataforma SaaS da NC Fly."
        ),
        "page_updated_at": timezone.localdate(),
    }
    context.update(
        _build_static_page_seo(
            request,
            route_name="portal_dpa_plataforma",
            title="DPA / Aditivo de Tratamento de Dados",
            description=(
                "Documento-base da plataforma NC Fly sobre controlador, operador, "
                "suboperadores, incidentes, segurança e tratamento de dados no contexto SaaS."
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


def robots_txt(request):
    sitemap_url = _absolute_public_url(request, reverse("portal_sitemap"))
    response = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Sitemap: {sitemap_url}",
        ]
    )
    return HttpResponse(response, content_type="text/plain; charset=utf-8")


def llms_txt(request):
    base_url = _public_base_url(request)
    response = "\n".join(
        [
            f"# {settings.PORTAL_SITE_NAME}",
            "",
            "> Portal editorial brasileiro sobre milhas, cartões, promoções, hotéis e viagens.",
            "",
            "## Páginas principais",
            f"- Home: {base_url}{reverse('portal_home')}",
            f"- Sobre nós: {base_url}{reverse('portal_sobre')}",
            f"- Política de Privacidade: {base_url}{reverse('portal_privacidade')}",
            f"- Termos de Uso: {base_url}{reverse('portal_termos')}",
            f"- Plataforma SaaS: {base_url}{reverse('portal_plataforma_saas')}",
            "",
            "## Categorias",
            "- Milhas e Pontos",
            "- Cartões de Crédito",
            "- Hotéis e Resorts",
            "- Promoções",
            "",
            "## Produto",
            "- Plataforma NC Fly: página pública que explica o produto da NC Fly para cotações, emissões, clientes, contas fidelidade e alertas.",
            "",
            "## Observações editoriais",
            "- O portal publica conteúdo editorial e informativo, com contexto próprio.",
            "- Ofertas, preços e disponibilidade exigem conferência final na origem.",
            "- Links externos úteis podem ser destacados quando forem relevantes para o leitor.",
            "",
            "## Contato",
            f"- Empresa: {settings.PORTAL_LEGAL_ENTITY_NAME or settings.PORTAL_SITE_NAME}",
            f"- E-mail: {settings.PORTAL_CONTACT_EMAIL or settings.PORTAL_DPO_EMAIL or 'não informado'}",
        ]
    )
    return HttpResponse(response, content_type="text/plain; charset=utf-8")


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
