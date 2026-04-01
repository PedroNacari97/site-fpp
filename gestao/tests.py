from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from gestao.forms import ProgramaFidelidadeForm
from gestao.models import (
    Aeroporto,
    Cliente,
    CompanhiaAerea,
    ContaFidelidade,
    CotacaoVoo,
    EmissaoPassagem,
    Movimentacao,
    ProgramaFidelidade,
)

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
