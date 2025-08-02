from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
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
from ..pdf_cotacao import gerar_pdf_cotacao
from ..pdf_emissao import gerar_pdf_emissao
import csv
import json
from datetime import timedelta


def admin_required(user):
    return user.is_staff or user.is_superuser


# --- EMISSÕES ---
@login_required
@user_passes_test(admin_required)
def admin_emissoes(request):
    programa_id = request.GET.get("programa")
    cliente_id = request.GET.get("cliente")
    q = request.GET.get("q")
    data_ini = request.GET.get("data_ini")
    data_fim = request.GET.get("data_fim")

    emissoes = EmissaoPassagem.objects.all().select_related(
        "cliente", "programa", "aeroporto_partida", "aeroporto_destino"
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
    clientes = Cliente.objects.all()
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
@user_passes_test(admin_required)
def nova_emissao(request):
    cliente_id = request.GET.get("cliente_id")
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST)
        if form.is_valid():
            emissao = form.save(commit=False)
            if not emissao.cliente.ativo:
                return HttpResponse("Cliente inativo", status=403)
            if emissao.valor_referencia and emissao.valor_pago:
                emissao.economia_obtida = emissao.valor_referencia - emissao.valor_pago
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
            total_escalas = int(request.POST.get("total_escalas", 0))
            for i in range(total_escalas):
                aeroporto_id = request.POST.get(f"escala-{i}-aeroporto")
                dur = request.POST.get(f"escala-{i}-duracao")
                cidade = request.POST.get(f"escala-{i}-cidade")
                if aeroporto_id and dur:
                    h, m = map(int, dur.split(":"))
                    Escala.objects.create(
                        emissao=emissao,
                        aeroporto_id=aeroporto_id,
                        duracao=timedelta(hours=h, minutes=m),
                        cidade=cidade or "",
                    )
            return redirect("admin_emissoes")
    else:
        initial = {"cliente": cliente_id} if cliente_id else {}
        form = EmissaoPassagemForm(initial=initial)
    emissoes = EmissaoPassagem.objects.all().order_by("-data_ida")
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        {
            "form": form,
            "emissoes": emissoes,
            "passageiros_json": "[]",
            "escalas_json": "[]",
            "aeroportos_json": json.dumps(aeroportos),
            "cliente_id": cliente_id,
        },
    )

@login_required
@user_passes_test(admin_required)
def editar_emissao(request, emissao_id):
    emissao = EmissaoPassagem.objects.get(id=emissao_id)
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST, instance=emissao)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.valor_referencia and emissao.valor_pago:
                emissao.economia_obtida = emissao.valor_referencia - emissao.valor_pago
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
            total_escalas = int(request.POST.get("total_escalas", 0))
            for i in range(total_escalas):
                aeroporto_id = request.POST.get(f"escala-{i}-aeroporto")
                dur = request.POST.get(f"escala-{i}-duracao")
                cidade = request.POST.get(f"escala-{i}-cidade")
                if aeroporto_id and dur:
                    h, m = map(int, dur.split(":"))
                    Escala.objects.create(
                        emissao=emissao,
                        aeroporto_id=aeroporto_id,
                        duracao=timedelta(hours=h, minutes=m),
                        cidade=cidade or "",
                    )
            return redirect("admin_emissoes")
    else:
        form = EmissaoPassagemForm(instance=emissao)
        form.fields['qtd_escalas'].initial = emissao.escalas.count()
    emissoes = EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida")
    passageiros = list(
        emissao.passageiros.filter(categoria="adulto").values("nome", "documento", "categoria")
    )
    passageiros += list(
        emissao.passageiros.filter(categoria="crianca").values("nome", "documento", "categoria")
    )
    passageiros += list(
        emissao.passageiros.filter(categoria="bebe").values("nome", "documento", "categoria")
    )
    escalas = list(
        emissao.escalas.values("aeroporto_id", "duracao", "cidade")
    )
    for e in escalas:
        total_seconds = int(e["duracao"].total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        e["duracao"] = f"{h:02d}:{m:02d}"
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        {
            "form": form,
            "emissoes": emissoes,
            "passageiros_json": json.dumps(passageiros),
            "escalas_json": json.dumps(escalas),
            "aeroportos_json": json.dumps(aeroportos),
        },
    )


@login_required
@user_passes_test(admin_required)
def emissao_pdf(request, emissao_id):
    emissao = get_object_or_404(EmissaoPassagem, id=emissao_id)
    pdf = gerar_pdf_emissao(emissao)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="emissao_{emissao.id}.pdf"'
    return response


@login_required
@user_passes_test(admin_required)
def admin_hoteis(request):
    emissoes = EmissaoHotel.objects.all().select_related("cliente")
    return render(request, "admin_custom/hoteis.html", {"emissoes": emissoes})


@login_required
@user_passes_test(admin_required)
def nova_emissao_hotel(request):
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
@user_passes_test(admin_required)
def editar_emissao_hotel(request, emissao_id):
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


