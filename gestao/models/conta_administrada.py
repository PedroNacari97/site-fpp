from django.db import models
from django.utils import timezone

from .empresa import Empresa


class ContaAdministrada(models.Model):
    """Conta de fidelidade controlada pela empresa para emissões de terceiros."""

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="contas_administradas"
    )
    nome = models.CharField(max_length=150)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Conta Administrada"
        verbose_name_plural = "Contas Administradas"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.empresa})"
