from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from gestao.models import AlertaViagem, Cliente, Empresa
from gestao.utils import validate_cpf_digits
from portal.models import Fonte, JobExecucao, LeadPlataforma, MateriaBruta, NoticiaPublicada, PortalMetricDaily


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


class CompanyManagementRulesTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome="Empresa Sem Operadores",
            limite_colaboradores=0,
            ativo=True,
        )
        self.admin_user = User.objects.create_user(username="admin-empresa", password="secret123")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        self.admin_cliente = Cliente.objects.create(
            usuario=self.admin_user,
            empresa=self.empresa,
            cpf="33322211100",
            perfil="admin",
            ativo=True,
        )
        self.empresa.admin = self.admin_cliente
        self.empresa.save(update_fields=["admin"])

        self.superuser = User.objects.create_superuser(
            username="super-admin-test",
            email="super@test.com",
            password="secret123",
        )

    def test_admin_empresa_nao_consegue_criar_operador_quando_limite_e_zero(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("user_create"),
            {
                "nome_completo": "Operador Bloqueado",
                "cpf": "44455566677",
                "perfil": "operador",
                "password": "secret123",
                "empresa": str(self.empresa.id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O limite de 0 colaboradores para esta empresa foi atingido.")
        self.assertFalse(Cliente.objects.filter(cpf="44455566677").exists())

    def test_superadmin_consegue_editar_empresa(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("admin_editar_empresa", args=[self.empresa.id]),
            {
                "nome": "Empresa Ajustada",
                "responsavel_nome": "Maria Gestora",
                "email_contato": "contato@empresa.com",
                "telefone_contato": "11999999999",
                "whatsapp": "11999999999",
                "website": "https://empresa.com",
                "cidade": "Sao Paulo",
                "estado": "SP",
                "endereco": "Rua Teste, 10",
                "descricao_rodape": "Rodape institucional",
                "limite_colaboradores": "3",
                "ativo": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_empresas"))
        self.empresa.refresh_from_db()
        self.assertEqual(self.empresa.nome, "Empresa Ajustada")
        self.assertEqual(self.empresa.limite_colaboradores, 3)


class SuperadminSiteMonitoringTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="super-site",
            email="super-site@example.com",
            password="secret123",
        )
        self.fonte = Fonte.objects.create(
            nome="Fonte Site",
            url="https://example.com",
            tipo_coleta="html",
        )
        materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://example.com/noticia-site",
            titulo_extraido="Noticia do site",
            texto_base="Texto base suficiente para a noticia do site.",
            hash_conteudo="site-monitoramento",
        )
        NoticiaPublicada.objects.create(
            materia_bruta=materia,
            fonte=self.fonte,
            titulo="Noticia publica do portal",
            resumo="Resumo publico.",
            conteudo="Conteudo publico suficiente para o portal.",
            slug="noticia-publica-do-portal",
            categoria="Milhas e Pontos",
            topico="Transferencias e Bonus",
            url_fonte="https://example.com/noticia-site",
            status="published",
            publicada_em=timezone.now(),
        )
        PortalMetricDaily.objects.create(
            metric_date=timezone.localdate(),
            metric_type="page_view",
            path="/home/",
            event_name="",
            section="home",
            article_slug="",
            article_category="",
            article_topic="",
            total=42,
        )
        PortalMetricDaily.objects.create(
            metric_date=timezone.localdate(),
            metric_type="click",
            path="/home/",
            event_name="click_cta_home",
            section="home",
            article_slug="",
            article_category="",
            article_topic="",
            total=7,
        )
        LeadPlataforma.objects.create(
            nome_completo="Maria Lead",
            empresa="Empresa Lead",
            email="maria@example.com",
            telefone="11999999999",
            status="novo",
        )
        JobExecucao.objects.create(
            job_name="sync_home_news",
            status="success",
            quantidade_processada=4,
            quantidade_publicada=2,
        )
        AlertaViagem.objects.create(
            titulo="GRU para MIA",
            conteudo="Alerta teste do portal.",
            continente="América do Norte",
            pais="Estados Unidos",
            cidade_destino="Miami",
            origem="GRU",
            destino="MIA",
            classe=AlertaViagem.CLASSE_ECONOMICA,
            programa_fidelidade="Smiles",
            companhia_aerea="American Airlines",
            valor_milhas=70000,
            datas_ida=["2026-05-10"],
            ativo=True,
        )

    def test_superadmin_visualiza_monitoramento_do_site(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin_site_monitoramento"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panorama do site e da captacao")
        self.assertContains(response, "42")
        self.assertContains(response, "Maria Lead")
        self.assertContains(response, "sync_home_news")
        self.assertContains(response, "GRU -&gt; MIA")

    @override_settings(SITE_ENVIRONMENT="production")
    def test_superadmin_filtra_metricas_e_leads_pelo_ambiente_atual(self):
        PortalMetricDaily.objects.create(
            metric_date=timezone.localdate(),
            site_environment="production",
            site_host="ncfly.com.br",
            metric_type="page_view",
            path="/home/",
            event_name="",
            section="home",
            article_slug="",
            article_category="",
            article_topic="",
            total=99,
        )
        LeadPlataforma.objects.create(
            nome_completo="Lead Producao",
            empresa="Empresa Producao",
            email="producao@example.com",
            telefone="11988887777",
            source_environment="production",
            source_host="ncfly.com.br",
            status="novo",
        )

        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin_site_monitoramento"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "99")
        self.assertContains(response, "Lead Producao")
        self.assertNotContains(response, "42")
        self.assertNotContains(response, "Maria Lead")
