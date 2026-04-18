"""
Testes do painel /adm/financeiro/ — lado agencia.

Foco: isolamento multi-tenant (empresa A nao enxerga dados de B)
e resposta gracciosa quando a empresa ainda nao tem assinatura.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from gestao.models import Cliente, Empresa
from onboarding.models import Assinatura, Pagamento, Plano


class FinanceiroAgenciaIsolamentoTest(TestCase):
    """Garante que uma agencia nao consegue ver pagamentos de outra."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()

        self.empresa_a = Empresa.objects.create(nome="Agencia A")
        self.empresa_b = Empresa.objects.create(nome="Agencia B")

        self.user_a = User.objects.create_user(username="admin_a", password="pass123")
        self.user_b = User.objects.create_user(username="admin_b", password="pass123")

        Cliente.objects.create(
            usuario=self.user_a, cpf="11111111111",
            perfil="admin", empresa=self.empresa_a, ativo=True,
        )
        Cliente.objects.create(
            usuario=self.user_b, cpf="22222222222",
            perfil="admin", empresa=self.empresa_b, ativo=True,
        )

        self.plano = Plano.objects.create(
            nome="Profissional", slug="profissional",
            preco_mensal=Decimal("199.00"), trial_dias=14,
        )
        self.assinatura_a = Assinatura.objects.create(
            empresa=self.empresa_a, plano=self.plano, status="ativa",
            trial_fim=timezone.now(),
        )
        self.assinatura_b = Assinatura.objects.create(
            empresa=self.empresa_b, plano=self.plano, status="ativa",
            trial_fim=timezone.now(),
        )
        Pagamento.objects.create(
            assinatura=self.assinatura_a, valor=Decimal("199.00"),
            status="confirmado", metodo="pix", gateway_ref="REF_A_1",
        )
        Pagamento.objects.create(
            assinatura=self.assinatura_b, valor=Decimal("199.00"),
            status="confirmado", metodo="pix", gateway_ref="REF_B_1",
        )

    def test_agencia_a_nao_ve_pagamento_de_agencia_b(self):
        self.client.login(username="admin_a", password="pass123")
        resp = self.client.get(reverse("admin_financeiro_pagamentos"))
        self.assertEqual(resp.status_code, 200)
        # O valor do gateway_ref de B nao pode aparecer no HTML da A.
        self.assertNotContains(resp, "REF_B_1")
        self.assertContains(resp, "REF_A_1")

    def test_dashboard_financeiro_mostra_propria_assinatura(self):
        self.client.login(username="admin_a", password="pass123")
        resp = self.client.get(reverse("admin_financeiro"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Profissional")
        self.assertContains(resp, "Agencia A")
        self.assertNotContains(resp, "Agencia B")


class FinanceiroAgenciaSemAssinaturaTest(TestCase):
    """A view deve responder com aviso, nao 500, quando nao ha assinatura."""

    def setUp(self):
        User = get_user_model()
        self.empresa = Empresa.objects.create(nome="Agencia Sem Assinatura")
        self.user = User.objects.create_user(username="admin_x", password="pass123")
        Cliente.objects.create(
            usuario=self.user, cpf="33333333333",
            perfil="admin", empresa=self.empresa, ativo=True,
        )

    def test_dashboard_sem_assinatura_responde_200(self):
        self.client.login(username="admin_x", password="pass123")
        resp = self.client.get(reverse("admin_financeiro"))
        self.assertEqual(resp.status_code, 200)
        # Aceita tanto unicode direto quanto escapado, conforme renderer.
        body = resp.content.decode("utf-8", errors="ignore").lower()
        self.assertTrue(
            ("ainda não tem assinatura" in body) or ("ainda n&#227;o tem assinatura" in body)
        )

    def test_download_contrato_sem_registro_redireciona(self):
        self.client.login(username="admin_x", password="pass123")
        resp = self.client.get(reverse("admin_financeiro_contrato"))
        # Hoje redireciona com mensagem — nao 500, nao 404 bruto.
        self.assertIn(resp.status_code, (302, 200))
