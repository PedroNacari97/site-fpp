from django.contrib import admin

from .models import Fonte, JobExecucao, MateriaBruta, NoticiaPublicada


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
