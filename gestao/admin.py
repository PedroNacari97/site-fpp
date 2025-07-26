from django.contrib import admin
from .models import (
    Cliente, ProgramaFidelidade,
    ContaFidelidade, EmissaoPassagem, MovimentacaoPontos
)

admin.site.register(Cliente)
admin.site.register(ProgramaFidelidade)

class MovimentacaoPontosInline(admin.TabularInline):
    model = MovimentacaoPontos
    extra = 1
    readonly_fields = ['data']
    fields = ['data', 'pontos', 'valor_pago', 'descricao']
    ordering = ['-data']

class ContaFidelidadeAdmin(admin.ModelAdmin):
    list_display = (
        'cliente',
        'programa',
        'get_saldo_pontos',
        'get_valor_total_pago',
        'get_valor_medio',
        'data_inicio_clube',  
        'clube_periodicidade',
        'pontos_clube_mes',
        'valor_assinatura_clube',
    )
   


    fields = (
        'cliente',
        'programa',
        'clube_periodicidade',
        'pontos_clube_mes',
        'valor_assinatura_clube',
        'data_inicio_clube',
        'validade',
        'get_saldo_pontos',
        'get_valor_total_pago',
        'get_valor_medio',
    )

    readonly_fields = (
        'get_saldo_pontos',
        'get_valor_total_pago',
        'get_valor_medio',
    )

    def get_saldo_pontos(self, obj):
        return obj.saldo_pontos
    get_saldo_pontos.short_description = 'Saldo pontos'

    def get_valor_total_pago(self, obj):
        return f'{obj.valor_total_pago:.2f}'
    get_valor_total_pago.short_description = 'Valor total pago'

    def get_valor_medio(self, obj):
        saldo = obj.saldo_pontos
        if saldo > 0:
            valor_medio = obj.valor_total_pago / (saldo / 1000)
        else:
            valor_medio = 0
        return f'{valor_medio:.2f}'
    get_valor_medio.short_description = 'Valor médio (por 1.000 pontos)'

    inlines = [MovimentacaoPontosInline]

admin.site.register(ContaFidelidade, ContaFidelidadeAdmin)

class EmissaoPassagemAdmin(admin.ModelAdmin):
    list_display = (
        'cliente',
        'programa',
        'aeroporto_ida',
        'aeroporto_volta',
        'data_ida',
        'data_volta',
        'qtd_passageiros',
        'valor_referencia',
        'valor_pago',
        'pontos_utilizados',
        'valor_referencia_pontos',
        'economia_obtida',
    )

admin.site.register(EmissaoPassagem, EmissaoPassagemAdmin)
