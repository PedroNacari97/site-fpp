"""Testes do modulo de monitoramento de status de passagens.

Cobre comparator, sanitize_payload, notifier (mockando o backend de email),
view publica de unsubscribe e o PortalCompanhiaScraperProvider com scraper falso.
"""
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from gestao.models import (
    AcompanhamentoPassagem,
    Aeroporto,
    Cliente,
    CompanhiaAerea,
    EmissaoPassagem,
    Empresa,
    HistoricoVerificacao,
    NotificacaoSistema,
    Passageiro,
    ProgramaFidelidade,
)
from gestao.services.acompanhamento_passagem import sync_acompanhamento_passagem
from gestao.services.monitoring import (
    MudancaDetectada,
    comparar_resultado,
    enviar_alerta_mudanca,
)
from gestao.services.scrapers import register_scraper
from gestao.services.scrapers.base import (
    ResultadoScrape,
    Scraper,
    ScraperError,
    sanitize_payload,
)


def _make_acompanhamento(
    *,
    empresa_nome="Agencia Boa Viagem",
    empresa_email="contato@boaviagem.com.br",
    cliente_email="op@boaviagem.com.br",
    passageiro_email="passageiro@example.com",
    email_consulta="acompanhamento@example.com",
    cia_nome="LATAM",
    cia_codigo=CompanhiaAerea.CODIGO_LATAM,
    status_reserva=AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO,
    status_voo=AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO,
):
    User = get_user_model()
    user = User.objects.create_user(
        username=f"user-{cliente_email}",
        email=cliente_email,
        password="x",
    )
    empresa = Empresa.objects.create(nome=empresa_nome, email_contato=empresa_email)
    cliente = Cliente.objects.create(
        usuario=user,
        cpf="12312312312",
        perfil="admin",
        empresa=empresa,
        ativo=True,
    )
    programa = ProgramaFidelidade.objects.create(nome=f"Smiles-{cia_nome}", preco_medio_milheiro=100)
    origem = Aeroporto.objects.create(sigla="GRU", nome="Guarulhos", cidade="Sao Paulo", estado="SP")
    destino = Aeroporto.objects.create(sigla="MIA", nome="Miami", cidade="Miami", estado="FL")
    cia = CompanhiaAerea.objects.create(
        nome=cia_nome,
        site_url="https://example.com/minhas-viagens",
        codigo=cia_codigo,
    )
    emissao = EmissaoPassagem.objects.create(
        cliente=cliente,
        programa=programa,
        companhia_aerea=cia,
        aeroporto_partida=origem,
        aeroporto_destino=destino,
        data_ida=datetime(2026, 5, 10, 14, 0, tzinfo=dt_timezone.utc),
        qtd_adultos=1,
        qtd_criancas=0,
        qtd_bebes=0,
        localizador="ABC123",
        valor_referencia="3500",
        valor_taxas="220.00",
        valor_total_final="3720.00",
        valor_venda_final="3720.00",
    )
    Passageiro.objects.create(
        emissao=emissao,
        nome="Maria Silva",
        cpf="52998224725",
        email=passageiro_email,
        categoria="adulto",
    )
    acompanhamento = AcompanhamentoPassagem.objects.create(
        emissao=emissao,
        modo_consulta=AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA,
        localizador_consulta="ABC123",
        sobrenome_consulta="Silva",
        email_consulta=email_consulta,
        status_reserva=status_reserva,
        status_voo=status_voo,
    )
    return acompanhamento


class SanitizePayloadTest(TestCase):
    def test_redacta_cpf_cnpj_e_passaporte(self):
        payload = {
            "passageiros": [
                {"nome": "Maria", "doc": "529.982.247-25"},
                {"nome": "Joao", "doc": "12.345.678/0001-99"},
                {"nome": "Ana", "passaporte": "BR1234567"},
            ],
            "bilhete": "1234567890123456",
            "obs": "ok",
        }

        clean = sanitize_payload(payload)

        self.assertEqual(clean["passageiros"][0]["doc"], "[REDACTED]")
        self.assertEqual(clean["passageiros"][1]["doc"], "[REDACTED]")
        self.assertEqual(clean["passageiros"][2]["passaporte"], "[REDACTED]")
        self.assertEqual(clean["bilhete"], "[REDACTED]")
        self.assertEqual(clean["obs"], "ok")
        self.assertEqual(clean["passageiros"][0]["nome"], "Maria")


class ComparatorTest(TestCase):
    def setUp(self):
        self.acomp = _make_acompanhamento()

    def test_sem_mudanca_quando_status_iguais(self):
        resultado = ResultadoScrape(
            sucesso=True,
            status_reserva=self.acomp.status_reserva,
            status_voo=self.acomp.status_voo,
        )

        mud = comparar_resultado(self.acomp, resultado)

        self.assertFalse(mud.mudou)
        self.assertFalse(mud.relevante_para_passageiro)

    def test_mudanca_irrelevante_para_passageiro(self):
        resultado = ResultadoScrape(
            sucesso=True,
            status_reserva=AcompanhamentoPassagem.STATUS_RESERVA_EMITIDO,
            status_voo=AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
        )

        mud = comparar_resultado(self.acomp, resultado)

        self.assertTrue(mud.mudou)
        self.assertFalse(mud.relevante_para_passageiro)

    def test_cancelamento_eh_relevante(self):
        resultado = ResultadoScrape(
            sucesso=True,
            status_reserva=AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
            status_voo=AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
        )

        mud = comparar_resultado(self.acomp, resultado)

        self.assertTrue(mud.mudou)
        self.assertTrue(mud.relevante_para_passageiro)
        self.assertIn("cancelado", mud.resumo_humano())


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_BASE_URL="https://app.ncfly.com.br",
    DEFAULT_FROM_EMAIL="no-reply@ncfly.com.br",
    PORTAL_ALERTS_FROM_EMAIL="alertas@ncfly.com.br",
    MONITORAMENTO_ALERTAS_FROM_EMAIL="alertas-monitoramento@ncfly.com.br",
)
class NotifierTest(TestCase):
    def setUp(self):
        self.acomp = _make_acompanhamento()
        mail.outbox = []

    def _mudanca_critica(self):
        return MudancaDetectada(
            mudou=True,
            status_reserva_anterior=AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO,
            status_voo_anterior=AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO,
            status_reserva_novo=AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
            status_voo_novo=AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
            relevante_para_passageiro=True,
        )

    def test_envia_email_em_nome_da_agencia(self):
        ok = enviar_alerta_mudanca(self.acomp, self._mudanca_critica())

        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn("Agencia Boa Viagem", msg.from_email)
        self.assertIn("alertas-monitoramento@ncfly.com.br", msg.from_email)
        self.assertEqual(msg.reply_to, ["contato@boaviagem.com.br"])
        self.assertIn("Agencia Boa Viagem", msg.subject)
        self.assertIn("Agencia Boa Viagem", msg.body)
        self.assertIn("operadora tecnica", msg.body.lower().replace("é", "e"))

    def test_inclui_header_list_unsubscribe(self):
        enviar_alerta_mudanca(self.acomp, self._mudanca_critica())

        msg = mail.outbox[0]
        link = reverse(
            "monitoramento_unsubscribe", kwargs={"token": str(self.acomp.opt_out_token)}
        )
        self.assertIn(link, msg.extra_headers["List-Unsubscribe"])
        self.assertEqual(
            msg.extra_headers["List-Unsubscribe-Post"],
            "List-Unsubscribe=One-Click",
        )

    def test_destinatarios_dedupedos_e_completos(self):
        enviar_alerta_mudanca(self.acomp, self._mudanca_critica())

        destinatarios = mail.outbox[0].to
        self.assertIn("acompanhamento@example.com", destinatarios)
        self.assertIn("passageiro@example.com", destinatarios)
        self.assertIn("op@boaviagem.com.br", destinatarios)
        self.assertEqual(len(destinatarios), len(set(destinatarios)))

    def test_nao_envia_quando_notificacao_desativada(self):
        self.acomp.notificar_passageiro = False
        self.acomp.save(update_fields=["notificar_passageiro"])

        ok = enviar_alerta_mudanca(self.acomp, self._mudanca_critica())

        self.assertFalse(ok)
        self.assertEqual(mail.outbox, [])

    def test_nao_envia_quando_mudanca_nao_eh_relevante(self):
        irrelevante = MudancaDetectada(
            mudou=True,
            status_reserva_anterior=AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO,
            status_voo_anterior=AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO,
            status_reserva_novo=AcompanhamentoPassagem.STATUS_RESERVA_EMITIDO,
            status_voo_novo=AcompanhamentoPassagem.STATUS_VOO_PROGRAMADO,
            relevante_para_passageiro=False,
        )

        ok = enviar_alerta_mudanca(self.acomp, irrelevante)

        self.assertFalse(ok)
        self.assertEqual(mail.outbox, [])


class UnsubscribeViewTest(TestCase):
    def setUp(self):
        self.acomp = _make_acompanhamento()
        self.url = reverse(
            "monitoramento_unsubscribe", kwargs={"token": str(self.acomp.opt_out_token)}
        )

    def test_get_mostra_pagina_de_confirmacao(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cancelar avisos")
        self.acomp.refresh_from_db()
        self.assertTrue(self.acomp.notificar_passageiro)

    def test_post_desativa_notificacoes(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.acomp.refresh_from_db()
        self.assertFalse(self.acomp.notificar_passageiro)

    def test_token_invalido_retorna_404(self):
        url_invalida = reverse(
            "monitoramento_unsubscribe",
            kwargs={"token": "00000000-0000-0000-0000-000000000000"},
        )
        response = self.client.get(url_invalida)
        self.assertEqual(response.status_code, 404)


class _FakeScraper(Scraper):
    """Scraper sintetico para testar o provider sem tocar Playwright."""

    codigo = CompanhiaAerea.CODIGO_LATAM

    def __init__(self, resultado=None, exc=None):
        self._resultado = resultado
        self._exc = exc
        self.chamadas = []

    def consultar(self, localizador, sobrenome, *, url=""):
        self.chamadas.append((localizador, sobrenome, url))
        if self._exc:
            raise self._exc
        return self._resultado


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_BASE_URL="https://app.ncfly.com.br",
)
class PortalCompanhiaScraperProviderTest(TestCase):
    def setUp(self):
        self.acomp = _make_acompanhamento()
        mail.outbox = []

    def _patch_scraper(self, scraper):
        register_scraper(CompanhiaAerea.CODIGO_LATAM, lambda: scraper)

    def test_mudanca_relevante_grava_historico_e_cria_notificacao_no_portal(self):
        resultado = ResultadoScrape(
            sucesso=True,
            status_reserva=AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
            status_voo=AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
            resumo="Reserva cancelada pela companhia",
            duracao_ms=1234,
            payload_sanitizado={"raw": "ok"},
        )
        scraper = _FakeScraper(resultado=resultado)
        self._patch_scraper(scraper)

        sync = sync_acompanhamento_passagem(self.acomp)

        self.assertTrue(sync.success)
        self.assertEqual(scraper.chamadas[0][:2], ("ABC123", "Silva"))
        self.acomp.refresh_from_db()
        self.assertEqual(
            self.acomp.status_reserva, AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO
        )
        historico = HistoricoVerificacao.objects.get(acompanhamento=self.acomp)
        self.assertTrue(historico.sucesso)
        self.assertTrue(historico.mudou_desde_anterior)
        self.assertTrue(historico.notificacao_disparada)
        self.assertEqual(historico.duracao_ms, 1234)
        # Email NAO eh enviado — modo atual cria alerta no portal.
        self.assertEqual(mail.outbox, [])
        notif = NotificacaoSistema.objects.get(
            usuario=self.acomp.emissao.cliente.usuario
        )
        self.assertEqual(notif.tipo, NotificacaoSistema.Tipo.ALERTA_PASSAGEM)
        self.assertIn("ABC123", notif.titulo)
        self.assertIn("cancelado", notif.mensagem)
        self.assertFalse(notif.lida)

    def test_chave_unica_evita_duplicar_notificacao_para_mesma_mudanca(self):
        from gestao.services.monitoring import (
            MudancaDetectada,
            criar_notificacao_mudanca,
        )

        mudanca = MudancaDetectada(
            mudou=True,
            status_reserva_anterior=AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO,
            status_voo_anterior=AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO,
            status_reserva_novo=AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
            status_voo_novo=AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
            relevante_para_passageiro=True,
        )

        criar_notificacao_mudanca(self.acomp, mudanca)
        notif = NotificacaoSistema.objects.get()
        notif.marcar_lida()
        # Mesma mudanca novamente — mesma chave, atualiza em vez de duplicar
        criar_notificacao_mudanca(self.acomp, mudanca)

        self.assertEqual(NotificacaoSistema.objects.count(), 1)
        notif.refresh_from_db()
        self.assertFalse(notif.lida)

    def test_sem_mudanca_nao_cria_notificacao_mas_grava_historico(self):
        resultado = ResultadoScrape(
            sucesso=True,
            status_reserva=self.acomp.status_reserva,
            status_voo=self.acomp.status_voo,
            payload_sanitizado={},
        )
        self._patch_scraper(_FakeScraper(resultado=resultado))

        sync = sync_acompanhamento_passagem(self.acomp)

        self.assertTrue(sync.success)
        historico = HistoricoVerificacao.objects.get(acompanhamento=self.acomp)
        self.assertFalse(historico.mudou_desde_anterior)
        self.assertFalse(historico.notificacao_disparada)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(NotificacaoSistema.objects.count(), 0)

    def test_scraper_error_grava_falha_e_nao_quebra(self):
        self._patch_scraper(
            _FakeScraper(exc=ScraperError("Portal indisponivel"))
        )

        sync = sync_acompanhamento_passagem(self.acomp)

        self.assertFalse(sync.success)
        self.assertIn("Portal", sync.message)
        historico = HistoricoVerificacao.objects.get(acompanhamento=self.acomp)
        self.assertFalse(historico.sucesso)
        self.assertIn("Portal", historico.erro_mensagem)
        self.acomp.refresh_from_db()
        self.assertEqual(self.acomp.ultimo_erro, "Portal indisponivel")
        self.assertEqual(mail.outbox, [])

    def test_sem_localizador_retorna_erro_amigavel(self):
        self.acomp.localizador_consulta = ""
        self.acomp.save(update_fields=["localizador_consulta"])
        # Mesmo registrando scraper, deve falhar antes de chamar.
        scraper = _FakeScraper(
            resultado=ResultadoScrape(
                sucesso=True,
                status_reserva=self.acomp.status_reserva,
                status_voo=self.acomp.status_voo,
            )
        )
        self._patch_scraper(scraper)

        sync = sync_acompanhamento_passagem(self.acomp)

        self.assertFalse(sync.success)
        self.assertEqual(scraper.chamadas, [])
        self.assertEqual(HistoricoVerificacao.objects.count(), 0)
