from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from gestao.models import (
    AcompanhamentoPassagem,
    Aeroporto,
    Cliente,
    CompanhiaAerea,
    EmissaoPassagem,
    Empresa,
    Passageiro,
    ProgramaFidelidade,
)


class AcompanhamentoPassagemViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username="trackadmin",
            password="pass123",
        )
        self.empresa = Empresa.objects.create(nome="Empresa Tracking")
        self.cliente = Cliente.objects.create(
            usuario=self.user,
            cpf="12312312312",
            perfil="admin",
            empresa=self.empresa,
            ativo=True,
        )
        self.programa = ProgramaFidelidade.objects.create(
            nome="Smiles",
            preco_medio_milheiro=100,
        )
        self.aeroporto_origem = Aeroporto.objects.create(
            sigla="GRU",
            nome="Guarulhos",
            cidade="Sao Paulo",
            estado="SP",
        )
        self.aeroporto_destino = Aeroporto.objects.create(
            sigla="MIA",
            nome="Miami International",
            cidade="Miami",
            estado="FL",
        )
        self.companhia = CompanhiaAerea.objects.create(
            nome="LATAM",
            site_url="https://www.latam.com/br/pt/minhas-viagens",
        )
        self.emissao = EmissaoPassagem.objects.create(
            cliente=self.cliente,
            programa=self.programa,
            companhia_aerea=self.companhia,
            aeroporto_partida=self.aeroporto_origem,
            aeroporto_destino=self.aeroporto_destino,
            data_ida=datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc),
            qtd_adultos=1,
            qtd_criancas=0,
            qtd_bebes=0,
            localizador="XYZ987",
            valor_referencia="3500",
            valor_taxas="220.00",
            valor_total_final="3720.00",
            valor_venda_final="3720.00",
        )
        Passageiro.objects.create(
            emissao=self.emissao,
            nome="Maria Silva",
            cpf="52998224725",
            categoria="adulto",
        )
        self.detail_url = reverse("admin_emissao_detalhe", args=[self.emissao.id])
        self.track_url = reverse("admin_emissao_acompanhamento", args=[self.emissao.id])

    def _login(self):
        assert self.client.login(username="trackadmin", password="pass123")

    def test_visualizacao_cria_acompanhamento_e_exibe_acao(self):
        self._login()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acompanhar Status")
        acompanhamento = AcompanhamentoPassagem.objects.get(emissao=self.emissao)
        self.assertEqual(acompanhamento.localizador_consulta, "XYZ987")
        self.assertEqual(acompanhamento.sobrenome_consulta, "Silva")

    def test_tela_de_acompanhamento_salva_status(self):
        self._login()
        self.client.get(self.track_url)
        acompanhamento = AcompanhamentoPassagem.objects.get(emissao=self.emissao)

        response = self.client.post(
            self.track_url,
            {
                "modo_consulta": AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA,
                "sistema_origem": "",
                "referencia_externa": "EM-ORIGEM-1",
                "localizador_consulta": "XYZ987",
                "sobrenome_consulta": "Silva",
                "email_consulta": "maria@example.com",
                "status_reserva": AcompanhamentoPassagem.STATUS_RESERVA_EMITIDO,
                "status_voo": AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
                "ultimo_resumo": "Bilhete confirmado no portal da companhia.",
                "orientacao_operacional": "Aguardar abertura do check-in.",
                "proxima_verificacao_em": "2026-05-09T10:30",
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        acompanhamento.refresh_from_db()
        self.assertEqual(acompanhamento.referencia_externa, "EM-ORIGEM-1")
        self.assertEqual(acompanhamento.status_reserva, AcompanhamentoPassagem.STATUS_RESERVA_EMITIDO)
        self.assertEqual(acompanhamento.sobrenome_consulta, "Silva")

    def test_comando_de_sincronizacao_manual_atualiza_timestamp(self):
        self._login()
        self.client.get(self.track_url)
        acompanhamento = AcompanhamentoPassagem.objects.get(emissao=self.emissao)
        acompanhamento.modo_consulta = AcompanhamentoPassagem.MODO_MANUAL
        acompanhamento.status_reserva = AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO
        acompanhamento.save()

        response = self.client.post(
            self.track_url,
            {
                "modo_consulta": AcompanhamentoPassagem.MODO_MANUAL,
                "sistema_origem": "",
                "referencia_externa": "",
                "localizador_consulta": "XYZ987",
                "sobrenome_consulta": "Silva",
                "email_consulta": "",
                "status_reserva": AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO,
                "status_voo": AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO,
                "ultimo_resumo": "",
                "orientacao_operacional": "",
                "proxima_verificacao_em": "",
                "ativo": "on",
                "sincronizar": "1",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        acompanhamento.refresh_from_db()
        self.assertIsNotNone(acompanhamento.ultima_sincronizacao_em)
