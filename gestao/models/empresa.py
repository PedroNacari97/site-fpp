from django.db import models
from django.utils import timezone


class Empresa(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    limite_colaboradores = models.PositiveIntegerField(default=0)
    admin = models.OneToOneField(
        "gestao.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="empresa_administrada",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome