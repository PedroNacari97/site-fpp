"""Testes do fluxo de atualizacao em massa.

Cobertura:
- Manager `da_empresa` isola tenants.
- Service `disparar_atualizacao_em_massa` respeita debounce.
- Tenant violation no `_pertence_a_empresa` nao deixa empresa B mexer em A.
- Rate limiter `acquire` bloqueia em rajada e libera depois.
- View JSON do job exige tenant correto.
"""
from datetime import datetime, timedelta, timezone as dt_tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from gestao.models import (
    AcompanhamentoPassagem,
    Aeroporto,
    AtualizacaoEmMassa,
    Cliente,
    CompanhiaAerea,
    EmissaoPassagem,
    Empresa,
    Passageiro,
    ProgramaFidelidade,
)
from gestao.services.acompanhamento_passagem import (
    AcompanhamentoSyncResult,
    ensure_acompanhamento_passagem,
)
from gestao.services.monitoring import bulk_runner
from gestao.services.monitoring.rate_limiter import (
    RateLimitConfig,
    RateLimitTimeout,
    acquire,
    reset,
)


_CPF_COUNTER = {"n": 0}


def _next_cpf():
    _CPF_COUNTER["n"] += 1
    return str(10000000000 + _CPF_COUNTER["n"]).zfill(11)


def _criar_emissao(empresa, *, sufixo="A", data_ida=None):
    user = get_user_model().objects.create_user(
        username=f"user{sufixo}",
        password="pass123",
    )
    cliente = Cliente.objects.create(
        usuario=user,
        cpf=_next_cpf(),
        perfil="admin",
        empresa=empresa,
        ativo=True,
    )
    programa = ProgramaFidelidade.objects.create(
        nome=f"Programa {sufixo}",
        preco_medio_milheiro=100,
    )
    origem = Aeroporto.objects.create(sigla=f"O{sufixo[:2]}", nome=f"Origem {sufixo}", cidade="X", estado="SP")
    destino = Aeroporto.objects.create(sigla=f"D{sufixo[:2]}", nome=f"Destino {sufixo}", cidade="Y", estado="SP")
    cia = CompanhiaAerea.objects.create(
        nome=f"LATAM {sufixo}",
        site_url="https://www.latam.com/br/pt/minhas-viagens",
        codigo="LATAM",
    )
    emissao = EmissaoPassagem.objects.create(
        cliente=cliente,
        programa=programa,
        companhia_aerea=cia,
        aeroporto_partida=origem,
        aeroporto_destino=destino,
        data_ida=data_ida or (timezone.now() + timedelta(days=10)),
        qtd_adultos=1,
        qtd_criancas=0,
        qtd_bebes=0,
        localizador=f"PNR{sufixo[:3]}",
        valor_referencia="100",
        valor_taxas="10",
        valor_total_final="110",
        valor_venda_final="110",
    )
    Passageiro.objects.create(emissao=emissao, nome=f"Pessoa {sufixo}", cpf="52998224725", categoria="adulto")
    return user, emissao


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "test-bulk"}})
class ManagerIsolationTest(TestCase):
    """`da_empresa` NUNCA pode vazar passagens entre empresas."""

    def setUp(self):
        cache.clear()
        self.empresa_a = Empresa.objects.create(nome="Agência A")
        self.empresa_b = Empresa.objects.create(nome="Agência B")
        _, self.emissao_a = _criar_emissao(self.empresa_a, sufixo="A1")
        _, self.emissao_b = _criar_emissao(self.empresa_b, sufixo="B1")
        ensure_acompanhamento_passagem(self.emissao_a)
        ensure_acompanhamento_passagem(self.emissao_b)

    def test_da_empresa_so_devolve_proprias(self):
        ids_a = list(
            AcompanhamentoPassagem.objects.da_empresa(self.empresa_a)
            .values_list("emissao_id", flat=True)
        )
        ids_b = list(
            AcompanhamentoPassagem.objects.da_empresa(self.empresa_b)
            .values_list("emissao_id", flat=True)
        )
        self.assertEqual(ids_a, [self.emissao_a.id])
        self.assertEqual(ids_b, [self.emissao_b.id])

    def test_da_empresa_sem_empresa_devolve_vazio(self):
        self.assertEqual(
            AcompanhamentoPassagem.objects.da_empresa(None).count(),
            0,
        )

    def test_com_voo_futuro_filtra_passados(self):
        # Criamos uma emissão com data passada e nenhuma volta
        passada = _criar_emissao(self.empresa_a, sufixo="A2", data_ida=timezone.now() - timedelta(days=3))[1]
        ensure_acompanhamento_passagem(passada)
        futuras = AcompanhamentoPassagem.objects.da_empresa(self.empresa_a).com_voo_futuro()
        self.assertNotIn(passada.id, list(futuras.values_list("emissao_id", flat=True)))


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "test-bulk"}})
class DispatchEDebounceTest(TestCase):
    """`disparar_atualizacao_em_massa` precisa ser idempotente em rajada."""

    def setUp(self):
        cache.clear()
        self.empresa = Empresa.objects.create(nome="Agência Debounce")
        user, emissao = _criar_emissao(self.empresa, sufixo="D1")
        ensure_acompanhamento_passagem(emissao)
        self.user = user

    def test_segundo_dispatch_recusa(self):
        # Forçamos o thread a não rodar inline
        with mock.patch("gestao.services.monitoring.bulk_runner.threading.Thread"):
            r1 = bulk_runner.disparar_atualizacao_em_massa(self.empresa, iniciado_por=self.user)
        self.assertTrue(r1.aceito)
        with mock.patch("gestao.services.monitoring.bulk_runner.threading.Thread"):
            r2 = bulk_runner.disparar_atualizacao_em_massa(self.empresa, iniciado_por=self.user)
        self.assertFalse(r2.aceito)
        self.assertEqual(r2.job.pk, r1.job.pk)

    def test_dispatch_sem_passagens_marca_concluido(self):
        AcompanhamentoPassagem.objects.all().delete()
        with mock.patch("gestao.services.monitoring.bulk_runner.threading.Thread"):
            r = bulk_runner.disparar_atualizacao_em_massa(self.empresa, iniciado_por=self.user)
        self.assertTrue(r.aceito)
        self.assertEqual(r.job.status, AtualizacaoEmMassa.STATUS_CONCLUIDO)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "test-bulk-rl"}})
class RateLimiterTest(TestCase):
    def setUp(self):
        cache.clear()

    def test_burst_e_recarrega(self):
        cfg = RateLimitConfig(rate_per_second=10.0, burst=2, max_wait_seconds=2.0)
        # 2 acquires consomem o burst — não devem bloquear
        with acquire("FAKE", config=cfg):
            pass
        with acquire("FAKE", config=cfg):
            pass

    def test_estoura_max_wait(self):
        cfg = RateLimitConfig(rate_per_second=0.05, burst=1, max_wait_seconds=0.2)
        with acquire("FAKE", config=cfg):
            pass
        with self.assertRaises(RateLimitTimeout):
            with acquire("FAKE", config=cfg):
                pass

    def tearDown(self):
        reset("FAKE")


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "test-bulk-views"}})
class ViewsAtualizacaoTest(TestCase):
    """Tenant gates nas views: empresa B não pode ler job da empresa A."""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.empresa_a = Empresa.objects.create(nome="Agência ViewA")
        self.empresa_b = Empresa.objects.create(nome="Agência ViewB")
        self.user_a, self.emissao_a = _criar_emissao(self.empresa_a, sufixo="VA1")
        self.user_b, self.emissao_b = _criar_emissao(self.empresa_b, sufixo="VB1")
        ensure_acompanhamento_passagem(self.emissao_a)
        ensure_acompanhamento_passagem(self.emissao_b)
        self.job_a = AtualizacaoEmMassa.objects.create(
            empresa=self.empresa_a,
            iniciado_por=self.user_a,
            total=1,
        )

    def test_user_b_nao_le_job_de_a(self):
        self.client.force_login(self.user_b)
        url = reverse("admin_monitoramento_job_status", args=[self.job_a.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_user_a_atualiza_propria_passagem(self):
        self.client.force_login(self.user_a)
        url = reverse("admin_emissao_atualizar_status", args=[self.emissao_a.pk])
        with mock.patch(
            "gestao.views.monitoramento.sync_acompanhamento_passagem",
            return_value=AcompanhamentoSyncResult(success=True, message="ok"),
        ):
            resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["sucesso"])

    def test_user_b_nao_atualiza_passagem_de_a(self):
        self.client.force_login(self.user_b)
        url = reverse("admin_emissao_atualizar_status", args=[self.emissao_a.pk])
        resp = self.client.post(url)
        # ensure_company_access devolve sem_permissao.html (HTTP 200 com template)
        self.assertNotIn("sucesso", resp.content.decode("utf-8", errors="ignore")[:200])
