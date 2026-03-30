from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from gestao.models import Cliente
from gestao.utils import validate_cpf_digits


User = get_user_model()


class AuthenticationRulesTest(TestCase):
    def test_inactive_cliente_cannot_authenticate(self):
        user = User.objects.create_user(username="op1", password="secret")
        cliente = Cliente.objects.create(usuario=user, cpf="12345678901", perfil="operador", ativo=False)

        user.refresh_from_db()
        self.assertFalse(user.is_active)

        authenticated = authenticate(cpf=cliente.cpf, password="secret")
        self.assertIsNone(authenticated)


class CPFValidationTest(TestCase):
    def test_cpf_must_have_eleven_digits(self):
        with self.assertRaises(ValidationError):
            validate_cpf_digits("123.456.789-0")
