from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .cliente import Cliente
from .conta_administrada import ContaAdministrada
from .programa_fidelidade import ProgramaFidelidade
from .aeroporto import Aeroporto
from .companhia_aerea import CompanhiaAerea
from .emissor_parceiro import EmissorParceiro
from .emissao_hotel import EmissaoHotel


class EmissaoPassagem(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True, blank=True)
    conta_administrada = models.ForeignKey(
        ContaAdministrada,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="emissoes",
    )
    programa = models.ForeignKey(
        ProgramaFidelidade, on_delete=models.CASCADE, null=True, blank=True
    )
    emissor_parceiro = models.ForeignKey(
        EmissorParceiro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emissoes",
    )
    criado_em = models.DateTimeField(default=timezone.now)
    valor_milheiro_parceiro = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    valor_venda_final = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    valor_total_final = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    custo_emissor = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    valor_cobrado_cliente = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    milhas_do_cliente = models.BooleanField(default=False)
    custo_total = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    lucro = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hotel_vinculado = models.ForeignKey(
        EmissaoHotel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emissoes_vinculadas",
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
    localizador = models.CharField(max_length=100, blank=True)
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_taxas = models.DecimalField(max_digits=10, decimal_places=2)
    pontos_utilizados = models.IntegerField(null=True, blank=True)
    valor_referencia_pontos = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    economia_obtida = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    detalhes = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if not self.cliente:
            raise ValidationError({"cliente": "Selecione o cliente que irá viajar."})

    def save(self, *args, **kwargs):
        self.qtd_passageiros = self.qtd_adultos + self.qtd_criancas + self.qtd_bebes
        pontos = Decimal(self.pontos_utilizados or 0)
        valor_milheiro = Decimal(self.valor_milheiro_parceiro or 0)
        custo_milhas = (pontos / Decimal("1000")) * valor_milheiro
        incluir_taxas = not self.emissor_parceiro_id and not self.conta_administrada_id
        custo_total = custo_milhas + (Decimal(self.valor_taxas or 0) if incluir_taxas else Decimal("0"))
        if self.emissor_parceiro_id and self.custo_emissor not in (None, ""):
            custo_total = Decimal(self.custo_emissor or 0)
        self.custo_total = custo_total
        valor_final_cliente = self.valor_venda_final
        valor_total = self.valor_total_final
        if self.emissor_parceiro_id and self.valor_cobrado_cliente not in (None, ""):
            base_lucro = Decimal(self.valor_cobrado_cliente or 0)
        elif valor_total not in (None, ""):
            base_lucro = Decimal(valor_total or 0)
        elif valor_final_cliente not in (None, ""):
            base_lucro = Decimal(valor_final_cliente or 0)
        else:
            base_lucro = None
        if base_lucro is not None:
            self.lucro = base_lucro - custo_total
        elif self.lucro is None:
            self.lucro = Decimal("0")
        valor_cliente = (
            Decimal(self.valor_cobrado_cliente or 0)
            if self.emissor_parceiro_id and self.valor_cobrado_cliente not in (None, "")
            else (Decimal(valor_final_cliente or 0) if valor_final_cliente not in (None, "") else None)
        )
        if valor_cliente is not None:
            self.economia_obtida = valor_cliente - Decimal(self.valor_referencia or 0)
        else:
            self.economia_obtida = None
        super().save(*args, **kwargs)

    def __str__(self):
        titular = self.cliente or self.conta_administrada
        return f"{titular} - {self.programa} - {self.data_ida}"
