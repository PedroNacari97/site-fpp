from django.db import models

class CompanhiaAerea(models.Model):
    nome = models.CharField("Nome", max_length=100, unique=True)
    site_url = models.URLField("Link para consulta de reserva", blank=True, null=True)

    class Meta:
        verbose_name = "Companhia Aérea"
        verbose_name_plural = "Companhias Aéreas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


