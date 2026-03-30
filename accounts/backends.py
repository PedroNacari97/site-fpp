from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from gestao.models import Cliente
from gestao.utils import normalize_cpf


class CPFBackend(ModelBackend):
    """
    Autenticação baseada em CPF vinculado ao Cliente.
    Mantém compatibilidade com o backend padrão do Django como fallback.
    """

    def authenticate(self, request, username=None, password=None, cpf=None, **kwargs):
        cpf = normalize_cpf(cpf or username)
        if not cpf:
            return None

        try:
            cliente = Cliente.objects.select_related("usuario").get(cpf=cpf)
        except Cliente.DoesNotExist:
            return None

        if not cliente.ativo:
            return None

        user = cliente.usuario
        if self.user_can_authenticate(user) and user.check_password(password):
            return user
        return None
