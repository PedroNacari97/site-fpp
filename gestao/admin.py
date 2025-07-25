from django.contrib import admin
from .models import Cliente, ProgramaFidelidade, ContaFidelidade, ParametroConversao, EmissaoPassagem

admin.site.register(Cliente)
admin.site.register(ProgramaFidelidade)
admin.site.register(ContaFidelidade)
admin.site.register(ParametroConversao)
admin.site.register( EmissaoPassagem )
class EmissaoPassagemAdmin (admin.ModelAdmin):
 
    lista_exibição = (
        'cliente',
        'aeroporto_ida' ,
        'aeroporto_volta',
        'data_ida' ,
        'data_volta' ,
        'qtd_passageiros',
        'valor_de_referência' ,
        'valor_pago',
        'pontos_utilizados',
        'valor_referencia_pontos',
    )

