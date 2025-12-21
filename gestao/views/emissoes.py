from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from decimal import Decimal
from gestao.models import ContaFidelidade, Movimentacao, AcessoClienteLog
from painel_cliente.views import build_dashboard_context
from django import forms
from django.db import models

from ..forms import (
    ContaFidelidadeForm,
    ProgramaFidelidadeForm,
    ClienteForm,
    NovoClienteForm,
    AeroportoForm,
    EmissaoPassagemForm,
    EmissaoHotelForm,
    CotacaoVooForm,
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
from services.pdf_service import emissao_pdf_response
import csv
import json
from datetime import timedelta

from .permissions import require_admin_or_operator
from gestao.services.emissao_financeiro import (
    calcular_economia,
    calcular_valor_referencia_pontos,
    registrar_movimentacao_pontos,
)
from gestao.services.clientes_programas import (
    build_clientes_programas_map,
    build_contas_administradas_programas_map,
)


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


# --- EMISSÕES ---
@login_required
def admin_emissoes(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    programa_id = request.GET.get("programa")
    cliente_id = request.GET.get("cliente")
    q = request.GET.get("q")
    data_ini = request.GET.get("data_ini")
    data_fim = request.GET.get("data_fim")

    emissoes = EmissaoPassagem.objects.filter(
        Q(cliente__perfil="cliente", cliente__ativo=True) | Q(conta_administrada__isnull=False)
    ).select_related(
        "cliente",
        "programa",
        "aeroporto_partida",
        "aeroporto_destino",
        "conta_administrada",
    )
    if programa_id:
        emissoes = emissoes.filter(programa_id=programa_id)
    if cliente_id:
        emissoes = emissoes.filter(cliente_id=cliente_id)
    if q:
        emissoes = emissoes.filter(
            Q(aeroporto_partida__sigla__icontains=q)
            | Q(aeroporto_destino__sigla__icontains=q)
            | Q(aeroporto_partida__nome__icontains=q)
            | Q(aeroporto_destino__nome__icontains=q)
            | Q(cliente__usuario__username__icontains=q)
        )
    if data_ini:
        emissoes = emissoes.filter(data_ida__gte=data_ini)
    if data_fim:
        emissoes = emissoes.filter(data_volta__lte=data_fim)

    if request.GET.get("export") == "excel":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="emissoes.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Cliente",
                "Programa",
                "Aeroporto Partida",
                "Aeroporto Destino",
                "Data Ida",
                "Data Volta",
                "Qtd Passageiros",
                "Valor Referência",
                "Valor Pago",
                "Pontos Usados",
                "Economia",
                "Detalhes",
            ]
        )
        for e in emissoes:
            writer.writerow(
                [
                    str(e.cliente),
                    str(e.programa),
                    e.aeroporto_partida,
                    e.aeroporto_destino,
                    e.data_ida,
                    e.data_volta,
                    e.qtd_passageiros,
                    e.valor_referencia,
                    e.valor_pago,
                    e.pontos_utilizados,
                    e.economia_obtida,
                    e.detalhes,
                ]
            )
        return response

    programas = ProgramaFidelidade.objects.all()
    clientes = Cliente.objects.filter(perfil="cliente", ativo=True).select_related("usuario")
    return render(
        request,
        "admin_custom/emissoes.html",
        {
            "emissoes": emissoes,
            "programas": programas,
            "clientes": clientes,
            "params": request.GET,
        },
    )


@login_required
def nova_emissao(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    cliente_id = request.GET.get("cliente_id")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    escalas_por_tipo = {"ida": [], "volta": []}
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.cliente and not emissao.cliente.ativo:
                return HttpResponse("Cliente inativo", status=403)
            if emissao.conta_administrada_id:
                conta = ContaFidelidade.objects.filter(
                    conta_administrada=emissao.conta_administrada,
                    programa=emissao.programa,
                ).select_related("programa").first()
            else:
                conta = ContaFidelidade.objects.filter(
                    cliente=emissao.cliente, programa=emissao.programa
                ).select_related("programa").first()
            if not conta:
                form.add_error("programa", "Selecione um programa vinculado ao titular escolhido.")
                messages.error(
                    request,
                    "Não foi possível salvar a emissão: programa não vinculado ao titular selecionado.",
                )
            if form.errors:
                form.add_error(None, "Revise os campos destacados antes de salvar a emissão.")
            elif emissao.pontos_utilizados and (not conta.valor_medio_por_mil or conta.valor_medio_por_mil <= 0):
                form.add_error(
                    "programa",
                    "Valor médio do milheiro ausente para o titular selecionado. Atualize os dados antes de prosseguir.",
                )
                messages.error(
                    request,
                    "Não foi possível salvar a emissão: valor médio do milheiro ausente para o titular.",
                )
            else:
                valor_referencia_pontos = calcular_valor_referencia_pontos(
                    emissao.pontos_utilizados or 0, conta.valor_medio_por_mil
                )
                emissao.valor_referencia_pontos = valor_referencia_pontos
                emissao.economia_obtida = calcular_economia(emissao, valor_referencia_pontos)
                emissao.save()
                total = int(request.POST.get("total_passageiros", 0))
                for i in range(total):
                    nome = request.POST.get(f"passageiro-{i}-nome")
                    doc = request.POST.get(f"passageiro-{i}-documento")
                    cat = request.POST.get(f"passageiro-{i}-categoria")
                    if nome and doc and cat:
                        Passageiro.objects.create(
                            emissao=emissao, nome=nome, documento=doc, categoria=cat
                        )
                for escala in escalas_payload:
                    Escala.objects.create(emissao=emissao, **escala)
                registrar_movimentacao_pontos(
                    conta, emissao, emissao.pontos_utilizados or 0, emissao.valor_referencia_pontos or Decimal("0")
                )
                messages.success(request, "Emissão salva com sucesso.")
                return redirect("admin_emissoes")
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
        else:
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
    else:
        initial = {"cliente": cliente_id} if cliente_id else {}
        form = EmissaoPassagemForm(initial=initial, empresa=empresa)
    emissoes = EmissaoPassagem.objects.all().order_by("-data_ida")
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        {
            "form": form,
            "emissoes": emissoes,
            "passageiros_json": "[]",
            "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
            "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
            "aeroportos_json": json.dumps(aeroportos),
            "cliente_id": cliente_id,
            "cliente_programas_json": json.dumps(build_clientes_programas_map(empresa_id=getattr(empresa, "id", None))),
            "contas_adm_programas_json": json.dumps(
                build_contas_administradas_programas_map(
                    empresa_id=getattr(empresa, "id", None)
                )
            ),
        },
    )


@login_required
def editar_emissao(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = EmissaoPassagem.objects.get(id=emissao_id)
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    escalas_por_tipo = _format_escalas(
        emissao.escalas.values("aeroporto_id", "duracao", "cidade", "tipo", "ordem")
    )
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST, instance=emissao, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.conta_administrada_id:
                conta = ContaFidelidade.objects.filter(
                    conta_administrada=emissao.conta_administrada,
                    programa=emissao.programa,
                ).select_related("programa").first()
            else:
                conta = ContaFidelidade.objects.filter(
                    cliente=emissao.cliente, programa=emissao.programa
                ).select_related("programa").first()
            if not conta:
                form.add_error("programa", "Selecione um programa vinculado ao titular escolhido.")
                messages.error(
                    request,
                    "Não foi possível salvar a emissão: programa não vinculado ao titular selecionado.",
                )
            if form.errors:
                form.add_error(None, "Revise os campos destacados antes de salvar a emissão.")
            elif emissao.pontos_utilizados and (not conta.valor_medio_por_mil or conta.valor_medio_por_mil <= 0):
                form.add_error(
                    "programa",
                    "Valor médio do milheiro ausente para o titular selecionado. Atualize os dados antes de prosseguir.",
                )
                messages.error(
                    request,
                    "Não foi possível salvar a emissão: valor médio do milheiro ausente para o titular.",
                )
            else:
                valor_referencia_pontos = calcular_valor_referencia_pontos(
                    emissao.pontos_utilizados or 0, conta.valor_medio_por_mil
                )
                emissao.valor_referencia_pontos = valor_referencia_pontos
                emissao.economia_obtida = calcular_economia(emissao, valor_referencia_pontos)
                emissao.save()
                emissao.passageiros.all().delete()
                total = int(request.POST.get("total_passageiros", 0))
                for i in range(total):
                    nome = request.POST.get(f"passageiro-{i}-nome")
                    doc = request.POST.get(f"passageiro-{i}-documento")
                    cat = request.POST.get(f"passageiro-{i}-categoria")
                    if nome and doc and cat:
                        Passageiro.objects.create(
                            emissao=emissao, nome=nome, documento=doc, categoria=cat
                        )
                emissao.escalas.all().delete()
                for escala in escalas_payload:
                    Escala.objects.create(emissao=emissao, **escala)
                registrar_movimentacao_pontos(
                    conta, emissao, emissao.pontos_utilizados or 0, emissao.valor_referencia_pontos or Decimal("0")
                )
                messages.success(request, "Emissão atualizada com sucesso.")
                return redirect("admin_emissoes")
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
        else:
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
    else:
        form = EmissaoPassagemForm(instance=emissao, empresa=empresa)
    emissoes = EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida")
    passageiros = list(
        emissao.passageiros.filter(categoria="adulto").values(
            "nome", "documento", "categoria"
        )
    )
    passageiros += list(
        emissao.passageiros.filter(categoria="crianca").values(
            "nome", "documento", "categoria"
        )
    )
    passageiros += list(
        emissao.passageiros.filter(categoria="bebe").values(
            "nome", "documento", "categoria"
        )
    )
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        {
            "form": form,
            "emissoes": emissoes,
            "passageiros_json": json.dumps(passageiros),
            "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
            "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
            "aeroportos_json": json.dumps(aeroportos),
            "cliente_programas_json": json.dumps(
                build_clientes_programas_map(emissao, empresa_id=getattr(empresa, "id", None))
            ),
            "contas_adm_programas_json": json.dumps(
                build_contas_administradas_programas_map(
                    empresa_id=getattr(empresa, "id", None), instance=emissao
                )
            ),
        },
    )


@login_required
def emissao_pdf(request, emissao_id):
    """Download da emissão em formato PDF para o painel administrativo."""
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = get_object_or_404(EmissaoPassagem, id=emissao_id)
    return emissao_pdf_response(emissao)


@login_required
def deletar_emissao(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    EmissaoPassagem.objects.filter(id=emissao_id).delete()
    messages.success(request, "Emissão deletada com sucesso.")
    return redirect("admin_emissoes")


@login_required
def admin_hoteis(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    busca = request.GET.get("busca", "")
    emissoes = EmissaoHotel.objects.all().select_related("cliente__usuario")
    if busca:
        emissoes = emissoes.filter(
            Q(cliente__usuario__username__icontains=busca)
            | Q(cliente__usuario__first_name__icontains=busca)
            | Q(nome_hotel__icontains=busca)
        )
    return render(
        request, "admin_custom/hoteis.html", {"emissoes": emissoes, "busca": busca}
    )


@login_required
def nova_emissao_hotel(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    if request.method == "POST":
        form = EmissaoHotelForm(request.POST)
        if form.is_valid():
            emissao = form.save(commit=False)
            if not emissao.cliente.ativo:
                return HttpResponse("Cliente inativo", status=403)
            if emissao.valor_referencia and emissao.valor_pago:
                emissao.economia_obtida = emissao.valor_referencia - emissao.valor_pago
            emissao.save()
            return redirect("admin_hoteis")
    else:
        form = EmissaoHotelForm()
    return render(request, "admin_custom/form_hotel.html", {"form": form})


@login_required
def editar_emissao_hotel(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = EmissaoHotel.objects.get(id=emissao_id)
    if request.method == "POST":
        form = EmissaoHotelForm(request.POST, instance=emissao)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.valor_referencia and emissao.valor_pago:
                emissao.economia_obtida = emissao.valor_referencia - emissao.valor_pago
            emissao.save()
            return redirect("admin_hoteis")
    else:
        form = EmissaoHotelForm(instance=emissao)
    return render(request, "admin_custom/form_hotel.html", {"form": form})


@login_required
def deletar_emissao_hotel(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    EmissaoHotel.objects.filter(id=emissao_id).delete()
    messages.success(request, "Emissão deletada com sucesso.")
    return redirect("admin_hoteis")
