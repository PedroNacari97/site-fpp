"""
Views do modulo tributario/operacional do /ncadm/.

- Custos operacionais (Railway, OpenAI, dominio) — CRUD simples.
- Obrigacoes fiscais (DAS, DEFIS, NFS-e) — CRUD simples + marcar como paga.
- Export CSV fechamento mensal pro contador.
"""
from __future__ import annotations

import csv
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .mixins import SuperAdminRequiredMixin
from .models import CustoOperacional, ObrigacaoFiscal, PerfilFiscal, RecebimentoReceita
from .services import das_calculator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_decimal(raw: str, default: Decimal = Decimal("0.00")) -> Decimal:
    if not raw:
        return default
    try:
        return Decimal(str(raw).replace(",", ".").strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def _parse_mes(raw: str) -> date | None:
    """Aceita 'YYYY-MM' ou 'YYYY-MM-DD' e retorna o primeiro dia do mes."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        if len(raw) == 7:
            return date.fromisoformat(f"{raw}-01")
        d = date.fromisoformat(raw)
        return d.replace(day=1)
    except (ValueError, TypeError):
        return None


def _parse_data(raw: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip())
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Custos operacionais
# ---------------------------------------------------------------------------

class CustosListView(SuperAdminRequiredMixin):
    def get(self, request):
        qs = CustoOperacional.objects.all()
        mes_filtro = request.GET.get("mes", "").strip()
        categoria_filtro = request.GET.get("categoria", "").strip()

        if mes_filtro:
            ref = _parse_mes(mes_filtro)
            if ref:
                qs = qs.filter(mes_referencia=ref)
        if categoria_filtro:
            qs = qs.filter(categoria=categoria_filtro)

        from django.db.models import Sum, Q as _Q
        totais = qs.aggregate(
            total=Sum("valor_brl"),
            iof=Sum("iof"),
            usd=Sum("valor_brl", filter=_Q(moeda=CustoOperacional.MOEDA_USD)),
            brl=Sum("valor_brl", filter=_Q(moeda=CustoOperacional.MOEDA_BRL)),
        )

        return render(request, "superadmin/custos_list.html", {
            "menu_ativo": "custos",
            "custos": qs.order_by("-mes_referencia", "categoria"),
            "categorias": CustoOperacional.CATEGORIA_CHOICES,
            "mes_filtro": mes_filtro,
            "categoria_filtro": categoria_filtro,
            "totais": totais,
        })


class CustoCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        mes_default = timezone.now().date().replace(day=1).isoformat()[:7]
        return render(request, "superadmin/custo_form.html", {
            "menu_ativo": "custos",
            "editando": False,
            "categorias": CustoOperacional.CATEGORIA_CHOICES,
            "moedas": CustoOperacional.MOEDA_CHOICES,
            "mes_default": mes_default,
        })

    def post(self, request):
        erros, custo = _save_custo(request)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/custo_form.html", {
                "menu_ativo": "custos", "editando": False,
                "categorias": CustoOperacional.CATEGORIA_CHOICES,
                "moedas": CustoOperacional.MOEDA_CHOICES,
                "form_data": request.POST,
            })
        messages.success(request, f"Custo {custo.fornecedor} registrado.")
        return redirect(reverse("superadmin_custos_list"))


class CustoEditView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        custo = get_object_or_404(CustoOperacional, pk=pk)
        return render(request, "superadmin/custo_form.html", {
            "menu_ativo": "custos",
            "editando": True,
            "custo": custo,
            "categorias": CustoOperacional.CATEGORIA_CHOICES,
            "moedas": CustoOperacional.MOEDA_CHOICES,
        })

    def post(self, request, pk):
        custo = get_object_or_404(CustoOperacional, pk=pk)
        erros, custo = _save_custo(request, custo)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/custo_form.html", {
                "menu_ativo": "custos", "editando": True,
                "custo": custo,
                "categorias": CustoOperacional.CATEGORIA_CHOICES,
                "moedas": CustoOperacional.MOEDA_CHOICES,
                "form_data": request.POST,
            })
        messages.success(request, "Custo atualizado.")
        return redirect(reverse("superadmin_custos_list"))


class CustoDeleteView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        custo = get_object_or_404(CustoOperacional, pk=pk)
        desc = f"{custo.fornecedor} ({custo.mes_referencia:%Y-%m})"
        custo.delete()
        messages.success(request, f"Custo {desc} removido.")
        return redirect(reverse("superadmin_custos_list"))


def _save_custo(request, custo: CustoOperacional | None = None):
    erros: list[str] = []
    mes = _parse_mes(request.POST.get("mes_referencia", ""))
    if not mes:
        erros.append("Informe o mes de referencia (YYYY-MM).")
    categoria = request.POST.get("categoria", "").strip()
    if categoria not in dict(CustoOperacional.CATEGORIA_CHOICES):
        categoria = CustoOperacional.CATEGORIA_OUTROS
    fornecedor = request.POST.get("fornecedor", "").strip()
    if not fornecedor:
        erros.append("Fornecedor e obrigatorio.")

    moeda = request.POST.get("moeda", CustoOperacional.MOEDA_BRL).strip()
    if moeda not in dict(CustoOperacional.MOEDA_CHOICES):
        moeda = CustoOperacional.MOEDA_BRL

    valor_original = _parse_decimal(request.POST.get("valor_original", ""))
    if valor_original <= 0:
        erros.append("Valor original deve ser maior que zero.")
    cambio = _parse_decimal(
        request.POST.get("cambio_ptax", ""),
        default=Decimal("1.0000") if moeda == CustoOperacional.MOEDA_BRL else Decimal("0"),
    )
    if moeda == CustoOperacional.MOEDA_USD and cambio <= 0:
        erros.append("Informe o cambio PTAX do dia do pagamento.")
    iof = _parse_decimal(request.POST.get("iof", ""))

    # Calcula valor_brl automaticamente
    if moeda == CustoOperacional.MOEDA_BRL:
        valor_brl = valor_original
    else:
        valor_brl = (valor_original * cambio) + iof

    if erros:
        return erros, custo

    if custo is None:
        custo = CustoOperacional()
    custo.mes_referencia = mes
    custo.categoria = categoria
    custo.fornecedor = fornecedor[:120]
    custo.descricao = request.POST.get("descricao", "").strip()[:240]
    custo.moeda = moeda
    custo.valor_original = valor_original
    custo.cambio_ptax = cambio if moeda == CustoOperacional.MOEDA_USD else Decimal("1.0000")
    custo.iof = iof if moeda == CustoOperacional.MOEDA_USD else Decimal("0.00")
    custo.valor_brl = valor_brl.quantize(Decimal("0.01"))
    custo.tem_invoice = request.POST.get("tem_invoice") == "1"
    custo.observacoes = request.POST.get("observacoes", "").strip()
    anexo = request.FILES.get("anexo")
    if anexo:
        custo.anexo = anexo
    custo.save()
    return [], custo


# ---------------------------------------------------------------------------
# Obrigacoes fiscais
# ---------------------------------------------------------------------------

class ObrigacoesListView(SuperAdminRequiredMixin):
    def get(self, request):
        qs = ObrigacaoFiscal.objects.all()
        status_filtro = request.GET.get("status", "").strip()
        if status_filtro:
            qs = qs.filter(status=status_filtro)

        hoje = timezone.now().date()
        # Marca atrasadas automaticamente
        qs.filter(
            status=ObrigacaoFiscal.STATUS_PENDENTE, vencimento__lt=hoje,
        ).update(status=ObrigacaoFiscal.STATUS_ATRASADA)

        return render(request, "superadmin/obrigacoes_list.html", {
            "menu_ativo": "fiscal",
            "obrigacoes": qs.order_by("vencimento"),
            "status_choices": ObrigacaoFiscal.STATUS_CHOICES,
            "tipo_choices": ObrigacaoFiscal.TIPO_CHOICES,
            "status_filtro": status_filtro,
            "hoje": hoje,
        })


class ObrigacaoCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        return render(request, "superadmin/obrigacao_form.html", {
            "menu_ativo": "fiscal",
            "editando": False,
            "tipos": ObrigacaoFiscal.TIPO_CHOICES,
        })

    def post(self, request):
        erros, obg = _save_obrigacao(request)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/obrigacao_form.html", {
                "menu_ativo": "fiscal", "editando": False,
                "tipos": ObrigacaoFiscal.TIPO_CHOICES,
                "form_data": request.POST,
            })
        messages.success(request, "Obrigacao registrada.")
        return redirect(reverse("superadmin_obrigacoes_list"))


class ObrigacaoEditView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        obg = get_object_or_404(ObrigacaoFiscal, pk=pk)
        return render(request, "superadmin/obrigacao_form.html", {
            "menu_ativo": "fiscal",
            "editando": True,
            "obrigacao": obg,
            "tipos": ObrigacaoFiscal.TIPO_CHOICES,
        })

    def post(self, request, pk):
        obg = get_object_or_404(ObrigacaoFiscal, pk=pk)
        erros, obg = _save_obrigacao(request, obg)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/obrigacao_form.html", {
                "menu_ativo": "fiscal", "editando": True,
                "obrigacao": obg, "tipos": ObrigacaoFiscal.TIPO_CHOICES,
                "form_data": request.POST,
            })
        messages.success(request, "Obrigacao atualizada.")
        return redirect(reverse("superadmin_obrigacoes_list"))


class ObrigacaoMarcarPagaView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        obg = get_object_or_404(ObrigacaoFiscal, pk=pk)
        obg.status = ObrigacaoFiscal.STATUS_PAGA
        obg.pago_em = timezone.now().date()
        obg.save(update_fields=["status", "pago_em", "atualizado_em"])
        messages.success(request, f"{obg.get_tipo_display()} marcada como paga.")
        return redirect(reverse("superadmin_obrigacoes_list"))


class ObrigacaoDeleteView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        obg = get_object_or_404(ObrigacaoFiscal, pk=pk)
        obg.delete()
        messages.success(request, "Obrigacao removida.")
        return redirect(reverse("superadmin_obrigacoes_list"))


def _save_obrigacao(request, obg: ObrigacaoFiscal | None = None):
    erros: list[str] = []
    tipo = request.POST.get("tipo", ObrigacaoFiscal.TIPO_OUTRA)
    if tipo not in dict(ObrigacaoFiscal.TIPO_CHOICES):
        tipo = ObrigacaoFiscal.TIPO_OUTRA
    descricao = request.POST.get("descricao", "").strip()
    if not descricao:
        erros.append("Descricao e obrigatoria.")
    competencia = _parse_mes(request.POST.get("competencia", ""))
    if not competencia:
        erros.append("Competencia invalida (YYYY-MM).")
    vencimento = _parse_data(request.POST.get("vencimento", ""))
    if not vencimento:
        erros.append("Data de vencimento invalida.")
    valor = _parse_decimal(request.POST.get("valor_estimado", ""))
    if erros:
        return erros, obg
    if obg is None:
        obg = ObrigacaoFiscal()
    obg.tipo = tipo
    obg.descricao = descricao[:180]
    obg.competencia = competencia
    obg.vencimento = vencimento
    obg.valor_estimado = valor
    obg.observacoes = request.POST.get("observacoes", "").strip()

    hoje = timezone.now().date()
    if obg.status != ObrigacaoFiscal.STATUS_PAGA:
        obg.status = (
            ObrigacaoFiscal.STATUS_ATRASADA if vencimento < hoje
            else ObrigacaoFiscal.STATUS_PENDENTE
        )
    obg.save()
    return [], obg


# ---------------------------------------------------------------------------
# Export CSV fechamento mensal
# ---------------------------------------------------------------------------

class FechamentoMensalCSVView(SuperAdminRequiredMixin):
    """Gera CSV unico com custos do mes — pro contador ou planilha."""

    def get(self, request):
        mes_raw = request.GET.get("mes", "").strip()
        mes = _parse_mes(mes_raw) or timezone.now().date().replace(day=1)

        qs = CustoOperacional.objects.filter(mes_referencia=mes).order_by(
            "categoria", "fornecedor",
        )

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="ncfly_custos_{mes:%Y-%m}.csv"'
        )
        response.write("\ufeff")  # BOM para Excel PT-BR
        writer = csv.writer(response, delimiter=";")
        writer.writerow([
            "mes", "categoria", "fornecedor", "descricao", "moeda",
            "valor_original", "cambio_ptax", "iof_brl", "valor_brl",
            "tem_invoice", "observacoes",
        ])
        for c in qs:
            writer.writerow([
                c.mes_referencia.isoformat(),
                c.get_categoria_display(),
                c.fornecedor,
                c.descricao,
                c.moeda,
                f"{c.valor_original:.2f}",
                f"{c.cambio_ptax:.4f}",
                f"{c.iof:.2f}",
                f"{c.valor_brl:.2f}",
                "sim" if c.tem_invoice else "nao",
                c.observacoes,
            ])
        return response


# ---------------------------------------------------------------------------
# Perfil Fiscal (singleton)
# ---------------------------------------------------------------------------

class PerfilFiscalView(SuperAdminRequiredMixin):
    """GET mostra o perfil fiscal atual; POST salva as alteracoes."""

    template_name = "superadmin/perfil_fiscal_form.html"

    def _context(self, perfil: PerfilFiscal, form_data=None):
        return {
            "menu_ativo": "perfil_fiscal",
            "perfil": perfil,
            "regimes": PerfilFiscal.REGIME_CHOICES,
            "conversoes": PerfilFiscal.CONVERSAO_CHOICES,
            "form_data": form_data or {},
        }

    def get(self, request):
        perfil = PerfilFiscal.get_singleton()
        return render(request, self.template_name, self._context(perfil))

    def post(self, request):
        perfil = PerfilFiscal.get_singleton()
        erros = _save_perfil_fiscal(request, perfil)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(
                request, self.template_name,
                self._context(perfil, form_data=request.POST),
            )
        messages.success(request, "Perfil fiscal atualizado.")
        return redirect(reverse("superadmin_perfil_fiscal"))


def _save_perfil_fiscal(request, perfil: PerfilFiscal) -> list[str]:
    erros: list[str] = []

    # Identificacao
    perfil.razao_social = request.POST.get("razao_social", "").strip()[:180]
    perfil.nome_fantasia = request.POST.get("nome_fantasia", "").strip()[:120]
    perfil.cnpj = request.POST.get("cnpj", "").strip()[:18]
    perfil.data_abertura = _parse_data(request.POST.get("data_abertura", ""))
    perfil.endereco = request.POST.get("endereco", "").strip()[:240]
    perfil.municipio = request.POST.get("municipio", "").strip()[:80]
    perfil.uf = request.POST.get("uf", "").strip().upper()[:2]

    # Regime
    regime = request.POST.get("regime_atual", PerfilFiscal.REGIME_INOVA_SIMPLES)
    if regime not in dict(PerfilFiscal.REGIME_CHOICES):
        regime = PerfilFiscal.REGIME_INOVA_SIMPLES
    perfil.regime_atual = regime
    perfil.anexo_simples = request.POST.get("anexo_simples", "").strip()[:5]
    perfil.cnae_principal = request.POST.get("cnae_principal", "").strip()[:20]
    perfil.cnaes_secundarios = request.POST.get("cnaes_secundarios", "").strip()

    # Municipal
    perfil.inscricao_municipal = request.POST.get("inscricao_municipal", "").strip()[:40]
    perfil.inscricao_estadual = request.POST.get("inscricao_estadual", "").strip()[:40]
    perfil.iss_aliquota = _parse_decimal(request.POST.get("iss_aliquota", ""))
    perfil.nfse_portal_url = request.POST.get("nfse_portal_url", "").strip()[:200]

    # Contador
    perfil.contador_nome = request.POST.get("contador_nome", "").strip()[:120]
    perfil.contador_crc = request.POST.get("contador_crc", "").strip()[:30]
    perfil.contador_email = request.POST.get("contador_email", "").strip()[:254]
    perfil.contador_telefone = request.POST.get("contador_telefone", "").strip()[:30]
    perfil.contador_escritorio = request.POST.get("contador_escritorio", "").strip()[:120]

    # Conversao
    regime_alvo = request.POST.get("regime_alvo", "").strip()
    if regime_alvo and regime_alvo not in dict(PerfilFiscal.REGIME_CHOICES):
        regime_alvo = ""
    perfil.regime_alvo = regime_alvo
    conversao_status = request.POST.get("conversao_status", PerfilFiscal.CONVERSAO_NAO_INICIADA)
    if conversao_status not in dict(PerfilFiscal.CONVERSAO_CHOICES):
        conversao_status = PerfilFiscal.CONVERSAO_NAO_INICIADA
    perfil.conversao_status = conversao_status
    perfil.conversao_iniciada_em = _parse_data(request.POST.get("conversao_iniciada_em", ""))
    perfil.conversao_prevista_para = _parse_data(request.POST.get("conversao_prevista_para", ""))
    perfil.conversao_concluida_em = _parse_data(request.POST.get("conversao_concluida_em", ""))
    perfil.conversao_checklist = request.POST.get("conversao_checklist", "").strip()

    perfil.observacoes = request.POST.get("observacoes", "").strip()

    try:
        perfil.save()
    except Exception as exc:
        logger.exception("Erro ao salvar PerfilFiscal")
        erros.append(f"Erro ao salvar: {exc}")
    return erros


# ---------------------------------------------------------------------------
# Receitas / DAS (Simples Nacional Anexo III)
# ---------------------------------------------------------------------------

def _faturamentos_por_mes(qs_all=None) -> dict[date, Decimal]:
    """Agrega receitas por mes_competencia (para alimentar o calculo de RBT12)."""
    from django.db.models import Sum
    qs = qs_all if qs_all is not None else RecebimentoReceita.objects.all()
    linhas = (
        qs.values("mes_competencia")
          .annotate(total=Sum("valor_bruto"))
          .order_by("mes_competencia")
    )
    return {l["mes_competencia"]: Decimal(l["total"] or 0) for l in linhas}


def _mes_anterior(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


class ReceitasListView(SuperAdminRequiredMixin):
    """Lista de recebimentos + painel DAS do mes atual + projecao 6 meses."""

    def get(self, request):
        hoje = timezone.now().date()
        mes_atual = hoje.replace(day=1)

        # Filtro por mes (parametro ?mes=YYYY-MM)
        mes_filtro_raw = request.GET.get("mes", "").strip()
        mes_filtro = _parse_mes(mes_filtro_raw) or mes_atual

        qs_all = RecebimentoReceita.objects.all()
        qs_mes = qs_all.filter(mes_competencia=mes_filtro).order_by("-data", "-criado_em")

        # Mapa de faturamentos por mes (base do RBT12)
        faturamentos = _faturamentos_por_mes(qs_all)

        # Perfil fiscal — data de abertura (para RBT12 proporcional)
        perfil = PerfilFiscal.get_singleton()
        data_abertura = perfil.data_abertura

        # Calculo do DAS do mes selecionado
        rbt12_mes, proporcional = das_calculator.calcular_rbt12(
            faturamentos, mes_filtro, data_abertura,
        )
        faturamento_mes = faturamentos.get(mes_filtro, Decimal("0"))
        resultado = das_calculator.calcular_das(rbt12_mes, faturamento_mes)

        # Serie dos ultimos 6 meses (historico + mes atual)
        historico_meses: list[date] = []
        m = mes_atual
        for _ in range(6):
            historico_meses.append(m)
            m = _mes_anterior(m)
        historico_meses.reverse()
        serie = das_calculator.serie_mensal(faturamentos, historico_meses, data_abertura)
        total_das_6m = sum((item["das"] for item in serie), Decimal("0"))

        # Totais agregados do mes filtrado
        from django.db.models import Sum
        totais = qs_mes.aggregate(
            bruto=Sum("valor_bruto"),
            taxa=Sum("taxa_adquirente"),
        )

        return render(request, "superadmin/receitas_list.html", {
            "menu_ativo": "receitas",
            "recebimentos": qs_mes,
            "mes_filtro": mes_filtro,
            "mes_filtro_iso": mes_filtro.strftime("%Y-%m"),
            "mes_atual": mes_atual,
            "resultado": resultado,
            "rbt12_proporcional": proporcional,
            "serie": serie,
            "total_das_6m": total_das_6m,
            "totais": totais,
            "origens": RecebimentoReceita.ORIGEM_CHOICES,
            "naturezas": RecebimentoReceita.NATUREZA_CHOICES,
            "perfil": perfil,
        })


class ReceitaCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        return render(request, "superadmin/receita_form.html", {
            "menu_ativo": "receitas",
            "editando": False,
            "origens": RecebimentoReceita.ORIGEM_CHOICES,
            "naturezas": RecebimentoReceita.NATUREZA_CHOICES,
            "hoje": timezone.now().date().isoformat(),
        })

    def post(self, request):
        erros, rec = _save_recebimento(request)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/receita_form.html", {
                "menu_ativo": "receitas", "editando": False,
                "origens": RecebimentoReceita.ORIGEM_CHOICES,
                "naturezas": RecebimentoReceita.NATUREZA_CHOICES,
                "hoje": timezone.now().date().isoformat(),
                "form_data": request.POST,
            })
        messages.success(request, f"Recebimento de R$ {rec.valor_bruto} registrado.")
        return redirect(reverse("superadmin_receitas_list"))


class ReceitaEditView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        rec = get_object_or_404(RecebimentoReceita, pk=pk)
        return render(request, "superadmin/receita_form.html", {
            "menu_ativo": "receitas",
            "editando": True,
            "recebimento": rec,
            "origens": RecebimentoReceita.ORIGEM_CHOICES,
            "naturezas": RecebimentoReceita.NATUREZA_CHOICES,
        })

    def post(self, request, pk):
        rec = get_object_or_404(RecebimentoReceita, pk=pk)
        erros, rec = _save_recebimento(request, rec)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/receita_form.html", {
                "menu_ativo": "receitas", "editando": True,
                "recebimento": rec,
                "origens": RecebimentoReceita.ORIGEM_CHOICES,
                "naturezas": RecebimentoReceita.NATUREZA_CHOICES,
                "form_data": request.POST,
            })
        messages.success(request, "Recebimento atualizado.")
        return redirect(reverse("superadmin_receitas_list"))


class ReceitaDeleteView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        rec = get_object_or_404(RecebimentoReceita, pk=pk)
        rec.delete()
        messages.success(request, "Recebimento removido.")
        return redirect(reverse("superadmin_receitas_list"))


def _save_recebimento(request, rec: RecebimentoReceita | None = None):
    erros: list[str] = []
    data_receb = _parse_data(request.POST.get("data", ""))
    if not data_receb:
        erros.append("Data do recebimento e obrigatoria.")
    valor_bruto = _parse_decimal(request.POST.get("valor_bruto", ""))
    if valor_bruto <= 0:
        erros.append("Valor bruto deve ser maior que zero.")
    taxa = _parse_decimal(request.POST.get("taxa_adquirente", ""))

    natureza = request.POST.get("natureza", RecebimentoReceita.NATUREZA_SAAS)
    if natureza not in dict(RecebimentoReceita.NATUREZA_CHOICES):
        natureza = RecebimentoReceita.NATUREZA_SAAS
    origem = request.POST.get("origem", RecebimentoReceita.ORIGEM_ADQUIRENTE)
    if origem not in dict(RecebimentoReceita.ORIGEM_CHOICES):
        origem = RecebimentoReceita.ORIGEM_ADQUIRENTE

    if erros:
        return erros, rec

    if rec is None:
        rec = RecebimentoReceita()
    rec.data = data_receb
    rec.mes_competencia = data_receb.replace(day=1)
    rec.cliente = request.POST.get("cliente", "").strip()[:180]
    rec.natureza = natureza
    rec.origem = origem
    rec.valor_bruto = valor_bruto
    rec.taxa_adquirente = taxa
    rec.descricao = request.POST.get("descricao", "").strip()[:240]
    rec.nfse_emitida = request.POST.get("nfse_emitida") == "1"
    rec.nfse_numero = request.POST.get("nfse_numero", "").strip()[:40]
    rec.observacoes = request.POST.get("observacoes", "").strip()
    rec.save()
    return [], rec
