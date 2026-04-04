from django.conf import settings
from django.db import models
from django.utils import timezone


class DocumentoPlataforma(models.Model):
    TIPO_TERMOS = "platform_terms"
    TIPO_PRIVACIDADE = "platform_privacy"
    TIPO_DPA = "platform_dpa"
    TIPO_SEGURANCA = "platform_security"

    TIPOS = (
        (TIPO_TERMOS, "Termos da Plataforma"),
        (TIPO_PRIVACIDADE, "Privacidade da Plataforma"),
        (TIPO_DPA, "DPA / Aditivo de Tratamento de Dados"),
        (TIPO_SEGURANCA, "Politica de Seguranca / Uso Aceitavel"),
    )

    tipo = models.CharField(max_length=40, choices=TIPOS, unique=True)
    versao_atual = models.CharField(max_length=30, default="v1.0")
    data_vigencia = models.DateField(default=timezone.localdate)
    exige_aceite_empresa = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)
    observacoes_internas = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Documento da plataforma"
        verbose_name_plural = "Documentos da plataforma"
        ordering = ["tipo"]

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.versao_atual})"


class AceiteDocumentoPlataforma(models.Model):
    empresa = models.ForeignKey(
        "gestao.Empresa",
        on_delete=models.CASCADE,
        related_name="aceites_documentos_plataforma",
    )
    documento = models.ForeignKey(
        DocumentoPlataforma,
        on_delete=models.CASCADE,
        related_name="aceites",
    )
    versao_aceita = models.CharField(max_length=30)
    aceito_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="aceites_documentos_plataforma",
    )
    aceito_em = models.DateTimeField(auto_now_add=True)
    ip_aceite = models.CharField(max_length=45, blank=True)
    user_agent_aceite = models.CharField(max_length=255, blank=True)
    device_type = models.CharField(max_length=20, blank=True)
    browser_name = models.CharField(max_length=60, blank=True)
    browser_version = models.CharField(max_length=60, blank=True)
    os_name = models.CharField(max_length=60, blank=True)
    os_version = models.CharField(max_length=60, blank=True)
    device_language = models.CharField(max_length=40, blank=True)
    device_timezone = models.CharField(max_length=80, blank=True)
    screen_resolution = models.CharField(max_length=40, blank=True)
    geolocation_status = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geolocation_accuracy_meters = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Aceite de documento da plataforma"
        verbose_name_plural = "Aceites de documentos da plataforma"
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "documento", "versao_aceita"],
                name="unique_aceite_documento_empresa_versao",
            )
        ]
        ordering = ["-aceito_em"]

    def __str__(self):
        return f"{self.empresa} - {self.documento.get_tipo_display()} ({self.versao_aceita})"
