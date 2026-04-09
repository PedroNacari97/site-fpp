"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic import RedirectView
from core.views import healthcheck
from accounts.views import custom_login, superadmin_login
from gestao.views.alertas import telegram_alertas_webhook, telegram_noticias_webhook
from portal import views as portal_views
from portal.sitemaps import AlertSitemap, CategorySitemap, HomeSitemap, NewsSitemap, StaticPageSitemap


portal_sitemaps = {
    "home": HomeSitemap,
    "static": StaticPageSitemap,
    "categories": CategorySitemap,
    "news": NewsSitemap,
    "alerts": AlertSitemap,
}

urlpatterns = [
    path("health/", healthcheck, name="healthcheck"),
    path("ads.txt", portal_views.ads_txt, name="portal_ads_txt"),
    path("robots.txt", portal_views.robots_txt, name="portal_robots"),
    path("llms.txt", portal_views.llms_txt, name="portal_llms"),
    path("sitemap.xml", sitemap, {"sitemaps": portal_sitemaps}, name="portal_sitemap"),
    path("plataforma/privacidade/", portal_views.privacidade_plataforma, name="portal_privacidade_plataforma"),
    path("plataforma/termos-de-uso/", portal_views.termos_plataforma, name="portal_termos_plataforma"),
    path("plataforma/dpa/", portal_views.dpa_plataforma, name="portal_dpa_plataforma"),
    path("plataforma/seguranca/", portal_views.seguranca_plataforma, name="portal_seguranca_plataforma"),
    path("plataforma/aceite/", portal_views.aceite_documentos_plataforma, name="portal_aceite_plataforma"),
    path("login/", custom_login, name="login_custom"),
    path("superadmin/login/", superadmin_login, name="superadmin_login"),
    path("integracoes/telegram/alertas/webhook/", telegram_alertas_webhook, name="telegram_alertas_webhook"),
    path("integracoes/telegram/noticias/webhook/", telegram_noticias_webhook, name="telegram_noticias_webhook"),
    path("painel/", include("painel_cliente.urls")),
    path("django/admin/", admin.site.urls),
    path("adm/", include("gestao.urls_admin")),
    path("accounts/", include("accounts.urls")),
    path("home/", include("portal.urls")),
    path("", RedirectView.as_view(pattern_name="portal_home", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
