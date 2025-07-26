from django.db import models
from django.contrib.auth.models import User

class Cliente(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cliente_gestao')
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, unique=True)
    PERFIS = (
        ('admin', 'Administrador'),
        ('cliente', 'Cliente'),
    )
    perfil = models.CharField(max_length=10, choices=PERFIS, default='cliente')
    observacoes = models.TextField(blank=True)

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

    PERIODICIDADE_CLUBE = (
        ('nenhum', 'Nenhum'),
        ('mensal', 'Mensal'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
    )
    clube_periodicidade = models.CharField(
        max_length=12, choices=PERIODICIDADE_CLUBE, default='nenhum')
    pontos_clube_mes = models.IntegerField(default=0)
    valor_assinatura_clube = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    data_inicio_clube = models.DateField(null=True, blank=True)
    validade = models.DateField(null=True, blank=True)

    @property
    def saldo_pontos(self):
        movs = self.movimentacoes.all()
        return sum(m.pontos for m in movs) if movs.exists() else 0

    @property
    def valor_total_pago(self):
        movs = self.movimentacoes.all()
        return sum(float(m.valor_pago) for m in movs) if movs.exists() else 0

    def __str__(self):
        return f'{self.cliente} - {self.programa}'

class MovimentacaoPontos(models.Model):
    conta = models.ForeignKey(ContaFidelidade, on_delete=models.CASCADE, related_name='movimentacoes')
    data = models.DateTimeField(auto_now_add=True)
    pontos = models.IntegerField(help_text="Positivo para adicionar, negativo para remover")
    descricao = models.CharField(max_length=200, blank=True)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.conta} - {self.data:%d/%m/%Y} - {self.pontos}'

class EmissaoPassagem(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    programa = models.ForeignKey(ProgramaFidelidade, on_delete=models.CASCADE, null=True, blank=True)
    aeroporto_ida = models.CharField(max_length=100)
    aeroporto_volta = models.CharField(max_length=100)
    data_ida = models.DateField()
    data_volta = models.DateField(null=True, blank=True)
    qtd_passageiros = models.PositiveIntegerField()
    valor_referencia = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2)
    pontos_utilizados = models.IntegerField(null=True, blank=True)
    valor_referencia_pontos = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    economia_obtida = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    detalhes = models.TextField(blank=True)

    def __str__(self):
        return f'{self.cliente} - {self.programa} - {self.data_ida}'
