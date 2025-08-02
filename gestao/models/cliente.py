from django.db import models
from django.contrib.auth.models import User

class Cliente(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="cliente_gestao"
    )
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, default="000.000.000-00")
    PERFIS = (
        ("admin", "Administrador"),
        ("operador", "Operador"),
        ("cliente", "Cliente"),
    )
    perfil = models.CharField(max_length=10, choices=PERFIS, default="cliente")
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username
