from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from .cliente import Cliente
from .conta_administrada import ContaAdministrada
from .aeroporto import Aeroporto
from .programa_fidelidade import ProgramaFidelidade

class CotacaoVoo(models.Model):
    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("aceita", "Aceita"),
        ("rejeitada", "Rejeitada"),
        ("emissao", "Emissão"),
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True)
    conta_administrada = models.ForeignKey(
        ContaAdministrada,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cotacoes",
    )
    companhia_aerea = models.CharField(max_length=100, blank=True)
    origem = models.ForeignKey(
        Aeroporto,
        related_name="cotacoes_origem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    destino = models.ForeignKey(
        Aeroporto,
        related_name="cotacoes_destino",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    data_ida = models.DateTimeField()
    data_volta = models.DateTimeField(null=True, blank=True)
    programa = models.ForeignKey(
        ProgramaFidelidade, on_delete=models.SET_NULL, null=True, blank=True
    )
    qtd_passageiros = models.PositiveIntegerField(default=1)
    classe = models.CharField(max_length=50, blank=True)
    observacoes = models.TextField(blank=True)
    valor_passagem = models.DecimalField(max_digits=10, decimal_places=2)
    taxas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    milhas = models.IntegerField(default=0)
    valor_milheiro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    parcelas = models.IntegerField(default=1)
    juros = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    desconto = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    valor_parcelado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_vista = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    validade = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    economia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    emissao = models.OneToOneField(
        "EmissaoPassagem", on_delete=models.SET_NULL, null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if bool(self.cliente) == bool(self.conta_administrada):
            raise ValidationError("Informe um cliente ou uma conta administrada, mas não ambos.")

    def calcular_valores(self):
        base = (Decimal(self.milhas) / Decimal('1000')) * Decimal(self.valor_milheiro) + Decimal(self.taxas)
        parcelado = base * Decimal(self.juros)
        avista = parcelado * Decimal(self.desconto)
        self.valor_parcelado = parcelado
        self.valor_vista = avista
        self.economia = Decimal(self.valor_passagem) - avista

    def save(self, *args, **kwargs):
        self.calcular_valores()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente} - {self.origem} -> {self.destino} ({self.data_ida})"
