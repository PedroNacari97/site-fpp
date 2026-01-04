from django.db import models


class NotificacaoSistema(models.Model):
    titulo = models.CharField(max_length=255)
    mensagem = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return self.titulo
