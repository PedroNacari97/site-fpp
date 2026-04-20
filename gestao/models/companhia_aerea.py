from django.db import models


class CompanhiaAerea(models.Model):
    CODIGO_LATAM = "LATAM"
    CODIGO_GOL = "GOL"
    CODIGO_AZUL = "AZUL"
    CODIGO_CHOICES = (
        (CODIGO_LATAM, "LATAM"),
        (CODIGO_GOL, "GOL"),
        (CODIGO_AZUL, "Azul"),
    )

    nome = models.CharField("Nome", max_length=100, unique=True)
    site_url = models.URLField("Link para consulta de reserva", blank=True, null=True)
    codigo = models.CharField(
        "Código do scraper",
        max_length=10,
        blank=True,
        choices=CODIGO_CHOICES,
        help_text="Identificador usado para selecionar o scraper de monitoramento.",
    )
    rotulo_codigo_reserva = models.CharField(
        "Rótulo do código de reserva",
        max_length=40,
        default="Código da Reserva",
        help_text="Como o operador chama o código da reserva no portal desta companhia. LATAM usa 'Nº da Ordem'.",
    )

    class Meta:
        verbose_name = "Companhia Aérea"
        verbose_name_plural = "Companhias Aéreas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def codigo_normalizado(self):
        if self.codigo:
            return self.codigo
        nome = (self.nome or "").strip().lower()
        if "latam" in nome:
            return self.CODIGO_LATAM
        if nome == "gol" or "gol linhas" in nome:
            return self.CODIGO_GOL
        if "azul" in nome:
            return self.CODIGO_AZUL
        return ""


