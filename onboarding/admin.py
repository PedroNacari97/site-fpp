from django.contrib import admin
from .models import Plano, Assinatura, Pagamento


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "preco_mensal", "limite_operadores", "trial_dias", "ativo", "destaque")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(Assinatura)
class AssinaturaAdmin(admin.ModelAdmin):
    list_display = ("empresa", "plano", "status", "data_inicio", "trial_fim")
    list_filter = ("status", "plano")


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ("assinatura", "valor", "status", "metodo", "criado_em")
    list_filter = ("status", "metodo")
