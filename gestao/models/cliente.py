from django.contrib.auth import get_user_model
from django.db import models

from gestao.utils import hash_cpf, normalize_cpf


User = get_user_model()

class Cliente(models.Model):
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="cliente_gestao"
    )
    empresa = models.ForeignKey(
        "gestao.Empresa",
        on_delete=models.CASCADE,
        related_name="pessoas",
        null=True,
        blank=True,
    )
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=11, unique=True)
    cpf_hash = models.CharField(max_length=64, blank=True, db_index=True)
    cep = models.CharField(max_length=9, blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=120, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    PERFIS = (
        ("admin", "Administrador"),
        ("operador", "Operador"),
        ("cliente", "Cliente"),
    )
    perfil = models.CharField(max_length=10, choices=PERFIS, default="cliente")

    TIPO_PASSAGEIRO_DIRETO = "passageiro_direto"
    TIPO_CONCIERGE = "concierge"
    TIPO_CONTA_ADMINISTRADA = "conta_administrada"
    TIPO_INTERMEDIARIO = "intermediario"
    TIPO_CLIENTE_CHOICES = (
        (TIPO_PASSAGEIRO_DIRETO, "Passageiro direto"),
        (TIPO_CONCIERGE, "Concierge"),
        (TIPO_CONTA_ADMINISTRADA, "Conta administrada"),
        (TIPO_INTERMEDIARIO, "Intermediario"),
    )
    tipo_cliente = models.CharField(
        max_length=20,
        choices=TIPO_CLIENTE_CHOICES,
        default=TIPO_PASSAGEIRO_DIRETO,
        db_index=True,
    )
    programas_concierge = models.CharField(max_length=255, blank=True)
    razao_social = models.CharField(max_length=255, blank=True)
    cnpj = models.CharField(max_length=20, blank=True)
    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="usuarios_criados",
        null=True, blank=True
    )

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username

    def save(self, *args, **kwargs):
        self.cpf = normalize_cpf(self.cpf)
        self.cpf_hash = hash_cpf(self.cpf)
        super().save(*args, **kwargs)
