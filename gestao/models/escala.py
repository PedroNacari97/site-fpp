from django.db import models
from .aeroporto import Aeroporto


class Escala(models.Model):
    TIPO_VOO_CHOICES = (
        ("ida", "Ida"),
        ("volta", "Volta"),
    )

    emissao = models.ForeignKey(
        "gestao.EmissaoPassagem",
        related_name="escalas",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    cotacao = models.ForeignKey(
        "gestao.CotacaoVoo",
        related_name="escalas",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    aeroporto = models.ForeignKey(Aeroporto, on_delete=models.CASCADE)
    duracao = models.DurationField()
    cidade = models.CharField(max_length=100, blank=True)
    tipo = models.CharField(
        max_length=10, choices=TIPO_VOO_CHOICES, default="ida"
    )
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["tipo", "ordem", "id"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.aeroporto} ({self.duracao})"
