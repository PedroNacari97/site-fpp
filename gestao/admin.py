from django.contrib import admin
from .models import (
    Cliente, ProgramaFidelidade,
    ContaFidelidade, EmissaoPassagem,
    EmissaoHotel, ValorMilheiro,
    Empresa, Administrador, Operador, ClienteEmpresa,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = (
        'nome', 'limite_admins', 'limite_operadores', 'limite_clientes', 'ativo'
    )
    list_filter = ('ativo',)
    search_fields = ('nome',)


@admin.register(Administrador)
class AdministradorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'empresa', 'acesso_ate', 'ativo')
    list_filter = ('ativo', 'empresa')
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name'
    )


@admin.register(Operador)
class OperadorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'empresa', 'admin', 'ativo')
    list_filter = ('ativo', 'empresa')
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name'
    )


@admin.register(ClienteEmpresa)
class ClienteEmpresaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'empresa', 'admin', 'operador', 'ativo')
    list_filter = ('ativo', 'empresa')
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name'
    )

admin.site.register(Cliente)
admin.site.register(ProgramaFidelidade)

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

   
admin.site.register(ContaFidelidade, ContaFidelidadeAdmin)

class EmissaoPassagemAdmin(admin.ModelAdmin):
    list_display = (
        'cliente',
        'programa',
        'aeroporto_partida',
        'aeroporto_destino',
        'data_ida',
        'data_volta',
        'qtd_passageiros',
        'valor_referencia',
        'valor_pago',
        'pontos_utilizados',
        'valor_referencia_pontos',
        'economia_obtida',
        'companhia_aerea',
        'localizador',
    )

admin.site.register(EmissaoPassagem, EmissaoPassagemAdmin)


class EmissaoHotelAdmin(admin.ModelAdmin):
    list_display = (
        'cliente',
        'nome_hotel',
        'check_in',
        'check_out',
        'valor_referencia',
        'valor_pago',
        'economia_obtida',
    )

admin.site.register(EmissaoHotel, EmissaoHotelAdmin)

@admin.register(ValorMilheiro)
class ValorMilheiroAdmin(admin.ModelAdmin):
    list_display = ('programa_nome', 'valor_mercado', 'atualizado_em')
    search_fields = ('programa_nome',)
