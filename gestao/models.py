from django.db import models
from django.contrib.auth.models import User

from django.db import models
from django.contrib.auth.models import User

class Cliente(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, unique=True)  # novo campo CPF
    PERFIS = (
        ('admin', 'Administrador'),
        ('cliente', 'Cliente'),
    )
    perfil = models.CharField(max_length=10, choices=PERFIS, default='cliente')
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username


    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username

class ProgramaFidelidade(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)

    def __str__(self):
        return self.nome

class ContaFidelidade(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    programa = models.ForeignKey(ProgramaFidelidade, on_delete=models.CASCADE)
    saldo_pontos = models.IntegerField(default=0)
    validade = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.cliente} - {self.programa}'

class ParametroConversao(models.Model):
    programa = models.ForeignKey(ProgramaFidelidade, on_delete=models.CASCADE)
    valor_por_1000_pontos = models.DecimalField(max_digits=10, decimal_places=2)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.programa} - R$ {self.valor_por_1000_pontos}/1000 pontos'

class EmissaoPassagem(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    programa = models.ForeignKey(ProgramaFidelidade, on_delete=models.CASCADE, null=True, blank=True)
    aeroporto_ida = models.CharField(max_length=100)
    aeroporto_volta = models.CharField(max_length=100)
    data_ida = models.DateField()
    data_volta = data_volta = models.DateField(null=True, blank=True)
    qtd_passageiros = models.PositiveIntegerField()
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    pontos_utilizados = models.IntegerField(null=True, blank=True)
    valor_referencia_pontos = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    economia_obtida = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    detalhes = models.TextField(blank=True)

    def __str__(self):
        return f'{self.cliente} - {self.programa} - {self.data_emissao}'



