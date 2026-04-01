from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from gestao.models import (
    Aeroporto,
    Cliente,
    CompanhiaAerea,
    EmissaoPassagem,
    Empresa,
    Passageiro,
    ProgramaFidelidade,
)


class EmissaoPreviewViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="previewadmin",
            password="pass123",
        )
        self.empresa = Empresa.objects.create(nome="Empresa Preview")
        self.cliente = Cliente.objects.create(
            usuario=self.user,
            cpf="11122233344",
            perfil="admin",
            empresa=self.empresa,
            ativo=True,
        )
        self.programa = ProgramaFidelidade.objects.create(
            nome="LATAM Pass",
            preco_medio_milheiro=100,
        )
        self.aeroporto_origem = Aeroporto.objects.create(
            sigla="GRU",
            nome="Guarulhos",
            cidade="Sao Paulo",
            estado="SP",
        )
        self.aeroporto_destino = Aeroporto.objects.create(
            sigla="JFK",
            nome="John F. Kennedy",
            cidade="Nova York",
            estado="NY",
        )
        self.companhia = CompanhiaAerea.objects.create(
            nome="LATAM Airlines",
            site_url="https://latam.com",
        )
        self.emissao = EmissaoPassagem.objects.create(
            cliente=self.cliente,
            programa=self.programa,
            companhia_aerea=self.companhia,
            aeroporto_partida=self.aeroporto_origem,
            aeroporto_destino=self.aeroporto_destino,
            data_ida=datetime(2026, 4, 15, 23, 45, tzinfo=timezone.utc),
            data_volta=datetime(2026, 4, 25, 19, 30, tzinfo=timezone.utc),
            bagagem_mao="mao_10kg",
            bagagem_despachada="1x23",
            qtd_adultos=1,
            qtd_criancas=0,
            qtd_bebes=0,
            localizador="ABC123",
            valor_referencia="8900",
            valor_taxas="1250.50",
            valor_total_final="10100.50",
            valor_venda_final="10100.50",
            detalhes="Emissao confirmada. Bilhetes enviados por e-mail.",
        )
        Passageiro.objects.create(
            emissao=self.emissao,
            nome="Joao Silva",
            cpf="123.456.789-00",
            rg="12.345.678-9",
            passaporte="BR123456",
            data_nascimento=datetime(1985, 5, 15, tzinfo=timezone.utc).date(),
            categoria="adulto",
        )
        self.detail_url = reverse("admin_emissao_detalhe", args=[self.emissao.id])
        self.print_url = reverse("admin_emissao_pdf", args=[self.emissao.id])

    def _login(self):
        assert self.client.login(username="previewadmin", password="pass123")

    def test_emissao_detail_uses_preview_layout(self):
        self._login()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visualizacao de Emissao")
        self.assertContains(response, "Passageiros")
        self.assertContains(response, "Imprimir / Salvar PDF")
        self.assertContains(response, "Item pessoal + bagagem de mao ate 10kg")
        self.assertContains(response, "1 bagagem despachada ate 23kg")

    def test_emissao_print_route_returns_pdf(self):
        self._login()

        response = self.client.get(self.print_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(
            f'filename="emissao_preview_{self.emissao.id}.pdf"',
            response["Content-Disposition"],
        )
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))
