from django.db import models
from django.utils import timezone

from .empresa import Empresa
from .programa_fidelidade import ProgramaFidelidade


class EmissorParceiro(models.Model):
    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="emissores_parceiros"
    )
    nome = models.CharField(max_length=150)
    programas = models.ManyToManyField(
        ProgramaFidelidade, related_name="emissores_parceiros", blank=True
    )
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Emissor Parceiro"
        verbose_name_plural = "Emissores Parceiros"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
