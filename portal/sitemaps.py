from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.urls import reverse

from gestao.models import AlertaViagem
from .models import NoticiaPublicada
from .services.public_alerts import PUBLIC_HOME_ALERT_MAX_AGE_DAYS


HUB_LASTMOD_CACHE_TTL = 600  # 10 min


CATEGORY_SLUGS = (
    "milhas-e-pontos",
    "cartoes-credito",
    "hoteis-resorts",
    "promocoes",
    "viagens",
)

STATIC_ROUTE_NAMES = (
    "portal_alertas",
    "portal_termos_alertas_email",
    "portal_sobre",
    "portal_fale_conosco",
    "portal_privacidade",
    "portal_termos",
    "portal_plataforma_saas",
)

HUB_ROUTE_NAMES = (
    "portal_artigos",
    "portal_noticias_todas",
)


class HomeSitemap(Sitemap):
    changefreq = "hourly"
    priority = 1.0

    def items(self):
        return ["portal_home"]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        latest_article = (
            NoticiaPublicada.objects.filter(status="published").order_by("-atualizada_em").first()
        )
        return latest_article.atualizada_em if latest_article else None


class CategorySitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return CATEGORY_SLUGS

    def location(self, item):
        return reverse("portal_categoria", kwargs={"categoria_slug": item})

    def lastmod(self, item):
        latest_article = (
            NoticiaPublicada.objects.filter(status="published").order_by("-atualizada_em").first()
        )
        return latest_article.atualizada_em if latest_article else None


class StaticPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return STATIC_ROUTE_NAMES

    def location(self, item):
        return reverse(item)


class HubSitemap(Sitemap):
    """Hubs de conteudo que captam lead (newsletter, opt-in artigos)."""
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return HUB_ROUTE_NAMES

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        cache_key = f"portal:sitemap:hub_lastmod:{item}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached or None
        from .models import ArtigoEstudo
        if item == "portal_artigos":
            latest = (
                ArtigoEstudo.objects.filter(status="published")
                .only("atualizado_em")
                .order_by("-atualizado_em")
                .first()
            )
            value = latest.atualizado_em if latest else None
        else:
            latest_news = (
                NoticiaPublicada.objects.filter(status="published")
                .only("atualizada_em")
                .order_by("-atualizada_em")
                .first()
            )
            value = latest_news.atualizada_em if latest_news else None
        cache.set(cache_key, value or "", HUB_LASTMOD_CACHE_TTL)
        return value


class NewsSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return NoticiaPublicada.objects.filter(status="published").order_by("-publicada_em")

    def lastmod(self, item):
        return item.atualizada_em


class AlertSitemap(Sitemap):
    changefreq = "hourly"
    priority = 0.8

    def items(self):
        return [
            alerta
            for alerta in AlertaViagem.objects.filter(ativo=True).order_by("-criado_em")
            if alerta.deve_aparecer_na_vitrine(max_age_days=PUBLIC_HOME_ALERT_MAX_AGE_DAYS)
        ]

    def location(self, item):
        return reverse("portal_alerta_detalhe", args=[item.id])

    def lastmod(self, item):
        return item.criado_em


class ArtigoEstudoSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        from .models import ArtigoEstudo
        return (
            ArtigoEstudo.objects.filter(status="published")
            .select_related("modulo")
            .only("slug", "atualizado_em", "publicado_em", "modulo__slug")
            .order_by("-publicado_em")
        )

    def lastmod(self, item):
        return item.atualizado_em


class ModuloEstudoSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        from .models import ModuloEstudo
        return (
            ModuloEstudo.objects.filter(ativo=True)
            .only("slug", "atualizado_em", "ordem")
            .order_by("ordem")
        )

    def lastmod(self, item):
        return item.atualizado_em
