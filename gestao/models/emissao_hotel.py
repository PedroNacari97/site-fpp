from django.db import models
from .cliente import Cliente

class EmissaoHotel(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    nome_hotel = models.CharField(max_length=200)
    check_in = models.DateField()
    check_out = models.DateField()
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    economia_obtida = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.cliente} - {self.nome_hotel}"
