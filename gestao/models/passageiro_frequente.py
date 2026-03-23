from django.db import models

from gestao.utils import normalize_cpf

from .cliente import Cliente


class PassageiroFrequente(models.Model):
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name="passageiros_frequentes"
    )
    nome = models.CharField(max_length=150)
    cpf = models.CharField(max_length=14)
    rg = models.CharField(max_length=50, blank=True)
    passaporte = models.CharField(max_length=30, blank=True)
    passaporte_validade = models.DateField(null=True, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    relacao = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Passageiro Frequente"
        verbose_name_plural = "Passageiros Frequentes"
        ordering = ["nome"]

    def save(self, *args, **kwargs):
        self.cpf = normalize_cpf(self.cpf)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} ({self.cliente})"
