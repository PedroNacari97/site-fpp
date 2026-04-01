import unicodedata

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone

from .models import NoticiaPublicada


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
        "hero_description": "Fique por dentro das melhores promoções de milhas, hotéis, cartões de crédito e muito mais. Não perca nenhuma oportunidade!",
        "hero_class": "portal-category-hero--promo",
        "icon_variant": "promo",
        "card_class": "news-category-card--green",
        "aliases": ("promocoes", "promocao", "oferta", "desconto", "bonus", "sale"),
        "load_more_label": "Carregar mais promoções",
        "cta_title": "Não perca nenhuma promoção!",
        "cta_description": "Cadastre-se e receba alertas instantâneos das melhores ofertas.",
        "cta_button": "Criar conta grátis",
    },
}


def _estimate_read_minutes(text):
    word_count = len((text or "").split())
    return max(1, round(word_count / 180))


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return normalized.encode("ascii", "ignore").decode("ascii").lower().strip()


def _get_published_news():
    return list(
        NoticiaPublicada.objects.filter(status="published")
        .select_related("fonte")
        .order_by("-publicada_em")
    )


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
    grouped: dict[str, list[NoticiaPublicada]] = {}
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
    noticias = _get_published_news()[:18]
    destaque = noticias[0] if noticias else None
    grade = noticias[4:10] if len(noticias) > 4 else noticias[1:7]
    return render(
        request,
        "portal/home.html",
        {
            "destaque": destaque,
            "noticias_grade": grade,
            "explore_categories": _build_explore_categories(),
            "publicadas_ate": timezone.localtime(),
            "noticias_publicadas_total": len(noticias),
        },
    )


def categoria_lista(request, categoria_slug):
    selected_topic_slug = slugify((request.GET.get("topico") or "").strip())
    return render(
        request,
        "portal/categoria.html",
        _build_category_page_context(categoria_slug, selected_topic_slug),
    )


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
    return render(
        request,
        "portal/detalhe.html",
        {
            "noticia": noticia,
            "relacionadas": relacionadas,
            "tempo_leitura_minutos": _estimate_read_minutes(noticia.conteudo),
            "breadcrumbs_categoria": noticia.categoria or "Milhas e Pontos",
            "categoria_url": reverse("portal_categoria", kwargs={"categoria_slug": categoria_slug}) if categoria_slug else None,
            "topico_url": f"{reverse('portal_categoria', kwargs={'categoria_slug': categoria_slug})}?topico={slugify(noticia.topico)}" if categoria_slug and noticia.topico else None,
            "comentarios_total": noticia.metadata_json.get("comments_count", 45),
            "visualizacoes_total": noticia.metadata_json.get("views_count", 234),
            "offer_cta": (noticia.metadata_json or {}).get("offer_cta", {}),
        },
    )
