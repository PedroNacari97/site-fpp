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
        ("enviada", "Enviada"),
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
    duracao_voo_ida_minutos = models.PositiveIntegerField(default=0)
    fuso_horario_ida = models.SmallIntegerField(default=0)
    duracao_voo_volta_minutos = models.PositiveIntegerField(default=0)
    fuso_horario_volta = models.SmallIntegerField(default=0)
    programa = models.ForeignKey(
        ProgramaFidelidade, on_delete=models.SET_NULL, null=True, blank=True
    )
    qtd_passageiros = models.PositiveIntegerField(default=1)
    classe = models.CharField(max_length=50, blank=True)
    observacoes = models.TextField(blank=True)
    valor_passagem = models.DecimalField(max_digits=10, decimal_places=2)
    taxas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    milhas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_milheiro = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    parcelas = models.IntegerField(default=1)
    juros = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    mostrar_valor_parcelado = models.BooleanField(default=True)
    valor_parcelado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_vista = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_referencia_manual = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Se preenchido, sobrescreve o valor de referencia calculado automaticamente."
    )
    validade = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    economia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    emissao = models.OneToOneField(
        "EmissaoPassagem", on_delete=models.SET_NULL, null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if not self.cliente:
            raise ValidationError({"cliente": "Selecione o cliente que irá viajar."})

    @property
    def economia_total(self):
        if self.economia is None:
            return None
        return Decimal(self.economia) * (self.qtd_passageiros or 1)

    def calcular_valores(self):
        base = (Decimal(self.milhas) / Decimal('1000')) * Decimal(self.valor_milheiro) + Decimal(self.taxas)
        juros_fator = 1 + Decimal(self.juros or 0) / Decimal('100')
        desconto_fator = 1 - Decimal(self.desconto or 0) / Decimal('100')
        parcelado = base * juros_fator
        avista = parcelado * desconto_fator
        self.valor_parcelado = parcelado
        self.valor_vista = avista
        referencia = self.valor_referencia_manual if self.valor_referencia_manual not in (None, "") else Decimal(self.valor_passagem)
        self.economia = referencia - avista

    def save(self, *args, **kwargs):
        self.calcular_valores()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente} - {self.origem} -> {self.destino} ({self.data_ida})"
