from django.db import models


class TelegramNoticiaEvento(models.Model):
    STATUS_RECEBIDO = "recebido"
    STATUS_PROCESSADO = "processado"
    STATUS_IGNORADO = "ignorado"
    STATUS_ERRO = "erro"
    STATUS_CHOICES = [
        (STATUS_RECEBIDO, "Recebido"),
        (STATUS_PROCESSADO, "Processado"),
        (STATUS_IGNORADO, "Ignorado"),
        (STATUS_ERRO, "Erro"),
    ]

    update_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    message_id = models.BigIntegerField(blank=True, null=True)
    chat_nome = models.CharField(max_length=255, blank=True)
    remetente = models.CharField(max_length=255, blank=True)
    mensagem_hash = models.CharField(max_length=64, blank=True, db_index=True)
    texto_bruto = models.TextField(blank=True)
    payload_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_RECEBIDO)
    erro = models.TextField(blank=True)
    noticia = models.ForeignKey(
        "portal.NoticiaPublicada",
        related_name="telegram_eventos_noticia",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    recebido_em = models.DateTimeField(auto_now_add=True)
    processado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-recebido_em"]
        verbose_name = "Evento de noticia Telegram"
        verbose_name_plural = "Eventos de noticias Telegram"

    def __str__(self):
        return f"Telegram news update {self.update_id} ({self.status})"
