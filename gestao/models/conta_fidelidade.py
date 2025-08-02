from django.db import models
from .cliente import Cliente
from .programa_fidelidade import ProgramaFidelidade

class ContaFidelidade(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    programa = models.ForeignKey(ProgramaFidelidade, on_delete=models.CASCADE)

    @property
    def valor_medio_por_mil(self):
        saldo = self.saldo_pontos
        if saldo > 0:
            return float(self.valor_total_pago) / (saldo / 1000)
        return 0

    PERIODICIDADE_CLUBE = (
        ("nenhum", "Nenhum"),
        ("mensal", "Mensal"),
        ("trimestral", "Trimestral"),
        ("semestral", "Semestral"),
        ("anual", "Anual"),
    )
    clube_periodicidade = models.CharField(
        max_length=12, choices=PERIODICIDADE_CLUBE, default="nenhum"
    )
    pontos_clube_mes = models.IntegerField(default=0)
    valor_assinatura_clube = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    data_inicio_clube = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)

    @property
    def saldo_pontos(self):
        movs = self.movimentacoes.all()
        return sum(m.pontos for m in movs) if movs.exists() else 0

    @property
    def valor_total_pago(self):
        movs = self.movimentacoes.all()
        return sum(float(m.valor_pago) for m in movs) if movs.exists() else 0

    def __str__(self):
        return f"{self.cliente} - {self.programa}"
