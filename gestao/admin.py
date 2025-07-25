from django.contrib import admin
from .models import Cliente, ProgramaFidelidade, ContaFidelidade, ParametroConversao, EmissaoPassagem

admin.site.register(Cliente)
admin.site.register(ProgramaFidelidade)
admin.site.register(ContaFidelidade)
admin.site.register(ParametroConversao)
admin.site.register(EmissaoPassagem)

