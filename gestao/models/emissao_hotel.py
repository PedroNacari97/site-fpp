from django.conf import settings
from django.db import models
from .cliente import Cliente


class EmissaoHotel(models.Model):
    STATUS_CHOICES = (
        ("solicitado", "Solicitado"),
        ("cotado", "Cotado"),
        ("confirmado", "Confirmado"),
        ("checkin", "Check-in"),
        ("finalizado", "Finalizado"),
        ("cancelado", "Cancelado"),
    )

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    nome_hotel = models.CharField(max_length=200)
    check_in = models.DateField()
    check_out = models.DateField()
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    economia_obtida = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="solicitado", db_index=True
    )
    voo_vinculado = models.ForeignKey(
        "gestao.CotacaoVoo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hoteis_vinculados",
        help_text="Cotação/voo associado a esta reserva de hotel.",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hoteis_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return f"{self.cliente} - {self.nome_hotel}"
