from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from gestao.models import Cliente, ContaFidelidade, Movimentacao, ProgramaFidelidade

User = get_user_model()


class TransferenciaPontosTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin1", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        self.admin_cliente = Cliente.objects.create(
            usuario=self.admin_user, cpf="00000000000", perfil="admin", ativo=True
        )

        self.user_cliente = User.objects.create_user(username="cliente1", password="secret")
        self.cliente = Cliente.objects.create(
            usuario=self.user_cliente, cpf="11111111111", perfil="cliente", ativo=True
        )
        self.prog_origem = ProgramaFidelidade.objects.create(nome="Livelo")
        self.prog_destino = ProgramaFidelidade.objects.create(nome="LATAM")
        self.conta_origem = ContaFidelidade.objects.create(
            cliente=self.cliente, programa=self.prog_origem
        )
        self.conta_destino = ContaFidelidade.objects.create(
            cliente=self.cliente, programa=self.prog_destino
        )
        Movimentacao.objects.create(
            conta=self.conta_origem,
            data=date.today(),
            pontos=10000,
            valor_pago=Decimal("305.00"),
            descricao="Crédito inicial",
        )
        Movimentacao.objects.create(
            conta=self.conta_destino,
            data=date.today(),
            pontos=5000,
            valor_pago=Decimal("100.00"),
            descricao="Crédito inicial",
        )

    def test_transfer_recalculates_destination_average(self):
        self.assertTrue(self.client.login(username="admin1", password="secret"))
        response = self.client.post(
            reverse("admin_transferir_pontos", args=[self.conta_origem.id]),
            {
                "conta_origem": self.conta_origem.id,
                "conta_destino": self.conta_destino.id,
                "data": "01/01/2024",
                "pontos": 10000,
                "bonus_percentual": 30,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.conta_origem.refresh_from_db()
        self.conta_destino.refresh_from_db()

        self.assertEqual(self.conta_origem.saldo_pontos, 0)
        self.assertAlmostEqual(self.conta_origem.valor_total_pago, 0)

        self.assertEqual(self.conta_destino.saldo_pontos, 18000)
        self.assertAlmostEqual(self.conta_destino.valor_total_pago, 405.00)
        self.assertAlmostEqual(self.conta_destino.valor_medio_por_mil, 22.5)
