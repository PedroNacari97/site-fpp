from django.db import models
from .emissao_passagem import EmissaoPassagem
from .aeroporto import Aeroporto


class Escala(models.Model):
    emissao = models.ForeignKey(
        EmissaoPassagem, related_name="escalas", on_delete=models.CASCADE
    )
    aeroporto = models.ForeignKey(Aeroporto, on_delete=models.CASCADE)
    duracao = models.DurationField()
    cidade = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.aeroporto} ({self.duracao})"
