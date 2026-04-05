from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from gestao.models import AlertaViagem
from .models import NoticiaPublicada


CATEGORY_SLUGS = (
    "milhas-e-pontos",
    "cartoes-credito",
    "hoteis-resorts",
)

STATIC_ROUTE_NAMES = (
    "portal_alertas",
    "portal_sobre",
    "portal_privacidade",
    "portal_termos",
    "portal_plataforma_saas",
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
        return [alerta for alerta in AlertaViagem.objects.filter(ativo=True).order_by("-criado_em") if alerta.deve_aparecer_na_vitrine()]

    def location(self, item):
        return reverse("portal_alerta_detalhe", args=[item.id])

    def lastmod(self, item):
        return item.criado_em
