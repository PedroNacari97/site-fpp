from django.urls import path

from . import views, views_auth, views_comentarios


urlpatterns = [
    path("", views.home_publica, name="portal_home"),
    # --- Portal B2C — autenticacao isolada (NAO usa auth.User do SaaS) ---
    path("login/", views_auth.portal_login, name="portal_login"),
    path("cadastro/", views_auth.portal_register, name="portal_register"),
    path("logout/", views_auth.portal_logout, name="portal_logout"),
    path("auth/google/", views_auth.portal_google_login, name="portal_google_login"),
    path(
        "auth/google/callback/",
        views_auth.portal_google_callback,
        name="portal_google_callback",
    ),
    path(
        "optout/alerta/<str:token>/",
        views_auth.portal_optout_alerta,
        name="portal_optout_alerta",
    ),
    path(
        "optout/artigo/<str:token>/",
        views_auth.portal_optout_artigo,
        name="portal_optout_artigo",
    ),
    path("metrics/event/", views.registrar_evento_publico, name="portal_metrics_event"),
    path("alertas/", views.alertas_publicos, name="portal_alertas"),
    path("alertas/termos-de-recebimento/", views.termos_alertas_email, name="portal_termos_alertas_email"),
    path("alertas/cancelar/", views.alertas_email_unsubscribe, name="portal_alertas_unsubscribe"),
    path("alertas/<int:alerta_id>/compartilhar/", views.alerta_publico_compartilhar, name="portal_alerta_compartilhar"),
    path("alertas/<int:alerta_id>/", views.alerta_publico_detalhe, name="portal_alerta_detalhe"),
    path("plataforma/", views.plataforma_saas, name="portal_plataforma_saas"),
    path("plataforma/contato/", views.plataforma_contato, name="portal_plataforma_contato"),
    path("sobre-nos/", views.sobre_empresa_publica, name="portal_sobre"),
    path("fale-conosco/", views.fale_conosco, name="portal_fale_conosco"),
    path("politica-de-privacidade/", views.politica_privacidade, name="portal_privacidade"),
    path("termos-de-uso/", views.termos_de_uso, name="portal_termos"),
    path("categorias/<slug:categoria_slug>/", views.categoria_lista, name="portal_categoria"),
    path("categorias/<slug:categoria_slug>/<slug:slug>/", views.noticia_detalhe, name="portal_noticia_detalhe"),
    path("artigos/", views.artigos_lista, name="portal_artigos"),
    path(
        "artigos/<slug:slug>/marcar-lido/",
        views.artigo_marcar_lido,
        name="portal_artigo_marcar_lido",
    ),
    path("artigos/<slug:slug>/", views.modulo_detalhe, name="portal_modulo_detalhe"),
    path("artigos/<slug:modulo_slug>/<slug:slug>/", views.artigo_detalhe, name="portal_artigo_detalhe"),
    path(
        "artigos/<slug:modulo_slug>/<slug:slug>/comentarios/",
        views_comentarios.criar,
        name="portal_comentario_criar",
    ),
    path(
        "artigos/<slug:modulo_slug>/<slug:slug>/comentarios/lista/",
        views_comentarios.listar,
        name="portal_comentario_listar",
    ),
    path(
        "comentarios/<int:comentario_id>/editar/",
        views_comentarios.editar,
        name="portal_comentario_editar",
    ),
    path(
        "comentarios/<int:comentario_id>/excluir/",
        views_comentarios.excluir,
        name="portal_comentario_excluir",
    ),
    path("noticias/", views.noticias_todas, name="portal_noticias_todas"),
    path("noticias/<slug:slug>/", views.noticia_redirect, name="portal_noticia_redirect"),
]
