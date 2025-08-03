from django.contrib import admin
from .models import Cliente, Empresa, Administrador, Operador, ClienteEmpresa


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

    def save_model(self, request, obj, form, change):
        obj.usuario.is_staff = True
        obj.usuario.save()
        super().save_model(request, obj, form, change)
        Cliente.objects.get_or_create(
            usuario=obj.usuario,
            defaults={'perfil': 'admin'}
        )


@admin.register(Operador)
class OperadorAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'empresa', 'admin', 'ativo')
    list_filter = ('ativo', 'empresa')
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name'
    )

    def save_model(self, request, obj, form, change):
        obj.usuario.is_staff = True
        obj.usuario.save()
        super().save_model(request, obj, form, change)
        Cliente.objects.get_or_create(
            usuario=obj.usuario,
            defaults={'perfil': 'operador'}
        )


@admin.register(ClienteEmpresa)
class ClienteEmpresaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'empresa', 'admin', 'operador', 'ativo')
    list_filter = ('ativo', 'empresa')
    search_fields = (
        'usuario__username', 'usuario__first_name', 'usuario__last_name'
    )

    def save_model(self, request, obj, form, change):
        obj.usuario.is_staff = False
        obj.usuario.save()
        super().save_model(request, obj, form, change)
        Cliente.objects.get_or_create(
            usuario=obj.usuario,
            defaults={'perfil': 'cliente'}
        )
