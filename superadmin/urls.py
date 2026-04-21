"""
URLs do painel superadmin NCfly.

Path base: /ncadm/   (registrado em core/urls.py)
"""
from django.urls import path

from . import views
from . import views_financeiro
from . import views_comentarios
from . import views_ncadm

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
    path("artigos/gerar-ia/", views.ArtigoGerarCompletoIAView.as_view(), name="superadmin_artigo_gerar_ia"),
    path("artigos/revisar-ia-preview/", views.ArtigoRevisarIAPreviewView.as_view(), name="superadmin_artigo_revisar_ia_preview"),
    path("artigos/buscar-videos-preview/", views.ArtigoBuscarVideosPreviewView.as_view(), name="superadmin_artigo_buscar_videos_preview"),
    path("artigos/<int:pk>/editar/", views.ArtigoEditView.as_view(), name="superadmin_artigo_edit"),
    path("artigos/<int:pk>/excluir/", views.ArtigoDeleteView.as_view(), name="superadmin_artigo_delete"),
    path("artigos/<int:pk>/review-ia/", views.ArtigoReviewIAView.as_view(), name="superadmin_artigo_review_ia"),
    path("artigos/<int:pk>/buscar-videos/", views.ArtigoBuscarVideosView.as_view(), name="superadmin_artigo_buscar_videos"),
    path("artigos/<int:pk>/adicionar-video-url/", views.ArtigoAdicionarVideoUrlView.as_view(), name="superadmin_artigo_adicionar_video_url"),

    # Modulos de Estudo
    path("artigos/modulos/", views.ModulosListView.as_view(), name="superadmin_modulos_list"),
    path("artigos/modulos/novo/", views.ModuloCreateView.as_view(), name="superadmin_modulo_create"),
    path("artigos/modulos/<int:pk>/editar/", views.ModuloEditView.as_view(), name="superadmin_modulo_edit"),
    path("artigos/modulos/<int:pk>/excluir/", views.ModuloDeleteView.as_view(), name="superadmin_modulo_delete"),

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

    # Custos operacionais (Railway, OpenAI, dominio)
    path("custos/", views_ncadm.CustosListView.as_view(), name="superadmin_custos_list"),
    path("custos/novo/", views_ncadm.CustoCreateView.as_view(), name="superadmin_custo_create"),
    path("custos/<int:pk>/editar/", views_ncadm.CustoEditView.as_view(), name="superadmin_custo_edit"),
    path("custos/<int:pk>/excluir/", views_ncadm.CustoDeleteView.as_view(), name="superadmin_custo_delete"),
    path("custos/fechamento-csv/", views_ncadm.FechamentoMensalCSVView.as_view(), name="superadmin_fechamento_csv"),

    # Perfil fiscal (CNPJ, regime, CNAEs, contador, conversao)
    path("fiscal/perfil/", views_ncadm.PerfilFiscalView.as_view(), name="superadmin_perfil_fiscal"),

    # Receitas e calculo do DAS
    path("fiscal/receitas/", views_ncadm.ReceitasListView.as_view(), name="superadmin_receitas_list"),
    path("fiscal/receitas/novo/", views_ncadm.ReceitaCreateView.as_view(), name="superadmin_receita_create"),
    path("fiscal/receitas/<int:pk>/editar/", views_ncadm.ReceitaEditView.as_view(), name="superadmin_receita_edit"),
    path("fiscal/receitas/<int:pk>/excluir/", views_ncadm.ReceitaDeleteView.as_view(), name="superadmin_receita_delete"),

    # Obrigacoes fiscais
    path("fiscal/", views_ncadm.ObrigacoesListView.as_view(), name="superadmin_obrigacoes_list"),
    path("fiscal/nova/", views_ncadm.ObrigacaoCreateView.as_view(), name="superadmin_obrigacao_create"),
    path("fiscal/<int:pk>/editar/", views_ncadm.ObrigacaoEditView.as_view(), name="superadmin_obrigacao_edit"),
    path("fiscal/<int:pk>/pagar/", views_ncadm.ObrigacaoMarcarPagaView.as_view(), name="superadmin_obrigacao_pagar"),
    path("fiscal/<int:pk>/excluir/", views_ncadm.ObrigacaoDeleteView.as_view(), name="superadmin_obrigacao_delete"),

    # Comentarios (moderacao B2C)
    path(
        "comentarios/",
        views_comentarios.ComentariosListView.as_view(),
        name="superadmin_comentarios_list",
    ),
    path(
        "comentarios/<int:pk>/ocultar/",
        views_comentarios.ComentarioOcultarView.as_view(),
        name="superadmin_comentario_ocultar",
    ),
    path(
        "comentarios/<int:pk>/restaurar/",
        views_comentarios.ComentarioRestaurarView.as_view(),
        name="superadmin_comentario_restaurar",
    ),
    path(
        "comentarios/<int:pk>/responder/",
        views_comentarios.ComentarioResponderView.as_view(),
        name="superadmin_comentario_responder",
    ),
]
