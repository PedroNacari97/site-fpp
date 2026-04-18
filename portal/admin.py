from django.contrib import admin

from .models import (
    Fonte,
    JobExecucao,
    LeadAlertaEmail,
    MateriaBruta,
    NoticiaPublicada,
    OptInAlertaPassagem,
    OptInArtigoNovo,
    PortalUser,
    ProgressoArtigo,
)


@admin.register(Fonte)
class FonteAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo_coleta", "ativa", "confianca_minima", "atualizada_em")
    list_filter = ("tipo_coleta", "ativa")
    search_fields = ("nome", "url")


@admin.register(MateriaBruta)
class MateriaBrutaAdmin(admin.ModelAdmin):
    list_display = ("titulo_extraido", "fonte", "url_original", "data_publicacao_original", "data_coleta")
    list_filter = ("fonte",)
    search_fields = ("titulo_extraido", "url_original", "texto_base")
    readonly_fields = ("hash_conteudo", "data_coleta", "processada_em")


@admin.register(NoticiaPublicada)
class NoticiaPublicadaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "categoria", "topico", "fonte", "status", "confianca", "publicada_em")
    list_filter = ("status", "categoria", "topico", "fonte", "imagem_ilustrativa")
    search_fields = ("titulo", "resumo", "slug", "url_fonte", "topico")
    prepopulated_fields = {"slug": ("titulo",)}


@admin.register(JobExecucao)
class JobExecucaoAdmin(admin.ModelAdmin):
    list_display = ("job_name", "status", "horario", "finalizado_em", "quantidade_processada", "quantidade_publicada")
    list_filter = ("status", "job_name")
    readonly_fields = ("horario", "finalizado_em")


@admin.register(LeadAlertaEmail)
class LeadAlertaEmailAdmin(admin.ModelAdmin):
    list_display = (
        "nome_completo",
        "email",
        "telefone",
        "origem_cadastro",
        "status",
        "motivo_cancelamento",
        "cancelado_em",
        "aceite_versao",
        "criado_em",
    )
    list_filter = ("origem_cadastro", "status", "motivo_cancelamento", "source_environment")
    search_fields = ("nome_completo", "email", "telefone", "source_host")
    readonly_fields = (
        "aceito_em",
        "aceito_ip",
        "aceito_user_agent",
        "cancelado_em",
        "criado_em",
        "atualizado_em",
    )


@admin.register(PortalUser)
class PortalUserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "nome",
        "email_verificado",
        "ativo",
        "criado_em",
        "ultimo_login_em",
    )
    list_filter = ("ativo", "email_verificado")
    search_fields = ("email", "nome", "google_sub")
    readonly_fields = (
        "google_sub",
        "senha_hash",
        "ip_cadastro",
        "user_agent_cadastro",
        "source_environment",
        "source_host",
        "criado_em",
        "atualizado_em",
        "ultimo_login_em",
        "ultimo_login_ip",
    )


class _OptInAdminBase(admin.ModelAdmin):
    list_display = ("user", "email", "ativo", "aceito_em", "cancelado_em", "aceite_versao")
    list_filter = ("ativo", "aceite_versao", "motivo_cancelamento")
    search_fields = ("user__email", "user__nome", "email", "token_unsubscribe")
    readonly_fields = (
        "user",
        "email",
        "aceito_em",
        "aceito_ip",
        "aceito_user_agent",
        "aceite_versao",
        "aceite_hash_documento",
        "token_unsubscribe",
        "cancelado_em",
        "cancelado_ip",
        "motivo_cancelamento",
        "criado_em",
        "atualizado_em",
    )


@admin.register(OptInAlertaPassagem)
class OptInAlertaPassagemAdmin(_OptInAdminBase):
    pass


@admin.register(OptInArtigoNovo)
class OptInArtigoNovoAdmin(_OptInAdminBase):
    pass


@admin.register(ProgressoArtigo)
class ProgressoArtigoAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "artigo",
        "progresso_percentual",
        "lido_em",
        "ultima_visita_em",
    )
    list_filter = ("lido_em",)
    search_fields = (
        "user__email",
        "user__nome",
        "artigo__titulo",
        "artigo__slug",
    )
    readonly_fields = (
        "user",
        "artigo",
        "primeira_visita_em",
        "ultima_visita_em",
    )
    list_select_related = ("user", "artigo", "artigo__modulo")
