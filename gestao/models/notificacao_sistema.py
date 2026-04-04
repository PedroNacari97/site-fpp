from django.conf import settings
from django.db import models


class NotificacaoSistema(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes_sistema",
        null=True,
        blank=True,
    )
    empresa = models.ForeignKey(
        "gestao.Empresa",
        on_delete=models.CASCADE,
        related_name="notificacoes_sistema",
        null=True,
        blank=True,
    )
    chave = models.CharField(max_length=191, blank=True, db_index=True)
    titulo = models.CharField(max_length=255, blank=True)
    mensagem = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)
    lida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "chave"],
                condition=~models.Q(chave=""),
                name="unique_notificacao_sistema_usuario_chave",
            )
        ]

    def __str__(self):
        return self.titulo or self.chave or "Notificacao"
