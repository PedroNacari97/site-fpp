from datetime import datetime, timezone
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from gestao.models import (
    Aeroporto,
    Cliente,
    ContaAdministrada,
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
            "tipo_emissao": "cliente",
            "cliente": str(self.cliente.id),
            "programa": str(self.programa.id),
            "aeroporto_partida": str(self.aeroporto_origem.id),
            "aeroporto_destino": str(self.aeroporto_destino.id),
            "data_ida": datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc).isoformat(),
            "valor_referencia": "1000",
            "valor_taxas": "500",
            "pontos_utilizados": "0",
            "qtd_adultos": "1",
            "qtd_criancas": "0",
            "qtd_bebes": "0",
            "total_passageiros": "1",
            "passageiro-0-nome": "Maria Teste",
            "passageiro-0-cpf": "123.456.789-00",
            "passageiro-0-data-nascimento": "1990-01-01",
            "passageiro-0-categoria": "adulto",
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

    def test_nova_emissao_administrada_requires_cliente_and_conta(self):
        conta_adm = ContaAdministrada.objects.create(nome="Conta ADM", empresa=self.empresa)
        ContaFidelidade.objects.create(conta_administrada=conta_adm, programa=self.programa)
        self._login()

        payload = self._post_payload(
            {
                "tipo_emissao": "administrada",
                "conta_administrada": str(conta_adm.id),
                "cliente": str(self.cliente.id),
            }
        )
        response = self.client.post(self.url, data=payload, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("admin_emissoes"))
        self.assertTrue(EmissaoPassagem.objects.filter(conta_administrada=conta_adm).exists())

    def test_nova_emissao_allows_pontos_with_program_preco_medio(self):
        ContaFidelidade.objects.create(cliente=self.cliente, programa=self.programa)
        self._login()

        response = self.client.post(
            self.url,
            data=self._post_payload({"pontos_utilizados": "1000"}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("admin_emissoes"))
        self.assertTrue(EmissaoPassagem.objects.exists())

    def test_nova_emissao_blocks_when_sem_valor_medio_ou_preco(self):
        programa_sem_preco = ProgramaFidelidade.objects.create(nome="Programa Sem Preço", preco_medio_milheiro=0)
        ContaFidelidade.objects.create(cliente=self.cliente, programa=programa_sem_preco)
        self._login()

        response = self.client.post(
            self.url,
            data=self._post_payload({"programa": str(programa_sem_preco.id), "pontos_utilizados": "1000"}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Valor médio do milheiro")
        self.assertFalse(EmissaoPassagem.objects.exists())
