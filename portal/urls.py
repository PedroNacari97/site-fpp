from django.urls import path

from . import views


urlpatterns = [
    path("", views.home_publica, name="portal_home"),
    path("metrics/event/", views.registrar_evento_publico, name="portal_metrics_event"),
    path("alertas/", views.alertas_publicos, name="portal_alertas"),
    path("alertas/termos-de-recebimento/", views.termos_alertas_email, name="portal_termos_alertas_email"),
    path("alertas/cancelar/", views.alertas_email_unsubscribe, name="portal_alertas_unsubscribe"),
    path("alertas/<int:alerta_id>/", views.alerta_publico_detalhe, name="portal_alerta_detalhe"),
    path("plataforma/", views.plataforma_saas, name="portal_plataforma_saas"),
    path("plataforma/contato/", views.plataforma_contato, name="portal_plataforma_contato"),
    path("sobre-nos/", views.sobre_empresa_publica, name="portal_sobre"),
    path("fale-conosco/", views.fale_conosco, name="portal_fale_conosco"),
    path("politica-de-privacidade/", views.politica_privacidade, name="portal_privacidade"),
    path("termos-de-uso/", views.termos_de_uso, name="portal_termos"),
    path("categorias/<slug:categoria_slug>/", views.categoria_lista, name="portal_categoria"),
    path("categorias/<slug:categoria_slug>/<slug:slug>/", views.noticia_detalhe, name="portal_noticia_detalhe"),
    path("noticias/<slug:slug>/", views.noticia_redirect, name="portal_noticia_redirect"),
]
