from django.db import models
from django.utils import timezone


class Empresa(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    responsavel_nome = models.CharField(max_length=150, blank=True)
    email_contato = models.EmailField(blank=True)
    telefone_contato = models.CharField(max_length=25, blank=True)
    whatsapp = models.CharField(max_length=25, blank=True)
    website = models.URLField(blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=120, blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    descricao_rodape = models.TextField(blank=True)
    limite_colaboradores = models.PositiveIntegerField(default=0)
    admin = models.OneToOneField(
        "gestao.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="empresa_administrada",
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
