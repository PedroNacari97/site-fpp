from django.db import models
from .cliente import Cliente
from .programa_fidelidade import ProgramaFidelidade
from .aeroporto import Aeroporto
from .companhia_aerea import CompanhiaAerea


class EmissaoPassagem(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    programa = models.ForeignKey(
        ProgramaFidelidade, on_delete=models.CASCADE, null=True, blank=True
    )

    companhia_aerea = models.ForeignKey(
        CompanhiaAerea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emissoes'
    )
    aeroporto_partida = models.ForeignKey(
        Aeroporto,
        on_delete=models.CASCADE,
        related_name="partidas",
        null=True,
        blank=True,
    )
    aeroporto_destino = models.ForeignKey(
        Aeroporto,
        on_delete=models.CASCADE,
        related_name="destinos",
        null=True,
        blank=True,
    )
    data_ida = models.DateTimeField()
    data_volta = models.DateTimeField(null=True, blank=True)
    qtd_passageiros = models.PositiveIntegerField(default=0)
    qtd_adultos = models.PositiveIntegerField(default=0)
    qtd_criancas = models.PositiveIntegerField(default=0)
    qtd_bebes = models.PositiveIntegerField(default=0)
    companhia_aerea = models.CharField(max_length=100, blank=True)
    localizador = models.CharField(max_length=100, blank=True)
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    pontos_utilizados = models.IntegerField(null=True, blank=True)
    valor_referencia_pontos = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    economia_obtida = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    detalhes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.qtd_passageiros = self.qtd_adultos + self.qtd_criancas + self.qtd_bebes
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente} - {self.programa} - {self.data_ida}"
