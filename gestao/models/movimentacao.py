from django.db import models
from .conta_fidelidade import ContaFidelidade

class Movimentacao(models.Model):
    conta = models.ForeignKey(
        ContaFidelidade, on_delete=models.CASCADE, related_name="movimentacoes"
    )
    data = models.DateField()
    pontos = models.IntegerField()
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.conta} - {self.data} - {self.pontos}"
