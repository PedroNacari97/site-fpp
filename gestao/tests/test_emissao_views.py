from datetime import datetime, timezone
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from gestao.models import (
    Aeroporto,
    Cliente,
    ContaFidelidade,
    EmissaoPassagem,
    Empresa,
    ProgramaFidelidade,
)


class NovaEmissaoViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="admin", password="pass123")
        self.empresa = Empresa.objects.create(nome="Empresa X")
        self.cliente = Cliente.objects.create(
            usuario=self.user, cpf="00000000000", perfil="admin", empresa=self.empresa, ativo=True
        )
        self.programa = ProgramaFidelidade.objects.create(nome="Programa 1", preco_medio_milheiro=100)
        self.aeroporto_origem = Aeroporto.objects.create(sigla="AAA", nome="Origem")
        self.aeroporto_destino = Aeroporto.objects.create(sigla="BBB", nome="Destino")
        self.url = reverse("admin_nova_emissao")

    def _login(self):
        assert self.client.login(username="admin", password="pass123")

    def _post_payload(self, extra=None):
        payload = {
            "tipo_titular": "cliente",
            "cliente": str(self.cliente.id),
            "programa": str(self.programa.id),
            "aeroporto_partida": str(self.aeroporto_origem.id),
            "aeroporto_destino": str(self.aeroporto_destino.id),
            "data_ida": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat(),
            "valor_referencia": "1000",
            "valor_pago": "500",
            "pontos_utilizados": "0",
            "qtd_adultos": "1",
            "qtd_criancas": "0",
            "qtd_bebes": "0",
            "total_passageiros": "1",
        }
        if extra:
            payload.update(extra)
        return payload

    def test_nova_emissao_saves_and_redirects(self):
        ContaFidelidade.objects.create(cliente=self.cliente, programa=self.programa)
        self._login()

        response = self.client.post(self.url, data=self._post_payload(), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("admin_emissoes"))
        self.assertTrue(EmissaoPassagem.objects.exists())

    def test_nova_emissao_without_conta_shows_error(self):
        self._login()

        response = self.client.post(self.url, data=self._post_payload(), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não foi possível salvar a emissão")
        self.assertFalse(EmissaoPassagem.objects.exists())
