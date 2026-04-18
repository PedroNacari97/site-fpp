"""
URLs do painel superadmin NCfly.

Path base: /ncadm/   (registrado em core/urls.py)
"""
from django.urls import path

from . import views
from . import views_financeiro

urlpatterns = [
    # Dashboard
    path("", views.DashboardView.as_view(), name="superadmin_dashboard"),

    # Noticias
    path("noticias/", views.NoticiasListView.as_view(), name="superadmin_noticias_list"),
    path("noticias/<int:pk>/excluir/", views.NoticiaDeleteView.as_view(), name="superadmin_noticia_delete"),
    path("noticias/upload/", views.ArtigoUploadView.as_view(), name="superadmin_artigo_upload"),

    # Artigos Educativos
    path("artigos/", views.ArtigosListView.as_view(), name="superadmin_artigos_list"),
    path("artigos/novo/", views.ArtigoCreateView.as_view(), name="superadmin_artigo_create"),
    path("artigos/<int:pk>/editar/", views.ArtigoEditView.as_view(), name="superadmin_artigo_edit"),
    path("artigos/<int:pk>/excluir/", views.ArtigoDeleteView.as_view(), name="superadmin_artigo_delete"),
    path("artigos/<int:pk>/review-ia/", views.ArtigoReviewIAView.as_view(), name="superadmin_artigo_review_ia"),
    path("artigos/<int:pk>/buscar-videos/", views.ArtigoBuscarVideosView.as_view(), name="superadmin_artigo_buscar_videos"),

    # Modulos de Estudo
    path("artigos/modulos/", views.ModulosListView.as_view(), name="superadmin_modulos_list"),
    path("artigos/modulos/novo/", views.ModuloCreateView.as_view(), name="superadmin_modulo_create"),
    path("artigos/modulos/<int:pk>/editar/", views.ModuloEditView.as_view(), name="superadmin_modulo_edit"),

    # Empresas
    path("empresas/", views.EmpresasListView.as_view(), name="superadmin_empresas_list"),
    path("empresas/nova/", views.EmpresaCreateView.as_view(), name="superadmin_empresa_create"),
    path("empresas/<int:pk>/", views.EmpresaDetailView.as_view(), name="superadmin_empresa_detail"),
    path("empresas/<int:pk>/editar/", views.EmpresaEditView.as_view(), name="superadmin_empresa_edit"),

    # Financeiro (SaaS B2B — assinaturas, pagamentos, MRR, churn)
    path(
        "financeiro/",
        views_financeiro.FinanceiroDashboardView.as_view(),
        name="superadmin_financeiro_dashboard",
    ),
    path(
        "financeiro/assinaturas/",
        views_financeiro.AssinaturasListView.as_view(),
        name="superadmin_assinaturas_list",
    ),
    path(
        "financeiro/assinaturas/<int:pk>/",
        views_financeiro.AssinaturaDetailView.as_view(),
        name="superadmin_assinatura_detail",
    ),
    path(
        "financeiro/assinaturas/<int:pk>/status/",
        views_financeiro.AssinaturaStatusChangeView.as_view(),
        name="superadmin_assinatura_status_change",
    ),
    path(
        "financeiro/pagamentos/",
        views_financeiro.PagamentosListView.as_view(),
        name="superadmin_pagamentos_list",
    ),
]
