from django.db import models


class InstagramNoticiaEvento(models.Model):
    STATUS_PENDENTE = "pendente"
    STATUS_PUBLICADO = "publicado"
    STATUS_ERRO = "erro"
    STATUS_IGNORADO = "ignorado"
    STATUS_CHOICES = [
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_PUBLICADO, "Publicado"),
        (STATUS_ERRO, "Erro"),
        (STATUS_IGNORADO, "Ignorado"),
    ]

    noticia = models.ForeignKey(
        "portal.NoticiaPublicada",
        related_name="instagram_eventos",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
        db_index=True,
    )
    ig_media_id = models.CharField(max_length=64, blank=True)
    ig_post_id = models.CharField(max_length=64, blank=True)
    caption = models.TextField(blank=True)
    image_url = models.URLField(blank=True, max_length=500)
    tentativas = models.PositiveSmallIntegerField(default=0)
    erro = models.TextField(blank=True)
    payload_json = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Evento de notícia Instagram"
        verbose_name_plural = "Eventos de notícias Instagram"

    def __str__(self):
        return f"Instagram noticia={self.noticia_id} ({self.status})"
