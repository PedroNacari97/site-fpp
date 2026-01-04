from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from gestao.models import ContaFidelidade, Movimentacao, AcessoClienteLog
from django import forms
from django.db import models, transaction

from gestao.services.clientes_programas import (
    build_clientes_programas_map,
    build_contas_administradas_programas_map,
)
from gestao.services.emissao_financeiro import (
    calcular_custo_milhas,
    calcular_custo_total_emissao,
    calcular_economia,
    registrar_movimentacao_pontos,
)
from ..forms import (
    ContaFidelidadeForm,
    ProgramaFidelidadeForm,
    ClienteForm,
    NovoClienteForm,
    AeroportoForm,
    EmissaoPassagemForm,
    EmissaoHotelForm,
    CotacaoVooForm,
    CalculadoraCotacaoForm,
)
from django.contrib.auth.models import User
from ..models import (
    Cliente,
    ContaFidelidade,
    ProgramaFidelidade,
    EmissaoPassagem,
    Aeroporto,
    ValorMilheiro,
    EmissaoHotel,
    CotacaoVoo,
    Passageiro,
    Escala,
    CompanhiaAerea,
)
from services.pdf_service import cotacao_pdf_response
import csv
import json
from datetime import timedelta
from decimal import Decimal

from .permissions import require_admin_or_operator


def _build_escalas_from_request(request):
    escalas = []
    for tipo in ("ida", "volta"):
        if not request.POST.get(f"{tipo}_tem_escala"):
            continue
        try:
            total_escalas = int(request.POST.get(f"total_escalas_{tipo}", 0) or 0)
        except (TypeError, ValueError):
            total_escalas = 0
        for i in range(total_escalas):
            aeroporto_id = request.POST.get(f"escala-{tipo}-{i}-aeroporto")
            dur = request.POST.get(f"escala-{tipo}-{i}-duracao")
            cidade = request.POST.get(f"escala-{tipo}-{i}-cidade")
            if aeroporto_id and dur:
                try:
                    h, m = map(int, dur.split(":"))
                except (TypeError, ValueError):
                    continue
                escalas.append(
                    {
                        "aeroporto_id": aeroporto_id,
                        "duracao": timedelta(hours=h, minutes=m),
                        "cidade": cidade or "",
                        "tipo": tipo,
                        "ordem": i + 1,
                    }
                )
    return escalas


def _format_escalas(escalas_queryset):
    escalas_por_tipo = {"ida": [], "volta": []}
    for e in escalas_queryset:
        total_seconds = int(e["duracao"].total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        escala_formatada = {
            "aeroporto_id": e["aeroporto_id"],
            "duracao": f"{h:02d}:{m:02d}",
            "cidade": e["cidade"],
            "ordem": e.get("ordem") or 0,
        }
        escalas_por_tipo.get(e.get("tipo") or "ida", escalas_por_tipo["ida"]).append(
            escala_formatada
        )
    for tipo in escalas_por_tipo:
        escalas_por_tipo[tipo] = sorted(
            escalas_por_tipo[tipo], key=lambda esc: esc.get("ordem") or 0
        )
    return escalas_por_tipo


# --- COTAÇÕES ---
@login_required
def admin_cotacoes(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    if request.method == "POST":
        programa_nome = request.POST.get("programa_nome")
        valor_mercado = request.POST.get("valor_mercado")
        if programa_nome and valor_mercado:
            ValorMilheiro.objects.update_or_create(
                programa_nome=programa_nome, defaults={"valor_mercado": valor_mercado}
            )
    busca = request.GET.get("busca", "")
    cotacoes = ValorMilheiro.objects.all().order_by("programa_nome")
    if busca:
        cotacoes = cotacoes.filter(programa_nome__icontains=busca)
    programas = ProgramaFidelidade.objects.all()
    return render(
        request,
        "admin_custom/cotacoes.html",
        {
            "cotacoes": cotacoes,
            "programas": programas,
            "busca": busca,
            "menu_ativo": "cotacoes",
        },
    )


@login_required
def deletar_cotacao(request, cotacao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    ValorMilheiro.objects.filter(id=cotacao_id).delete()
    messages.success(request, "Cotação deletada com sucesso.")
    return redirect("admin_cotacoes")


# --- COTAÇÕES DE VOO ---
@login_required
def admin_cotacoes_voo(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    busca = request.GET.get("busca", "")
    cotacoes = CotacaoVoo.objects.filter(
        Q(cliente__perfil="cliente", cliente__ativo=True) | Q(conta_administrada__isnull=False)
    ).select_related(
        "cliente__usuario", "origem", "destino", "conta_administrada"
    )
    if busca:
        cotacoes = cotacoes.filter(
            Q(cliente__usuario__username__icontains=busca)
            | Q(cliente__usuario__first_name__icontains=busca)
            | Q(origem__nome__icontains=busca)
            | Q(destino__nome__icontains=busca)
        )
    return render(
        request,
        "admin_custom/cotacoes_voo.html",
        {"cotacoes": cotacoes, "busca": busca, "menu_ativo": "cotacoes"},
    )


@login_required
def nova_cotacao_voo(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    initial = {}
    escalas_por_tipo = {"ida": [], "volta": []}
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissao_id = request.GET.get("emissao")
    if emissao_id:
        emissao = get_object_or_404(EmissaoPassagem, id=emissao_id)
        initial = {
            "cliente": emissao.cliente_id,
            "companhia_aerea": (
                emissao.companhia_aerea.nome if emissao.companhia_aerea else ""
            ),
            "origem": emissao.aeroporto_partida_id,
            "destino": emissao.aeroporto_destino_id,
            "data_ida": emissao.data_ida,
            "data_volta": emissao.data_volta,
            "programa": emissao.programa_id,
            "qtd_passageiros": emissao.qtd_passageiros,
        }
        escalas_por_tipo = _format_escalas(
            emissao.escalas.values("aeroporto_id", "duracao", "cidade", "tipo", "ordem")
        )
    if request.method == "POST":
        form = CotacaoVooForm(request.POST, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        if form.is_valid():
            conta_filters = {"programa": form.cleaned_data["programa"]}
            if form.cleaned_data.get("conta_administrada"):
                conta_filters["conta_administrada"] = form.cleaned_data["conta_administrada"]
            else:
                conta_filters["cliente"] = form.cleaned_data["cliente"]
            conta = ContaFidelidade.objects.filter(**conta_filters).select_related("programa").first()
            valor_medio_milheiro = None
            if conta:
                valor_medio_milheiro = conta.valor_medio_por_mil
                if (not valor_medio_milheiro or valor_medio_milheiro <= 0) and getattr(conta.programa, "preco_medio_milheiro", None):
                    valor_medio_milheiro = float(conta.programa.preco_medio_milheiro)
            if not conta:
                form.add_error("programa", "Selecione um programa vinculado ao titular escolhido.")
            if form.errors:
                form.add_error(None, "Revise os campos destacados antes de salvar a cotação.")
                messages.error(
                    request,
                    "Não foi possível salvar a cotação: revise o programa e os campos destacados.",
                )
            elif form.cleaned_data.get("milhas") and (not valor_medio_milheiro or valor_medio_milheiro <= 0):
                form.add_error(
                    "programa",
                    "Valor médio do milheiro ausente para o titular selecionado. Atualize os dados antes de prosseguir.",
                )
                messages.error(
                    request,
                    "Não foi possível salvar a cotação: valor médio do milheiro ausente para o titular.",
                )
            else:
                cot = form.save()
                cot.escalas.all().delete()
                for escala in escalas_payload:
                    Escala.objects.create(cotacao=cot, **escala)
                if cot.status == "emissao" and cot.emissao is None:
                    try:
                        emissao = EmissaoPassagem(
                            cliente=cot.cliente,
                            aeroporto_partida=cot.origem,
                            aeroporto_destino=cot.destino,
                            data_ida=cot.data_ida,
                            data_volta=cot.data_volta,
                            programa=cot.programa,
                            qtd_passageiros=cot.qtd_passageiros,
                            companhia_aerea=CompanhiaAerea.objects.filter(
                                nome=cot.companhia_aerea
                            ).first(),
                            valor_referencia=cot.valor_passagem,
                            valor_pago=cot.valor_vista,
                            pontos_utilizados=cot.milhas,
                            detalhes=cot.observacoes,
                        )
                        emissao.valor_referencia_pontos = calcular_custo_milhas(
                            emissao.pontos_utilizados, valor_medio_milheiro
                        )
                        custo_total = calcular_custo_total_emissao(
                            emissao, valor_medio_milheiro, incluir_taxas=True
                        )
                        emissao.economia_obtida = calcular_economia(emissao, custo_total)
                        emissao.save()
                        for escala in cot.escalas.all():
                            Escala.objects.create(
                                emissao=emissao,
                                aeroporto=escala.aeroporto,
                                duracao=escala.duracao,
                                cidade=escala.cidade,
                                tipo=escala.tipo,
                                ordem=escala.ordem,
                            )
                        cot.emissao = emissao
                        cot.save()
                        registrar_movimentacao_pontos(
                            conta,
                            emissao,
                            emissao.pontos_utilizados or 0,
                            emissao.valor_referencia_pontos,
                        )
                    except Exception as e:
                        cot.delete()
                        messages.error(
                            request, f"Erro ao tentar criar Emissão a partir da Cotação: {e}"
                        )
                        return redirect("admin_cotacoes_voo")
                messages.success(request, "Cotação salva com sucesso.")
                return redirect("admin_cotacoes_voo")
        else:
            messages.error(
                request,
                "Não foi possível salvar a cotação. Corrija os campos destacados e tente novamente.",
            )
    else:
        form = CotacaoVooForm(initial=initial, empresa=empresa)
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_cotacao.html",
        {
            "form": form,
            "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
            "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
            "aeroportos_json": json.dumps(aeroportos),
            "cliente_programas_json": json.dumps(build_clientes_programas_map(empresa_id=getattr(empresa, "id", None))),
            "contas_adm_programas_json": json.dumps(
                build_contas_administradas_programas_map(
                    empresa_id=getattr(empresa, "id", None)
                )
            ),
            "menu_ativo": "cotacoes",
        },
    )


@login_required
def editar_cotacao_voo(request, cotacao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    cotacao = get_object_or_404(CotacaoVoo, id=cotacao_id)
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    escalas_por_tipo = _format_escalas(
        cotacao.escalas.values("aeroporto_id", "duracao", "cidade", "tipo", "ordem")
    )
    if request.method == "POST":
        form = CotacaoVooForm(request.POST, instance=cotacao, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        if form.is_valid():
            with transaction.atomic():
                conta_filters = {"programa": form.cleaned_data["programa"]}
                if form.cleaned_data.get("conta_administrada"):
                    conta_filters["conta_administrada"] = form.cleaned_data["conta_administrada"]
                else:
                    conta_filters["cliente"] = form.cleaned_data["cliente"]
                conta = ContaFidelidade.objects.filter(**conta_filters).select_related("programa").first()
                valor_medio_milheiro = None
                if conta:
                    valor_medio_milheiro = conta.valor_medio_por_mil
                    if (not valor_medio_milheiro or valor_medio_milheiro <= 0) and getattr(conta.programa, "preco_medio_milheiro", None):
                        valor_medio_milheiro = float(conta.programa.preco_medio_milheiro)
                if not conta:
                    form.add_error("programa", "Selecione um programa vinculado ao titular escolhido.")
                if form.errors:
                    form.add_error(None, "Revise os campos destacados antes de salvar a cotação.")
                    messages.error(
                        request,
                        "Não foi possível salvar a cotação: revise o programa e os campos destacados.",
                    )
                elif form.cleaned_data.get("milhas") and (not valor_medio_milheiro or valor_medio_milheiro <= 0):
                    form.add_error(
                        "programa",
                        "Valor médio do milheiro ausente para o titular selecionado. Atualize os dados antes de prosseguir.",
                    )
                    messages.error(
                        request,
                        "Não foi possível salvar a cotação: valor médio do milheiro ausente para o titular.",
                    )
                else:
                    cot = form.save()
                    cot.escalas.all().delete()
                    for escala in escalas_payload:
                        Escala.objects.create(cotacao=cot, **escala)
                    if cot.status == "emissao" and cot.emissao is None:
                        try:
                            emissao = EmissaoPassagem(
                                cliente=cot.cliente,
                                aeroporto_partida=cot.origem,
                                aeroporto_destino=cot.destino,
                                data_ida=cot.data_ida,
                                data_volta=cot.data_volta,
                                programa=cot.programa,
                                qtd_passageiros=cot.qtd_passageiros,
                                companhia_aerea=CompanhiaAerea.objects.filter(
                                    nome=cot.companhia_aerea
                                ).first(),
                                valor_referencia=cot.valor_passagem,
                                valor_pago=cot.valor_vista,
                                pontos_utilizados=cot.milhas,
                                detalhes=cot.observacoes,
                            )
                            emissao.valor_referencia_pontos = calcular_custo_milhas(
                                emissao.pontos_utilizados, conta.valor_medio_por_mil
                            )
                            custo_total = calcular_custo_total_emissao(
                                emissao, conta.valor_medio_por_mil, incluir_taxas=True
                            )
                            emissao.economia_obtida = calcular_economia(emissao, custo_total)
                            emissao.save()
                            for escala in cot.escalas.all():
                                Escala.objects.create(
                                    emissao=emissao,
                                    aeroporto=escala.aeroporto,
                                    duracao=escala.duracao,
                                    cidade=escala.cidade,
                                    tipo=escala.tipo,
                                    ordem=escala.ordem,
                                )
                            cot.emissao = emissao
                            cot.save()
                            registrar_movimentacao_pontos(
                                conta,
                                emissao,
                                emissao.pontos_utilizados or 0,
                                emissao.valor_referencia_pontos,
                            )
                        except Exception as e:
                            transaction.set_rollback(True)
                            messages.error(
                                request, f"Erro ao tentar criar Emissão a partir da Cotação: {e}"
                            )
                            return redirect("admin_cotacoes_voo")
                    messages.success(request, "Cotação atualizada com sucesso.")
                    return redirect("admin_cotacoes_voo")
    else:
        form = CotacaoVooForm(instance=cotacao, empresa=empresa)
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_cotacao.html",
        {
            "form": form,
            "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
            "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
            "aeroportos_json": json.dumps(aeroportos),
            "cliente_programas_json": json.dumps(
                build_clientes_programas_map(cotacao, empresa_id=getattr(empresa, "id", None))
            ),
            "contas_adm_programas_json": json.dumps(
                build_contas_administradas_programas_map(
                    empresa_id=getattr(empresa, "id", None), instance=cotacao
                )
            ),
            "menu_ativo": "cotacoes",
        },
    )


@login_required
def deletar_cotacao_voo(request, cotacao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    CotacaoVoo.objects.filter(id=cotacao_id).delete()
    messages.success(request, "Cotação de voo deletada com sucesso.")
    return redirect("admin_cotacoes_voo")


@login_required
def admin_valor_milheiro(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    cotacoes = ValorMilheiro.objects.all().order_by("programa_nome")
    return render(
        request,
        "admin_custom/valor_milheiro.html",
        {"cotacoes": cotacoes, "menu_ativo": "cotacoes"},
    )


@login_required
def cotacao_voo_pdf(request, cotacao_id):
    """Download da cotação de voo em PDF."""
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    cotacao = get_object_or_404(CotacaoVoo, id=cotacao_id)
    return cotacao_pdf_response(cotacao)


@login_required
def calculadora_cotacao(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    resultado = None
    if request.method == "POST":
        form = CalculadoraCotacaoForm(request.POST)
        if form.is_valid():
            milhas = form.cleaned_data["milhas"]
            valor_milheiro = form.cleaned_data["valor_milheiro"]
            taxas = form.cleaned_data["taxas"]
            juros = form.cleaned_data["juros"]
            desconto = form.cleaned_data["desconto"]
            valor_passagem = form.cleaned_data["valor_passagem"]
            parcelas = form.cleaned_data["parcelas"] or 1

            base = (Decimal(milhas) / Decimal("1000")) * Decimal(
                valor_milheiro
            ) + Decimal(taxas)
            valor_parcelado = base * Decimal(juros)
            valor_vista = valor_parcelado * Decimal(desconto)
            economia = Decimal(valor_passagem) - valor_vista
            parcela = valor_parcelado / Decimal(parcelas)
            resultado = {
                "valor_parcelado": round(valor_parcelado, 2),
                "valor_vista": round(valor_vista, 2),
                "economia": round(economia, 2),
                "parcela": round(parcela, 2),
            }
    else:
        form = CalculadoraCotacaoForm()
    return render(
        request,
        "admin_custom/calculadora_cotacao.html",
        {"form": form, "resultado": resultado, "menu_ativo": "calculadora"},
    )
