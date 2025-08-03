from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Empresa(models.Model):
    nome = models.CharField(max_length=100)
    limite_admins = models.IntegerField(null=True, blank=True)
    limite_operadores = models.IntegerField(null=True, blank=True)
    limite_clientes = models.IntegerField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

class Administrador(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    acesso_ate = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username

    def save(self, *args, **kwargs):
        if self.acesso_ate and self.acesso_ate < date.today():
            self.ativo = False
        super().save(*args, **kwargs)
        if not self.ativo:
            from .organizacao import Operador, ClienteEmpresa
            Operador.objects.filter(admin=self).update(ativo=False)
            ClienteEmpresa.objects.filter(admin=self).update(ativo=False)

class Operador(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    admin = models.ForeignKey(Administrador, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username

class ClienteEmpresa(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    operador = models.ForeignKey(Operador, on_delete=models.CASCADE)
    admin = models.ForeignKey(Administrador, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.usuario.get_full_name() or self.usuario.username
