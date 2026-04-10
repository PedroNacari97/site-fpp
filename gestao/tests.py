import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from gestao.forms import CotacaoVooForm, NovoClienteForm, ProgramaFidelidadeForm
from gestao.models import (
    AlertaViagem,
    Aeroporto,
    Empresa,
    Cliente,
    CompanhiaAerea,
    ContaFidelidade,
    CotacaoVoo,
    EmissaoPassagem,
    InteresseViagemCliente,
    InteresseViagemMatch,
    Movimentacao,
    NotificacaoSistema,
    PassageiroFrequente,
    ProgramaFidelidade,
    TelegramAlertaEvento,
    TelegramNoticiaEvento,
)
from gestao.services.dashboard import build_operational_notifications
from gestao.services.interesses_viagem import sync_alerta_interest_matches
from portal.models import Fonte, MateriaBruta, NoticiaPublicada

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


class ProgramaVinculadoSaldoTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin2", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        self.admin_cliente = Cliente.objects.create(
            usuario=self.admin_user, cpf="22222222222", perfil="admin", ativo=True
        )

        self.user_cliente = User.objects.create_user(username="cliente2", password="secret")
        self.cliente = Cliente.objects.create(
            usuario=self.user_cliente, cpf="33333333333", perfil="cliente", ativo=True
        )
        self.programa_base = ProgramaFidelidade.objects.create(
            nome="Azul", tipo=ProgramaFidelidade.TIPO_PRINCIPAL
        )
        self.programa_vinculado = ProgramaFidelidade.objects.create(
            nome="Azul pelo Mundo",
            tipo=ProgramaFidelidade.TIPO_VINCULADO,
            programa_base=self.programa_base,
            preco_medio_milheiro=Decimal("35.00"),
        )
        self.conta_base = ContaFidelidade.objects.create(
            cliente=self.cliente, programa=self.programa_base
        )
        self.conta_vinculada = ContaFidelidade.objects.create(
            cliente=self.cliente, programa=self.programa_vinculado
        )
        Movimentacao.objects.create(
            conta=self.conta_base,
            data=date.today(),
            pontos=100000,
            valor_pago=Decimal("2800.00"),
            descricao="Crédito base",
        )

    def test_saldo_compartilhado_e_valor_proprio(self):
        self.assertEqual(self.conta_vinculada.saldo_pontos, 100000)
        self.assertAlmostEqual(self.conta_vinculada.valor_total_pago, 2800.00)
        self.assertEqual(self.conta_vinculada.conta_saldo().id, self.conta_base.id)

        # Valor estimado deve usar o valor do milheiro do programa vinculado
        saldo = self.conta_vinculada.saldo_pontos
        valor_medio_programa = float(self.conta_vinculada.programa.preco_medio_milheiro)
        self.assertEqual((saldo / 1000) * valor_medio_programa, 3500.0)
        # O valor médio do milheiro exibido no card deve refletir o programa vinculado, não o programa base
        self.assertAlmostEqual(self.conta_vinculada.valor_medio_por_mil, 35.0)

    def test_nova_movimentacao_redireciona_para_base(self):
        self.assertTrue(self.client.login(username="admin2", password="secret"))
        response = self.client.get(
            reverse("admin_nova_movimentacao", args=[self.conta_vinculada.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url, reverse("admin_movimentacoes", args=[self.conta_base.id])
        )


class ClubeContaFidelidadeRecorrenciaTest(TestCase):
    def setUp(self):
        self.user_cliente = User.objects.create_user(username="cliente-clube", password="secret")
        self.cliente = Cliente.objects.create(
            usuario=self.user_cliente,
            cpf="55566677788",
            perfil="cliente",
            ativo=True,
        )
        self.programa = ProgramaFidelidade.objects.create(nome="Smiles")

    def test_recorrencia_mensal_gera_movimentacoes_e_recalcula_valor_medio(self):
        conta = ContaFidelidade.objects.create(
            cliente=self.cliente,
            programa=self.programa,
            clube_periodicidade="mensal",
            pontos_clube_mes=1000,
            valor_assinatura_clube=Decimal("42.00"),
            data_inicio_clube=timezone.localdate() - timedelta(days=65),
        )

        saldo = conta.saldo_pontos
        valor_total = Decimal(str(conta.valor_total_pago))

        self.assertEqual(saldo, 3000)
        self.assertEqual(valor_total, Decimal("126.00"))
        self.assertAlmostEqual(conta.valor_medio_por_mil, 42.0)
        self.assertEqual(conta.movimentacoes_compartilhadas.filter(tipo=Movimentacao.TIPO_CLUBE).count(), 3)

    def test_recorrencia_trimestral_respeita_intervalo_da_cobranca(self):
        conta = ContaFidelidade.objects.create(
            cliente=self.cliente,
            programa=self.programa,
            clube_periodicidade="trimestral",
            pontos_clube_mes=5000,
            valor_assinatura_clube=Decimal("180.00"),
            data_inicio_clube=timezone.localdate() - timedelta(days=220),
        )

        saldo = conta.saldo_pontos

        self.assertEqual(saldo, 15000)
        self.assertEqual(conta.movimentacoes_compartilhadas.filter(tipo=Movimentacao.TIPO_CLUBE).count(), 3)
        self.assertAlmostEqual(conta.valor_medio_por_mil, 36.0)


class ProgramaLogoValidationTest(TestCase):
    def test_logo_must_be_png_with_max_50kb(self):
        oversized_logo = SimpleUploadedFile(
            "livelo.png",
            b"\x89PNG\r\n\x1a\n" + b"0" * (50 * 1024),
            content_type="image/png",
        )
        form = ProgramaFidelidadeForm(
            data={
                "nome": "Livelo",
                "descricao": "",
                "preco_medio_milheiro": "15.00",
                "quantidade_cpfs_disponiveis": "",
                "limite_cpfs": "",
                "tipo_regra_reset": "ano",
                "dias_reset": "",
                "tipo": "principal",
                "programa_base": "",
            },
            files={"logo": oversized_logo},
        )

        self.assertFalse(form.is_valid())
        self.assertIn("logo", form.errors)


class CotacaoParaEmissaoFlowTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin-cot", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        self.admin_cliente = Cliente.objects.create(
            usuario=self.admin_user,
            cpf="39053344705",
            perfil="admin",
            ativo=True,
        )

        self.cliente_user = User.objects.create_user(username="cliente-cot", password="secret")
        self.cliente = Cliente.objects.create(
            usuario=self.cliente_user,
            cpf="11144477735",
            perfil="cliente",
            ativo=True,
        )
        self.programa = ProgramaFidelidade.objects.create(
            nome="Livelo",
            preco_medio_milheiro=Decimal("35.00"),
        )
        self.conta = ContaFidelidade.objects.create(cliente=self.cliente, programa=self.programa)
        Movimentacao.objects.create(
            conta=self.conta,
            data=date.today(),
            pontos=50000,
            valor_pago=Decimal("1750.00"),
            descricao="Saldo inicial",
        )
        self.origem = Aeroporto.objects.create(sigla="GRU", nome="Guarulhos")
        self.destino = Aeroporto.objects.create(sigla="JFK", nome="John F Kennedy")
        self.companhia = CompanhiaAerea.objects.create(nome="LATAM")
        self.data_ida = timezone.now().replace(second=0, microsecond=0)
        self.validade = date.today()
        self.client.force_login(self.admin_user)

    def _cotacao_payload(self):
        return {
            "tipo_titular": "cliente",
            "cliente": str(self.cliente.id),
            "conta_administrada": "",
            "companhia_aerea": self.companhia.nome,
            "origem": str(self.origem.id),
            "destino": str(self.destino.id),
            "programa": str(self.programa.id),
            "data_ida": self.data_ida.strftime("%Y-%m-%dT%H:%M"),
            "data_volta": "",
            "qtd_passageiros": "1",
            "classe": "Economica",
            "observacoes": "Cotacao de teste",
            "valor_passagem": "2500.00",
            "taxas": "150.00",
            "milhas": "20000",
            "valor_milheiro": "35.00",
            "parcelas": "1",
            "juros": "1.00",
            "desconto": "1.00",
            "validade": self.validade.isoformat(),
            "status": "emissao",
        }

    def _create_cotacao_emitida(self):
        return CotacaoVoo.objects.create(
            cliente=self.cliente,
            companhia_aerea=self.companhia.nome,
            origem=self.origem,
            destino=self.destino,
            data_ida=self.data_ida,
            programa=self.programa,
            qtd_passageiros=1,
            classe="Economica",
            observacoes="Cotacao de teste",
            valor_passagem=Decimal("2500.00"),
            taxas=Decimal("150.00"),
            milhas=20000,
            valor_milheiro=Decimal("35.00"),
            parcelas=1,
            juros=Decimal("1.00"),
            desconto=Decimal("1.00"),
            validade=self.validade,
            status="emissao",
        )

    def test_cotacao_emitida_redireciona_para_complemento_de_emissao(self):
        response = self.client.post(reverse("admin_nova_cotacao_voo"), self._cotacao_payload())

        self.assertEqual(response.status_code, 302)
        cotacao = CotacaoVoo.objects.get()
        self.assertEqual(response.url, f"{reverse('admin_nova_emissao')}?cotacao_id={cotacao.id}")
        cotacao.refresh_from_db()
        self.assertEqual(cotacao.status, "emissao")
        self.assertIsNone(cotacao.emissao)

    def test_tela_de_emissao_mostra_faltantes_da_cotacao(self):
        cotacao = self._create_cotacao_emitida()

        response = self.client.get(reverse("admin_nova_emissao"), {"cotacao_id": cotacao.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{cotacao.id}"')
        self.assertContains(response, "Complementar emissao da cotacao")
        self.assertContains(response, "Localizador da reserva.")

    def test_tela_de_emissao_preenche_campos_correspondentes_da_cotacao(self):
        cotacao = self._create_cotacao_emitida()

        response = self.client.get(reverse("admin_nova_emissao"), {"cotacao_id": cotacao.id})

        self.assertEqual(response.status_code, 200)
        initial = response.context["form"].initial
        self.assertEqual(initial["tipo_emissao"], "cliente")
        self.assertEqual(initial["cliente"], self.cliente.id)
        self.assertEqual(initial["programa"], self.programa.id)
        self.assertEqual(initial["companhia_aerea"], self.companhia.id)
        self.assertEqual(initial["aeroporto_partida"], self.origem.id)
        self.assertEqual(initial["aeroporto_destino"], self.destino.id)
        self.assertEqual(initial["qtd_adultos"], 1)
        self.assertEqual(initial["qtd_criancas"], 0)
        self.assertEqual(initial["qtd_bebes"], 0)
        self.assertEqual(initial["valor_referencia"], Decimal("2500.00"))
        self.assertEqual(initial["valor_taxas"], Decimal("150.00"))
        self.assertEqual(initial["pontos_utilizados"], 20000)
        self.assertEqual(initial["valor_referencia_pontos"], Decimal("700.00"))
        self.assertEqual(initial["valor_milheiro_parceiro"], Decimal("35.00"))
        self.assertEqual(initial["valor_venda_final"], Decimal("850.00"))
        self.assertEqual(initial["valor_total_final"], Decimal("850.00"))
        self.assertEqual(initial["economia_obtida"], Decimal("1650.00"))
        self.assertTrue(initial["milhas_do_cliente"])
        self.assertIn("Cotacao de teste", initial["detalhes"])
        self.assertIn("Classe cotada: Economica", initial["detalhes"])

    def test_concluir_emissao_vincula_cotacao(self):
        cotacao = self._create_cotacao_emitida()

        response = self.client.post(
            reverse("admin_nova_emissao"),
            {
                "cotacao_id": str(cotacao.id),
                "tipo_emissao": "cliente",
                "cliente": str(self.cliente.id),
                "conta_administrada": "",
                "programa": str(self.programa.id),
                "emissor_parceiro": "",
                "aeroporto_partida": str(self.origem.id),
                "aeroporto_destino": str(self.destino.id),
                "data_ida": self.data_ida.strftime("%Y-%m-%dT%H:%M"),
                "data_volta": "",
                "qtd_adultos": "1",
                "qtd_criancas": "0",
                "qtd_bebes": "0",
                "companhia_aerea": str(self.companhia.id),
                "localizador": "ABC123",
                "valor_referencia": "2500.00",
                "valor_taxas": "150.00",
                "pontos_utilizados": "20000",
                "valor_referencia_pontos": "",
                "economia_obtida": "",
                "detalhes": "Cotacao convertida",
                "valor_milheiro_parceiro": "",
                "valor_venda_final": "2200.00",
                "valor_total_final": "2200.00",
                "custo_emissor": "",
                "valor_cobrado_cliente": "",
                "milhas_do_cliente": "",
                "lucro": "",
                "hotel_vinculado": "",
                "criar_hotel_nome": "",
                "criar_hotel_check_in": "",
                "criar_hotel_check_out": "",
                "total_passageiros": "1",
                "passageiro-0-nome": "Fulano Teste",
                "passageiro-0-cpf": "52998224725",
                "passageiro-0-rg": "RG123",
                "passageiro-0-passaporte": "",
                "passageiro-0-passaporte-validade": "",
                "passageiro-0-data-nascimento": "1990-01-01",
                "passageiro-0-observacoes": "",
                "passageiro-0-categoria": "adulto",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin_emissoes"))
        cotacao.refresh_from_db()
        self.assertIsNotNone(cotacao.emissao_id)
        self.assertEqual(cotacao.status, "emissao")
        self.assertTrue(EmissaoPassagem.objects.filter(id=cotacao.emissao_id).exists())

    def test_visualizacao_de_cotacao_exibe_ctas(self):
        cotacao = self._create_cotacao_emitida()

        response = self.client.get(reverse("admin_visualizar_cotacao_voo", args=[cotacao.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visualizacao de Cotacao")
        self.assertContains(response, "Enviar por E-mail")
        self.assertContains(response, "Imprimir / Salvar PDF")
        self.assertContains(response, "Valor economizado")
        self.assertContains(response, reverse("admin_cotacao_voo_pdf", args=[cotacao.id]))

    def test_lista_de_cotacoes_usa_cta_de_visualizacao(self):
        cotacao = self._create_cotacao_emitida()

        response = self.client.get(reverse("admin_cotacoes_voo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visualizar Cotacao")
        self.assertContains(response, reverse("admin_visualizar_cotacao_voo", args=[cotacao.id]))

    def test_pdf_de_cotacao_retorna_arquivo_pdf(self):
        cotacao = self._create_cotacao_emitida()

        response = self.client.get(reverse("admin_cotacao_voo_pdf", args=[cotacao.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(f'filename="cotacao_preview_{cotacao.id}.pdf"', response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_visualizacao_de_cotacao_separa_ida_e_volta_em_blocos(self):
        cotacao = CotacaoVoo.objects.create(
            cliente=self.cliente,
            companhia_aerea=self.companhia.nome,
            origem=self.origem,
            destino=self.destino,
            data_ida=self.data_ida,
            data_volta=self.data_ida + timedelta(days=4),
            duracao_voo_ida_minutos=330,
            fuso_horario_ida=1,
            duracao_voo_volta_minutos=360,
            fuso_horario_volta=-1,
            programa=self.programa,
            qtd_passageiros=1,
            classe="Economica",
            observacoes="Cotacao com volta",
            valor_passagem=Decimal("2500.00"),
            taxas=Decimal("150.00"),
            milhas=20000,
            valor_milheiro=Decimal("35.00"),
            parcelas=1,
            juros=Decimal("1.00"),
            desconto=Decimal("1.00"),
            validade=self.validade,
            status="pendente",
        )

        response = self.client.get(reverse("admin_visualizar_cotacao_voo", args=[cotacao.id]))
        expected_ida_chegada = timezone.localtime(self.data_ida + timedelta(minutes=330, hours=1)).strftime("%H:%M")
        expected_volta_chegada = timezone.localtime((self.data_ida + timedelta(days=4)) + timedelta(minutes=360, hours=-1)).strftime("%H:%M")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["voos"]), 2)
        self.assertEqual(response.context["voos"][0]["label"], "Ida")
        self.assertEqual(response.context["voos"][0]["destino_hora"], expected_ida_chegada)
        self.assertIn("05h30", response.context["voos"][0]["trajeto_hint"])
        self.assertIn("Fuso +1h", response.context["voos"][0]["trajeto_hint"])
        self.assertEqual(response.context["voos"][1]["label"], "Volta")
        self.assertEqual(response.context["voos"][1]["destino_hora"], expected_volta_chegada)
        self.assertIn("06h00", response.context["voos"][1]["trajeto_hint"])
        self.assertIn("Fuso -1h", response.context["voos"][1]["trajeto_hint"])
        self.assertContains(
            response,
            '<span class="emission-preview-flight-card__tag">Ida</span>',
            html=True,
        )
        self.assertContains(
            response,
            '<span class="emission-preview-flight-card__tag">Volta</span>',
            html=True,
        )
        self.assertNotContains(response, "Horario da volta")

    def test_visualizacao_de_cotacao_nao_exibe_cpf_tecnico(self):
        cliente_sem_cpf_real_user = User.objects.create_user(
            username="cliente-sem-cpf-preview",
            password="secret",
        )
        cliente_sem_cpf_real = Cliente.objects.create(
            usuario=cliente_sem_cpf_real_user,
            cpf="91234567890",
            perfil="cliente",
            ativo=True,
        )
        cotacao = CotacaoVoo.objects.create(
            cliente=cliente_sem_cpf_real,
            companhia_aerea=self.companhia.nome,
            origem=self.origem,
            destino=self.destino,
            data_ida=self.data_ida,
            programa=self.programa,
            qtd_passageiros=1,
            classe="Economica",
            observacoes="Cotacao com CPF tecnico",
            valor_passagem=Decimal("2500.00"),
            taxas=Decimal("150.00"),
            milhas=0,
            valor_milheiro=Decimal("0.00"),
            parcelas=1,
            juros=Decimal("1.00"),
            desconto=Decimal("1.00"),
            validade=self.validade,
            status="pendente",
        )

        response = self.client.get(reverse("admin_visualizar_cotacao_voo", args=[cotacao.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["titular_info"]["cpf"], "")
        self.assertNotContains(response, "91234567890")

    def test_visualizacao_de_cotacao_pode_ocultar_opcao_parcelada(self):
        cotacao = CotacaoVoo.objects.create(
            cliente=self.cliente,
            companhia_aerea=self.companhia.nome,
            origem=self.origem,
            destino=self.destino,
            data_ida=self.data_ida,
            programa=self.programa,
            qtd_passageiros=1,
            classe="Economica",
            observacoes="Cotacao sem parcelado",
            valor_passagem=Decimal("2500.00"),
            taxas=Decimal("150.00"),
            milhas=20000,
            valor_milheiro=Decimal("35.00"),
            parcelas=6,
            juros=Decimal("1.10"),
            desconto=Decimal("1.00"),
            mostrar_valor_parcelado=False,
            validade=self.validade,
            status="pendente",
        )

        response = self.client.get(reverse("admin_visualizar_cotacao_voo", args=[cotacao.id]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["mostrar_valor_parcelado"])
        self.assertNotContains(response, "Valor Parcelado")


@override_settings(
    TELEGRAM_ALERTS_BOT_TOKEN="dummy-token",
    TELEGRAM_ALERTS_WEBHOOK_SECRET="segredo-alertas",
    TELEGRAM_ALERTS_ALLOWED_CHAT_IDS=["-100123456"],
)
class TelegramAlertasWebhookTest(TestCase):
    def setUp(self):
        Aeroporto.objects.create(sigla="GRU", nome="Guarulhos", cidade="Sao Paulo", estado="SP")
        Aeroporto.objects.create(
            sigla="RAO",
            nome="Ribeirao Preto (Leite Lopes)",
            cidade="Ribeirao Preto (Leite Lopes)",
            estado="N/A",
        )
        self.payload_text = (
            "Ribeirão Preto (RAO) 3.928 Milhas + taxas\n"
            "Econômica\n\n"
            "Programa LatamPass\n"
            "Custo trecho: 3.928 milhas + taxas\n"
            "Classe Econômica\n"
            "Voando Latam\n\n"
            "São Paulo (GRU) > Ribeirão Preto (RAO)\n\n"
            ":date: Disponibilidade de Ida\n"
            "Jun/26:`01,02,03,04,05,06`\n\n"
            "Ribeirão Preto (RAO) > São Paulo (GRU)\n\n"
            ":date: Disponibilidade de Volta\n"
            "Jun/26:`03,04,05,06,07,09,11`\n\n"
            "Pesquisar ida e volta para achar esses valores."
        )

    def _build_payload(self, update_id=501):
        return {
            "update_id": update_id,
            "channel_post": {
                "message_id": 77,
                "date": 1775070000,
                "chat": {
                    "id": -100123456,
                    "title": "Alertas Milhas",
                    "type": "channel",
                },
                "text": self.payload_text,
            },
        }

    def test_webhook_cadastra_alerta_automaticamente(self):
        response = self.client.post(
            reverse("telegram_alertas_webhook"),
            data=json.dumps(self._build_payload()),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="segredo-alertas",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AlertaViagem.objects.count(), 1)
        self.assertEqual(TelegramAlertaEvento.objects.count(), 1)

        alerta = AlertaViagem.objects.get()
        self.assertEqual(alerta.origem, "GRU")
        self.assertEqual(alerta.destino, "RAO")
        self.assertEqual(alerta.programa_fidelidade, "LatamPass")
        self.assertEqual(alerta.pais, "Brasil")
        self.assertEqual(alerta.continente, "América do Sul")
        self.assertEqual(alerta.valor_milhas, 3928)

    @patch("gestao.views.alertas.telegram_send_message")
    def test_webhook_envia_confirmacao_no_bot_quando_alerta_sobe(self, mock_send_message):
        response = self.client.post(
            reverse("telegram_alertas_webhook"),
            data=json.dumps(self._build_payload(update_id=502)),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="segredo-alertas",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send_message.called)
        sent_chat_id, sent_text = mock_send_message.call_args.args
        self.assertEqual(sent_chat_id, -100123456)
        self.assertIn("Alerta publicado com sucesso.", sent_text)
        self.assertIn("Ver no site:", sent_text)

    @patch("gestao.views.alertas.telegram_send_message")
    def test_webhook_envia_erro_claro_no_bot_quando_nao_consegue_interpretar(self, mock_send_message):
        payload = self._build_payload(update_id=503)
        payload["channel_post"]["text"] = "oi"

        response = self.client.post(
            reverse("telegram_alertas_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="segredo-alertas",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send_message.called)
        sent_chat_id, sent_text = mock_send_message.call_args.args
        self.assertEqual(sent_chat_id, -100123456)
        self.assertIn("Nao consegui interpretar o alerta.", sent_text)

    def test_webhook_nao_duplica_mesmo_update(self):
        payload = self._build_payload(update_id=777)
        headers = {
            "content_type": "application/json",
            "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": "segredo-alertas",
        }

        first = self.client.post(reverse("telegram_alertas_webhook"), data=json.dumps(payload), **headers)
        second = self.client.post(reverse("telegram_alertas_webhook"), data=json.dumps(payload), **headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(AlertaViagem.objects.count(), 1)
        self.assertEqual(TelegramAlertaEvento.objects.count(), 1)

    def test_webhook_mesmo_alerta_atualiza_datas_e_nao_cria_novo_card(self):
        from gestao.services.telegram_alertas import process_telegram_alert_update

        first_payload = self._build_payload(update_id=900)
        second_payload = self._build_payload(update_id=901)
        second_payload["channel_post"]["text"] = (
            "RibeirÃ£o Preto (RAO) 4.100 Milhas + taxas\n"
            "EconÃ´mica\n\n"
            "Programa LatamPass\n"
            "Custo trecho: 4.100 milhas + taxas\n"
            "Classe EconÃ´mica\n"
            "Voando Latam\n\n"
            "SÃ£o Paulo (GRU) > RibeirÃ£o Preto (RAO)\n\n"
            ":date: Disponibilidade de Ida\n"
            "Jun/26:`01,02,03,04,05,06,08`\n\n"
            "RibeirÃ£o Preto (RAO) > SÃ£o Paulo (GRU)\n\n"
            ":date: Disponibilidade de Volta\n"
            "Jun/26:`03,04,05,06,07,09,11,12`\n\n"
            "Pesquisar ida e volta para achar esses valores."
        )
        _, first_outcome = process_telegram_alert_update(first_payload)
        alerta = AlertaViagem.objects.get()
        old_created_at = timezone.now() - timedelta(days=3)
        AlertaViagem.objects.filter(id=alerta.id).update(criado_em=old_created_at)

        _, second_outcome = process_telegram_alert_update(second_payload)

        self.assertEqual(first_outcome, "created")
        self.assertEqual(second_outcome, "updated")
        self.assertEqual(AlertaViagem.objects.count(), 1)

        alerta.refresh_from_db()
        self.assertEqual(alerta.valor_milhas, 4100)
        self.assertIn("2026-06-08", alerta.datas_ida)
        self.assertIn("2026-06-12", alerta.datas_volta)
        self.assertGreater(alerta.criado_em, old_created_at)

    def test_webhook_mesma_mensagem_republicada_atualiza_data_do_alerta(self):
        from gestao.services.telegram_alertas import process_telegram_alert_update

        first_payload = self._build_payload(update_id=910)
        second_payload = self._build_payload(update_id=911)

        _, first_outcome = process_telegram_alert_update(first_payload)
        alerta = AlertaViagem.objects.get()
        old_created_at = timezone.now() - timedelta(days=2)
        AlertaViagem.objects.filter(id=alerta.id).update(criado_em=old_created_at)

        _, second_outcome = process_telegram_alert_update(second_payload)

        self.assertEqual(first_outcome, "created")
        self.assertEqual(second_outcome, "updated")
        self.assertEqual(AlertaViagem.objects.count(), 1)

        alerta.refresh_from_db()
        self.assertGreater(alerta.criado_em, old_created_at)


@override_settings(
    TELEGRAM_NEWS_BOT_TOKEN="dummy-news-token",
    TELEGRAM_NEWS_ALLOWED_CHAT_IDS=["-100123456"],
)
class TelegramNoticiasServiceTest(TestCase):
    def setUp(self):
        self.fonte = Fonte.objects.create(
            nome="Fonte Telegram Noticias",
            url="https://example.com/",
            tipo_coleta="html",
        )
        self.materia = MateriaBruta.objects.create(
            fonte=self.fonte,
            url_original="https://example.com/noticia",
            titulo_extraido="Titulo base",
            texto_base="Texto base de noticia suficiente para testes.",
            hash_conteudo="hash-noticia-1",
        )
        self.noticia = NoticiaPublicada.objects.create(
            materia_bruta=self.materia,
            fonte=self.fonte,
            titulo="Noticia do teste",
            resumo="Resumo do teste",
            conteudo="Conteudo do teste",
            slug="noticia-do-teste",
            categoria="Promocoes",
            topico="Ofertas",
            url_fonte="https://example.com/noticia",
            status="published",
        )

    def _build_payload(self, text, update_id=9001):
        return {
            "update_id": update_id,
            "message": {
                "message_id": 55,
                "date": 1775070000,
                "chat": {
                    "id": -100123456,
                    "title": "Noticias NC Fly",
                    "type": "supergroup",
                },
                "text": text,
            },
        }

    def test_parse_single_news_url_command_aceita_link_puro_e_embutido(self):
        from gestao.services.telegram_noticias import parse_single_news_url_command

        url = "https://www.cartoesdecredito.me/cartoes/btg-tap-black-oferece-ate-2-anos-de-anuidade-gratis/"
        self.assertEqual(parse_single_news_url_command(url), url)
        self.assertEqual(parse_single_news_url_command(f"noticia {url}"), url)
        self.assertEqual(parse_single_news_url_command(f"Veja isso aqui {url} agora"), url)

    def test_parse_single_news_url_command_ignora_url_embutida_em_texto_promocional_longo(self):
        from gestao.services.telegram_noticias import parse_single_news_url_command

        text = (
            "TEM PROMOCODE NOVO NO AR NESTE MES DE ANIVERSARIO DA AZUL VIAGENS. "
            "FESTA10 com 10% OFF em pacote aereo e hotel. "
            "Tipo de produto: Aereo Azul, Aereo Amadeus, Hotel, Passeio, Traslado. "
            "Data de venda: 08/04/2026 a 21/04/2026. "
            "Data de viagem: 09/04/2026 a 27/06/2027. "
            "Regra juridica com condicoes completas da campanha em http://azulviagens.com.br/termos-e-condicoes."
        )

        self.assertIsNone(parse_single_news_url_command(text))

    def test_looks_like_manual_news_text_detecta_texto_promocional(self):
        from gestao.services.telegram_noticias import looks_like_manual_news_text

        self.assertTrue(
            looks_like_manual_news_text(
                "TEM PROMOCODE NOVO NO AR. FESTA10 com 10% OFF. "
                "Tipo de produto: Aereo Azul e Hotel. "
                "Data de venda: 08/04/2026 a 21/04/2026. "
                "Data de viagem: 09/04/2026 a 27/06/2027. "
                "Regra juridica com condicoes detalhadas."
            )
        )

    def test_looks_like_manual_news_text_ignora_bom_invisivel(self):
        from gestao.services.telegram_noticias import looks_like_manual_news_text

        self.assertTrue(
            looks_like_manual_news_text(
                "TEM PROMOCODE NOVO NO AR. FESTA10 com 10% OFF. "
                "Tipo de produto: Aereo Azul e Hotel. "
                "Data de venda: 08/04/2026 a 21/04/2026. "
                "Data de viagem: 09/04/2026 a 27/06/2027. "
                "Regra juridica com condicoes detalhadas. "
                "http://azulviagens.com.br/termos-e-condicoes\ufeff"
            )
        )

    @patch("portal.views.invalidate_news_cache")
    @patch("portal.services.news_sync_service.sync_news_from_url")
    def test_process_news_update_com_link(self, mock_sync_news_from_url, _mock_invalidate_news_cache):
        from gestao.services.telegram_noticias import process_telegram_news_update

        mock_sync_news_from_url.return_value = {
            "outcome": "published",
            "noticia": self.noticia,
            "processed": 1,
            "published": 1,
        }

        event, outcome, meta = process_telegram_news_update(
            self._build_payload("https://example.com/noticia-do-dia", update_id=9002)
        )

        self.assertEqual(outcome, "url_published")
        self.assertEqual(event.status, TelegramNoticiaEvento.STATUS_PROCESSADO)
        self.assertEqual(event.noticia_id, self.noticia.id)
        self.assertIn("Noticia publicada.", meta["message"])

    @patch("portal.views.invalidate_news_cache")
    @patch("portal.services.news_sync_service.sync_news_from_text")
    def test_process_news_update_com_texto_promocional(self, mock_sync_news_from_text, _mock_invalidate_news_cache):
        from gestao.services.telegram_noticias import process_telegram_news_update

        mock_sync_news_from_text.return_value = {
            "outcome": "published",
            "noticia": self.noticia,
            "processed": 1,
            "published": 1,
        }

        event, outcome, meta = process_telegram_news_update(
            self._build_payload(
                "TEM PROMOCODE NOVO NO AR NESTE MES DE ANIVERSARIO DA AZUL VIAGENS. "
                "FESTA10 com 10% OFF em pacote aereo e hotel. "
                "Tipo de produto: Aereo Azul, Hotel. "
                "Data de venda: 08/04/2026 a 21/04/2026. "
                "Data de viagem: 09/04/2026 a 27/06/2027. "
                "Regra juridica com condicoes completas da campanha.",
                update_id=9003,
            )
        )

        self.assertEqual(outcome, "text_published")
        self.assertEqual(event.status, TelegramNoticiaEvento.STATUS_PROCESSADO)
        self.assertEqual(event.noticia_id, self.noticia.id)
        self.assertIn("Noticia publicada.", meta["message"])

    @patch("portal.views.invalidate_news_cache")
    @patch("portal.services.news_sync_service.sync_news_progressive")
    def test_process_news_update_com_atualizar(self, mock_sync_news_progressive, _mock_invalidate_news_cache):
        from gestao.services.telegram_noticias import process_telegram_news_update

        mock_sync_news_progressive.return_value = (4, 2, [])

        event, outcome, meta = process_telegram_news_update(
            self._build_payload("atualizar 4", update_id=9004)
        )

        self.assertEqual(outcome, "sync_batch")
        self.assertEqual(event.status, TelegramNoticiaEvento.STATUS_PROCESSADO)
        self.assertIn("Sync concluido: 4 processadas, 2 publicadas.", meta["message"])


class AlertaViagemVitrineTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(username="alertadmin", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        Cliente.objects.create(
            usuario=self.admin_user,
            cpf="12345678901",
            perfil="admin",
            ativo=True,
        )
        self.assertTrue(self.client.login(username="alertadmin", password="secret"))

    def _create_alerta(self, **overrides):
        payload = {
            "titulo": "Alerta teste vitrine",
            "conteudo": "Conteudo do alerta",
            "continente": "AmÃ©rica do Sul",
            "pais": "Brasil",
            "cidade_destino": "Cidade Teste Alertas",
            "origem": "GRU",
            "destino": "RAO",
            "classe": "economica",
            "programa_fidelidade": "LatamPass",
            "companhia_aerea": "Latam",
            "valor_milhas": 3928,
            "datas_ida": ["2026-06-01"],
            "datas_volta": ["2026-06-03"],
            "ativo": True,
        }
        payload.update(overrides)
        alerta = AlertaViagem.objects.create(**payload)
        return alerta

    def _set_created_days_ago(self, alerta, days):
        created_at = timezone.now() - timedelta(days=days)
        AlertaViagem.objects.filter(id=alerta.id).update(criado_em=created_at)
        alerta.refresh_from_db()
        return alerta

    def _vitrine_response(self, cidade):
        return self.client.get(
            reverse("alertas_passagens"),
            {
                "continente": "AmÃ©rica do Sul",
                "pais": "Brasil",
                "cidade": cidade,
            },
        )

    def test_alerta_padrao_some_apos_cinco_dias(self):
        alerta = self._create_alerta(
            titulo="Alerta padrao vencido",
            cidade_destino="Cidade Vencida",
        )
        self._set_created_days_ago(alerta, 6)

        response = self._vitrine_response(alerta.cidade_destino)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["alertas"].values_list("id", flat=True)), [])

    def test_alerta_pode_continuar_apos_cinco_dias(self):
        alerta = self._create_alerta(
            titulo="Alerta continua",
            manter_apos_cinco_dias=True,
            cidade_destino="Cidade Continua",
        )
        self._set_created_days_ago(alerta, 8)

        response = self._vitrine_response(alerta.cidade_destino)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["alertas"].values_list("id", flat=True)), [alerta.id])

    def test_alerta_some_quando_todas_as_datas_passarem(self):
        alerta = self._create_alerta(
            titulo="Alerta por datas",
            ocultar_apos_datas=True,
            datas_ida=["2026-01-01"],
            datas_volta=["2026-01-02"],
            cidade_destino="Cidade Datas",
        )
        self._set_created_days_ago(alerta, 1)

        response = self._vitrine_response(alerta.cidade_destino)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["alertas"].values_list("id", flat=True)), [])

    def test_alerta_detalhe_vencido_retorna_404(self):
        alerta = self._create_alerta(
            titulo="Alerta detalhe vencido",
            ocultar_apos_datas=True,
            datas_ida=["2026-01-01"],
            datas_volta=["2026-01-02"],
        )
        self._set_created_days_ago(alerta, 1)

        response = self.client.get(reverse("alerta_passagem_detalhe", args=[alerta.id]))

        self.assertEqual(response.status_code, 404)


class AdminAlertasRegrasExibicaoTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="super-alerta",
            email="super@example.com",
            password="secret",
        )
        self.assertTrue(self.client.login(username="super-alerta", password="secret"))

    def test_checkbox_na_gerencia_atualiza_regras(self):
        alerta = AlertaViagem.objects.create(
            titulo="Alerta gerencia",
            conteudo="Conteudo",
            continente="AmÃ©rica do Sul",
            pais="Brasil",
            cidade_destino="Sao Paulo",
            origem="GRU",
            destino="RAO",
            classe="economica",
            programa_fidelidade="LatamPass",
            companhia_aerea="LATAM",
            ativo=True,
        )

        response = self.client.post(
            reverse("admin_alertas_passagens"),
            {
                "alerta_id": alerta.id,
                "manter_apos_cinco_dias": "on",
                "ocultar_apos_datas": "on",
                "next": reverse("admin_alertas_passagens"),
            },
        )

        self.assertEqual(response.status_code, 302)
        alerta.refresh_from_db()
        self.assertTrue(alerta.manter_apos_cinco_dias)
        self.assertTrue(alerta.ocultar_apos_datas)


class InteresseViagemMatchTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cliente-match", password="secret")
        self.empresa = Empresa.objects.create(
            nome="Empresa Match",
            limite_colaboradores=5,
        )
        self.cliente = Cliente.objects.create(
            usuario=self.user,
            empresa=self.empresa,
            cpf="98765432100",
            perfil="cliente",
            ativo=True,
        )

    def test_sync_cria_match_por_destino_e_mes(self):
        interesse = InteresseViagemCliente.objects.create(
            cliente=self.cliente,
            continente="Europa",
            cidade_destino="Roma",
            classe="economica",
            meses_ida=[9],
            ativo=True,
        )
        alerta = AlertaViagem.objects.create(
            titulo="Roma em setembro",
            conteudo="Oferta para Roma",
            continente="Europa",
            pais="Italia",
            cidade_destino="Roma",
            origem="GRU",
            destino="FCO",
            classe="economica",
            programa_fidelidade="LatamPass",
            companhia_aerea="LATAM",
            datas_ida=["2026-09-10"],
            datas_volta=["2026-09-21"],
            ativo=True,
            manter_apos_cinco_dias=True,
        )

        sync_alerta_interest_matches(alerta)

        self.assertEqual(InteresseViagemMatch.objects.count(), 1)
        match = InteresseViagemMatch.objects.get()
        self.assertEqual(match.interesse, interesse)
        self.assertEqual(match.alerta, alerta)

    def test_sync_nao_cria_match_quando_mes_nao_bate(self):
        InteresseViagemCliente.objects.create(
            cliente=self.cliente,
            continente="Europa",
            cidade_destino="Roma",
            meses_ida=[9],
            ativo=True,
        )
        alerta = AlertaViagem.objects.create(
            titulo="Roma em outubro",
            conteudo="Oferta para Roma",
            continente="Europa",
            pais="Italia",
            cidade_destino="Roma",
            origem="GRU",
            destino="FCO",
            classe="economica",
            programa_fidelidade="LatamPass",
            companhia_aerea="LATAM",
            datas_ida=["2026-10-10"],
            datas_volta=["2026-10-21"],
            ativo=True,
            manter_apos_cinco_dias=True,
        )

        sync_alerta_interest_matches(alerta)

        self.assertEqual(InteresseViagemMatch.objects.count(), 0)


class AdminCompanyScopeTest(TestCase):
    def setUp(self):
        self.empresa_a = Empresa.objects.create(nome="Empresa A")
        self.empresa_b = Empresa.objects.create(nome="Empresa B")

        self.admin_user = User.objects.create_user(username="admin-empresa-a", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        Cliente.objects.create(
            usuario=self.admin_user,
            cpf="90123456789",
            perfil="admin",
            ativo=True,
            empresa=self.empresa_a,
        )

        self.client_user_b = User.objects.create_user(username="cliente-empresa-b", password="secret")
        self.cliente_b = Cliente.objects.create(
            usuario=self.client_user_b,
            cpf="10987654321",
            perfil="cliente",
            ativo=True,
            empresa=self.empresa_b,
        )
        self.cliente = self.cliente_b

        self.programa = ProgramaFidelidade.objects.create(nome="Programa Scope")
        self.aeroporto_origem = Aeroporto.objects.create(nome="Guarulhos", sigla="GRU", cidade="Sao Paulo")
        self.aeroporto_destino = Aeroporto.objects.create(nome="Congonhas", sigla="CGH", cidade="Sao Paulo")

        self.conta_b = ContaFidelidade.objects.create(cliente=self.cliente_b, programa=self.programa)
        self.cotacao_b = CotacaoVoo.objects.create(
            cliente=self.cliente_b,
            origem=self.aeroporto_origem,
            destino=self.aeroporto_destino,
            data_ida=timezone.now() + timedelta(days=10),
            programa=self.programa,
            qtd_passageiros=1,
            classe="Economica",
            valor_passagem=Decimal("1200.00"),
            taxas=Decimal("50.00"),
            milhas=10000,
            valor_milheiro=Decimal("30.00"),
        )
        self.emissao_b = EmissaoPassagem.objects.create(
            cliente=self.cliente_b,
            programa=self.programa,
            aeroporto_partida=self.aeroporto_origem,
            aeroporto_destino=self.aeroporto_destino,
            data_ida=timezone.now() + timedelta(days=15),
            valor_referencia=Decimal("1300.00"),
            valor_taxas=Decimal("60.00"),
        )

    def test_admin_nao_visualiza_cliente_de_outra_empresa(self):
        self.assertTrue(self.client.login(username="admin-empresa-a", password="secret"))
        response = self.client.get(reverse("admin_visualizar_cliente", args=[self.cliente_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_admin_nao_edita_conta_de_outra_empresa(self):
        self.assertTrue(self.client.login(username="admin-empresa-a", password="secret"))
        response = self.client.get(reverse("admin_editar_conta", args=[self.conta_b.id]))
        self.assertTemplateUsed(response, "sem_permissao.html")

    def test_admin_nao_visualiza_cotacao_de_outra_empresa(self):
        self.assertTrue(self.client.login(username="admin-empresa-a", password="secret"))
        response = self.client.get(reverse("admin_visualizar_cotacao_voo", args=[self.cotacao_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_admin_nao_visualiza_emissao_de_outra_empresa(self):
        self.assertTrue(self.client.login(username="admin-empresa-a", password="secret"))
        response = self.client.get(reverse("admin_emissao_detalhe", args=[self.emissao_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_listagens_filtram_dados_de_outra_empresa(self):
        self.assertTrue(self.client.login(username="admin-empresa-a", password="secret"))
        clientes_response = self.client.get(reverse("admin_clientes"))
        contas_response = self.client.get(reverse("admin_contas"))
        cotacoes_response = self.client.get(reverse("admin_cotacoes_voo"))
        emissoes_response = self.client.get(reverse("admin_emissoes"))

        self.assertNotContains(clientes_response, self.client_user_b.username)
        self.assertNotContains(contas_response, self.programa.nome)
        self.assertNotContains(cotacoes_response, self.cotacao_b.classe)
        self.assertNotContains(emissoes_response, self.programa.nome)

    def test_sync_cria_match_por_dia_e_semestre(self):
        InteresseViagemCliente.objects.create(
            cliente=self.cliente,
            destino="MIA",
            dias_ida=[15],
            semestres_ida=[2],
            ativo=True,
        )
        alerta = AlertaViagem.objects.create(
            titulo="Miami em julho",
            conteudo="Oferta para Miami",
            continente="AmÃƒÂ©rica do Norte",
            pais="Estados Unidos",
            cidade_destino="Miami",
            origem="GRU",
            destino="MIA",
            classe="economica",
            programa_fidelidade="LatamPass",
            companhia_aerea="LATAM",
            datas_ida=["2026-07-15"],
            ativo=True,
            manter_apos_cinco_dias=True,
        )

        sync_alerta_interest_matches(alerta)

        self.assertEqual(InteresseViagemMatch.objects.count(), 1)

    def test_sync_nao_cria_match_quando_dia_nao_bate(self):
        InteresseViagemCliente.objects.create(
            cliente=self.cliente,
            destino="MIA",
            dias_ida=[16],
            semestres_ida=[2],
            ativo=True,
        )
        alerta = AlertaViagem.objects.create(
            titulo="Miami em julho",
            conteudo="Oferta para Miami",
            continente="AmÃƒÂ©rica do Norte",
            pais="Estados Unidos",
            cidade_destino="Miami",
            origem="GRU",
            destino="MIA",
            classe="economica",
            programa_fidelidade="LatamPass",
            companhia_aerea="LATAM",
            datas_ida=["2026-07-15"],
            ativo=True,
            manter_apos_cinco_dias=True,
        )

        sync_alerta_interest_matches(alerta)

        self.assertEqual(InteresseViagemMatch.objects.count(), 0)


class EmissaoFrontendPrivacyTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Privacidade", limite_colaboradores=5)
        self.admin_user = User.objects.create_user(username="admin-privacidade", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        Cliente.objects.create(
            usuario=self.admin_user,
            empresa=self.empresa,
            cpf="11122233344",
            perfil="admin",
            ativo=True,
        )

        self.client_user = User.objects.create_user(
            username="cliente-privacidade",
            first_name="Cliente",
            last_name="Privado",
            password="secret",
        )
        self.cliente = Cliente.objects.create(
            usuario=self.client_user,
            empresa=self.empresa,
            cpf="98765432100",
            perfil="cliente",
            ativo=True,
        )
        self.programa = ProgramaFidelidade.objects.create(nome="Programa Privado")
        ContaFidelidade.objects.create(
            cliente=self.cliente,
            programa=self.programa,
            quantidade_cpfs_disponiveis=2,
        )
        self.passageiro = PassageiroFrequente.objects.create(
            cliente=self.cliente,
            nome="Passageiro Frequente",
            cpf="12312312312",
            rg="RG-SEGREDO",
            passaporte="XPTO1234",
        )
        self.assertTrue(self.client.login(username="admin-privacidade", password="secret"))

    def test_formulario_emissao_nao_embute_documentos_de_passageiros_no_html(self):
        response = self.client.get(reverse("admin_nova_emissao"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.passageiro.cpf)
        self.assertNotContains(response, self.passageiro.rg)
        self.assertNotContains(response, self.passageiro.passaporte)
        self.assertNotContains(response, self.cliente.cpf)

    def test_contexto_cliente_e_detalhe_passageiro_sao_carregados_sob_demanda(self):
        cliente_response = self.client.get(reverse("admin_emissao_cliente_contexto", args=[self.cliente.id]))
        passageiro_response = self.client.get(reverse("admin_emissao_passageiro_frequente_detalhe", args=[self.passageiro.id]))

        self.assertEqual(cliente_response.status_code, 200)
        self.assertEqual(passageiro_response.status_code, 200)
        self.assertJSONEqual(
            cliente_response.content,
            {
                "cliente": {
                    "id": self.cliente.id,
                    "nome": "Cliente Privado",
                    "cpf": self.cliente.cpf,
                },
                "passageiros_frequentes": [
                    {
                        "id": self.passageiro.id,
                        "nome": self.passageiro.nome,
                        "cpf_masked": "123.***.***-12",
                    }
                ],
            },
        )
        self.assertJSONEqual(
            passageiro_response.content,
            {
                "id": self.passageiro.id,
                "nome": self.passageiro.nome,
                "cpf": self.passageiro.cpf,
                "rg": self.passageiro.rg,
                "passaporte": self.passageiro.passaporte,
                "passaporte_validade": "",
                "data_nascimento": "",
            },
        )


class CadastroMinimoClienteECotacaoOpcionalTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Cadastro", limite_colaboradores=5)
        self.admin_user = User.objects.create_user(username="admin-cadastro", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        Cliente.objects.create(
            usuario=self.admin_user,
            empresa=self.empresa,
            cpf="12312312399",
            perfil="admin",
            ativo=True,
        )
        self.user_cliente = User.objects.create_user(username="cliente-cotacao", password="secret")
        self.cliente = Cliente.objects.create(
            usuario=self.user_cliente,
            empresa=self.empresa,
            cpf="22233344455",
            perfil="cliente",
            ativo=True,
        )
        self.origem = Aeroporto.objects.create(sigla="GRU", nome="Guarulhos", cidade="Sao Paulo", estado="SP")
        self.destino = Aeroporto.objects.create(sigla="RAO", nome="Leite Lopes", cidade="Ribeirao Preto", estado="SP")
        self.programa = ProgramaFidelidade.objects.create(nome="Programa Opcional")
        self.assertTrue(self.client.login(username="admin-cadastro", password="secret"))

    def test_novo_cliente_form_aceita_nome_e_sobrenome_como_minimo(self):
        form = NovoClienteForm(
            data={
                "first_name": "Pedro",
                "last_name": "Pires",
                "email": "",
                "telefone": "",
                "data_nascimento": "",
                "cpf": "",
                "password": "",
                "confirm_password": "",
                "observacoes": "",
                "ativo": "on",
                "perfil": "cliente",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["cpf"]), 11)

    def test_criar_cliente_aceita_cadastro_minimo(self):
        response = self.client.post(
            reverse("admin_novo_cliente"),
            {
                "first_name": "Maria",
                "last_name": "Silva",
                "email": "",
                "telefone": "",
                "data_nascimento": "",
                "cpf": "",
                "password": "",
                "confirm_password": "",
                "observacoes": "",
                "ativo": "on",
                "perfil": "cliente",
            },
        )

        self.assertEqual(response.status_code, 302)
        novo_cliente = Cliente.objects.exclude(usuario=self.admin_user).get(usuario__first_name="Maria", usuario__last_name="Silva")
        self.assertEqual(novo_cliente.empresa, self.empresa)
        self.assertEqual(len(novo_cliente.cpf), 11)

    def test_cotacao_form_aceita_programa_vazio(self):
        form = CotacaoVooForm(
            data={
                "tipo_titular": "cliente",
                "cliente": str(self.cliente.id),
                "conta_administrada": "",
                "companhia_aerea": "",
                "origem": str(self.origem.id),
                "destino": str(self.destino.id),
                "programa": "",
                "data_ida": "2026-04-10T10:00",
                "data_volta": "",
                "qtd_passageiros": "1",
                "classe": "Economica",
                "observacoes": "",
                "valor_passagem": "1500.00",
                "taxas": "100.00",
                "milhas": "0",
                "valor_milheiro": "0",
                "parcelas": "1",
                "juros": "1.00",
                "desconto": "1.00",
                "validade": "2026-04-12",
                "status": "pendente",
            },
            empresa=self.empresa,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["programa"])


class AdminNotificationReadStateTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Notificacoes")
        self.admin_user = User.objects.create_user(username="admin-notificacoes", password="secret")
        self.admin_user.is_staff = True
        self.admin_user.save(update_fields=["is_staff"])
        Cliente.objects.create(
            usuario=self.admin_user,
            empresa=self.empresa,
            cpf="55566677710",
            perfil="admin",
            ativo=True,
        )

        self.cliente_user = User.objects.create_user(username="cliente-notificacoes", password="secret")
        self.cliente = Cliente.objects.create(
            usuario=self.cliente_user,
            empresa=self.empresa,
            cpf="55566677711",
            perfil="cliente",
            ativo=True,
        )
        self.origem = Aeroporto.objects.create(sigla="GRU", nome="Guarulhos", cidade="Sao Paulo")
        self.destino = Aeroporto.objects.create(sigla="MIA", nome="Miami", cidade="Miami")
        self.assertTrue(self.client.login(username="admin-notificacoes", password="secret"))

        self.cotacao = CotacaoVoo.objects.create(
            cliente=self.cliente,
            origem=self.origem,
            destino=self.destino,
            data_ida=timezone.now() + timedelta(days=10),
            validade=timezone.localdate() + timedelta(days=1),
            qtd_passageiros=1,
            classe="Economica",
            valor_passagem=Decimal("3500.00"),
            taxas=Decimal("180.00"),
            milhas=0,
            valor_milheiro=Decimal("0.00"),
        )

    def test_marcar_notificacao_lida_remove_item_das_proximas_listagens(self):
        notifications = build_operational_notifications(
            user=self.admin_user,
            empresa=self.empresa,
            limit=6,
        )
        target = next(item for item in notifications if item["title"] == "Cotacao vencendo")

        response = self.client.post(
            reverse("admin_marcar_notificacao_lida"),
            data=json.dumps({"key": target["key"]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            NotificacaoSistema.objects.filter(
                usuario=self.admin_user,
                empresa=self.empresa,
                chave=target["key"],
                lida=True,
            ).exists()
        )

        remaining = build_operational_notifications(
            user=self.admin_user,
            empresa=self.empresa,
            limit=6,
        )
        self.assertFalse(any(item["key"] == target["key"] for item in remaining))

    def test_marcar_notificacao_lida_rejeita_chave_invalida(self):
        response = self.client.post(
            reverse("admin_marcar_notificacao_lida"),
            data=json.dumps({"key": "nao-existe"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
