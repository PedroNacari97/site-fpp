from django.db import models
from django.contrib.auth.models import User
from .empresa import Empresa

class Cliente(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="cliente_gestao"
    )
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    TIPO_DOCUMENTO = (
        ("cpf", "CPF"),
        ("cnpj", "CNPJ"),
    )
    tipo_documento = models.CharField(
        max_length=4, choices=TIPO_DOCUMENTO, default="cpf"
    )
    documento = models.CharField(max_length=18, default="")
    data_expiracao = models.DateField(null=True, blank=True)
    PERFIS = (
        ("admin", "Administrador"),
        ("operador", "Operador"),
        ("cliente", "Cliente"),
    )
    perfil = models.CharField(max_length=10, choices=PERFIS, default="cliente")
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="usuarios_criados",
        null=True, blank=True
    )
    empresa = models.ForeignKey(
        Empresa, on_delete=models.SET_NULL, null=True, blank=True, related_name="clientes"
    )
    administrador_responsavel = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"perfil": "admin"},
        related_name="subordinados",
    )
    operador_responsavel = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"perfil": "operador"},
        related_name="clientes_associados",
    )

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username
