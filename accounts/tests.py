from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

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


class SingleSessionEnforcementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="superroot",
            email="root@example.com",
            password="secret123",
        )
        self.first_machine = Client()
        self.second_machine = Client()
        self.protected_url = reverse("user_list")

    def test_new_login_invalidates_previous_machine_session(self):
        self.assertTrue(
            self.first_machine.login(username="superroot", password="secret123")
        )
        first_response = self.first_machine.get(self.protected_url)
        self.assertEqual(first_response.status_code, 200)

        self.assertTrue(
            self.second_machine.login(username="superroot", password="secret123")
        )
        second_response = self.second_machine.get(self.protected_url)
        self.assertEqual(second_response.status_code, 200)

        stale_response = self.first_machine.get(self.protected_url)
        self.assertEqual(stale_response.status_code, 302)
        self.assertIn(reverse("login_custom"), stale_response.url)


class LoginSecurityFlowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="client-user", password="secret123")
        self.cliente = Cliente.objects.create(
            usuario=self.user,
            cpf="12345678901",
            perfil="cliente",
            ativo=True,
        )

    def test_wrong_profile_does_not_authenticate(self):
        response = self.client.post(
            reverse("login_custom"),
            {
                "identifier": "123.456.789-01",
                "password": "secret123",
                "perfil": "admin",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(SECURITY_LOGIN_FAILURE_LIMIT=3, SECURITY_LOGIN_LOCKOUT_MINUTES=5)
    def test_login_is_locked_after_repeated_failures(self):
        login_url = reverse("login_custom")
        payload = {
            "identifier": "123.456.789-01",
            "password": "wrong-pass",
            "perfil": "cliente",
        }

        for _ in range(3):
            self.client.post(login_url, payload)

        locked_response = self.client.post(login_url, payload)
        self.assertContains(locked_response, "Muitas tentativas de acesso", status_code=200)


class SuperadminMfaTest(TestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SUPERADMIN_MFA_ENABLED=True,
    )
    def test_superadmin_login_requires_email_code(self):
        User.objects.create_superuser(
            username="root-sec",
            email="root-sec@example.com",
            password="secret123",
        )

        start_response = self.client.post(
            reverse("superadmin_login"),
            {"identifier": "root-sec", "password": "secret123", "perfil": "superadmin"},
        )
        self.assertEqual(start_response.status_code, 200)
        self.assertContains(start_response, "Codigo de verificacao", status_code=200)
        self.assertEqual(len(mail.outbox), 1)

        verification_code = "".join(ch for ch in mail.outbox[0].body if ch.isdigit())[:6]
        final_response = self.client.post(
            reverse("superadmin_login"),
            {"action": "verify_mfa", "mfa_code": verification_code},
        )
        self.assertEqual(final_response.status_code, 302)
        self.assertEqual(final_response.url, reverse("admin_dashboard"))


class SessionTimeoutTest(TestCase):
    @override_settings(ADMIN_SESSION_IDLE_TIMEOUT_SECONDS=1)
    def test_admin_session_expires_after_inactivity(self):
        user = User.objects.create_user(username="admin-timeout", password="secret123")
        Cliente.objects.create(
            usuario=user,
            cpf="22222222222",
            perfil="admin",
            ativo=True,
        )

        self.assertTrue(self.client.login(username="admin-timeout", password="secret123"))
        session = self.client.session
        session["last_activity_at"] = 1
        session.save()

        response = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login_custom"), response.url)
