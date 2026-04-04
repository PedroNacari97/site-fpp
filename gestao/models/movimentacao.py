from django.db import models
from .conta_fidelidade import ContaFidelidade

class Movimentacao(models.Model):
    TIPO_MANUAL = "manual"
    TIPO_EMISSAO = "emissao"
    TIPO_TRANSFERENCIA = "transferencia"
    TIPO_CLUBE = "clube"

    TIPO_CHOICES = (
        (TIPO_MANUAL, "Manual"),
        (TIPO_EMISSAO, "Emissão"),
        (TIPO_TRANSFERENCIA, "Transferência"),
        (TIPO_CLUBE, "Clube"),
    )

    conta = models.ForeignKey(
        ContaFidelidade, on_delete=models.CASCADE, related_name="movimentacoes"
    )
    data = models.DateField()
    pontos = models.IntegerField()
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_MANUAL)
    chave_origem = models.CharField(max_length=120, blank=True, default="")

    def __str__(self):
        return f"{self.conta} - {self.data} - {self.pontos}"
