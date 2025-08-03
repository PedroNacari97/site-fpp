from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponse, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from gestao.models import ContaFidelidade, Movimentacao, AcessoClienteLog
from painel_cliente.views import build_dashboard_context
from django import forms
from django.db import models
from decimal import Decimal


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


# --- CONTAS ---
@login_required
@user_passes_test(admin_required)
def listar_contas(request):
    contas = ContaFidelidade.objects.all()
    return render(request, "admin_custom/contas_list.html", {"contas": contas})


@login_required
@user_passes_test(admin_required)
def criar_conta(request):
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm()
    return render(request, "admin_custom/contas_form.html", {"form": form})


@login_required
@user_passes_test(admin_required)
def editar_conta(request, conta_id):
    conta = ContaFidelidade.objects.get(id=conta_id)
    if request.method == "POST":
        form = ContaFidelidadeForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            return redirect("admin_contas")
    else:
        form = ContaFidelidadeForm(instance=conta)
    return render(request, "admin_custom/contas_form.html", {"form": form})


@login_required
def deletar_conta(request, conta_id):
    if not getattr(request.user, "cliente_gestao", None) or request.user.cliente_gestao.perfil != "admin":
        return HttpResponse("Você não tem permissão para deletar este item")
    ContaFidelidade.objects.filter(id=conta_id).delete()
    return redirect("admin_contas")


@login_required
@user_passes_test(admin_required)
def admin_contas(request):
    busca = request.GET.get("busca", "")
    contas = ContaFidelidade.objects.select_related("cliente__usuario", "programa")
    if busca:
        contas = contas.filter(
            Q(cliente__usuario__username__icontains=busca)
            | Q(cliente__usuario__first_name__icontains=busca)
            | Q(programa__nome__icontains=busca)
        )
    paginator = Paginator(contas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "admin_custom/contas.html",
        {
            "page_obj": page_obj,
            "busca": busca,
            "total_contas": contas.count(),
        },
    )



# --- AEROPORTOS ---
@login_required
@user_passes_test(admin_required)
def admin_aeroportos(request):
    busca = request.GET.get("busca", "")
    aeroportos = Aeroporto.objects.all()
    if busca:
        aeroportos = aeroportos.filter(Q(nome__icontains=busca) | Q(sigla__icontains=busca))
    return render(
        request,
        "admin_custom/aeroportos.html",
        {"aeroportos": aeroportos, "busca": busca},
    )


@login_required
@user_passes_test(admin_required)
def criar_aeroporto(request):
    if request.method == "POST":
        form = AeroportoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_aeroportos")
    else:
        form = AeroportoForm()
    return render(request, "admin_custom/form_aeroporto.html", {"form": form})


@login_required
def deletar_aeroporto(request, aeroporto_id):
    if not getattr(request.user, "cliente_gestao", None) or request.user.cliente_gestao.perfil != "admin":
        return HttpResponse("Você não tem permissão para deletar este item")
    Aeroporto.objects.filter(id=aeroporto_id).delete()
    return redirect("admin_aeroportos")


@login_required
@user_passes_test(admin_required)
def editar_aeroporto(request, aeroporto_id):
    aeroporto = Aeroporto.objects.get(id=aeroporto_id)
    if request.method == "POST":
        form = AeroportoForm(request.POST, instance=aeroporto)
        if form.is_valid():
            form.save()
            return redirect("admin_aeroportos")
    else:
        form = AeroportoForm(instance=aeroporto)
    return render(request, "admin_custom/form_aeroporto.html", {"form": form})


# --- DASHBOARD ---

def build_dashboard_metrics(cliente_id=None):
    contas = ContaFidelidade.objects.select_related("programa")
    emissoes = EmissaoPassagem.objects.all()
    hoteis = EmissaoHotel.objects.all()

    if cliente_id:
        contas = contas.filter(cliente_id=cliente_id)
        emissoes = emissoes.filter(cliente_id=cliente_id)
        hoteis = hoteis.filter(cliente_id=cliente_id)

    programas_data = []
    if cliente_id:
        for conta in contas:
            programas_data.append({
                "id": conta.programa.id,
                "nome": conta.programa.nome,
                "pontos": conta.saldo_pontos,
                "valor_total": (
                    Decimal(conta.saldo_pontos) / Decimal(1000)
                ) * Decimal(conta.valor_medio_por_mil) * conta.programa.preco_medio_milheiro,
                "valor_medio": conta.valor_medio_por_mil,
                "valor_referencia": conta.programa.preco_medio_milheiro,
                "conta_id": conta.id,
        })

    else:
        for prog in ProgramaFidelidade.objects.all():
            contas_prog = contas.filter(programa=prog)
            if not contas_prog.exists():
                continue
            total_pontos_prog = sum(c.saldo_pontos for c in contas_prog)
            valor_medio = prog.preco_medio_milheiro
            programas_data.append(
                {
                    "id": prog.id,
                    "nome": prog.nome,
                    "pontos": total_pontos_prog,
                    "valor_total": (total_pontos_prog / 1000) * float(valor_medio),
                    "valor_medio": valor_medio,
                    "valor_referencia": prog.preco_medio_milheiro,
                    "conta_id": None,
                }
            )

    total_pontos = sum(p["pontos"] for p in programas_data)

    total_emissoes = emissoes.count()
    pontos_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_ref_emissoes = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_pago_emissoes = sum(float(e.valor_pago or 0) for e in emissoes)
    valor_economizado_emissoes = valor_ref_emissoes - valor_pago_emissoes

    qtd_hoteis = hoteis.count()
    valor_ref_hoteis = sum(float(h.valor_referencia or 0) for h in hoteis)
    valor_pago_hoteis = sum(float(h.valor_pago or 0) for h in hoteis)
    valor_economizado_hoteis = valor_ref_hoteis - valor_pago_hoteis

    total_clientes = Cliente.objects.count() if not cliente_id else 1
    total_economizado = valor_economizado_emissoes + valor_economizado_hoteis

    emissoes_programa_qs = (
        emissoes.values("programa__nome")
        .annotate(qtd=Count("id"))
        .order_by("programa__nome")
    )
    emissoes_programa = [
        {"programa": e["programa__nome"] or "N/D", "quantidade": e["qtd"]}
        for e in emissoes_programa_qs
    ]

    return {
        "total_clientes": total_clientes,
        "total_emissoes": total_emissoes,
        "total_pontos": total_pontos,
        "total_economizado": total_economizado,
        "programas": programas_data,
        "emissoes": {
            "qtd": total_emissoes,
            "pontos": pontos_utilizados,
            "valor_referencia": valor_ref_emissoes,
            "valor_pago": valor_pago_emissoes,
            "valor_economizado": valor_economizado_emissoes,
        },
        "hoteis": {
            "qtd": qtd_hoteis,
            "valor_referencia": valor_ref_hoteis,
            "valor_pago": valor_pago_hoteis,
            "valor_economizado": valor_economizado_hoteis,
        },
        "emissoes_programa": emissoes_programa,
    }


@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    cliente_id = request.GET.get("cliente_id")
    data = build_dashboard_metrics(cliente_id)
    clientes = Cliente.objects.all().order_by("usuario__first_name")
    selected_cliente = (
        Cliente.objects.filter(id=cliente_id).first() if cliente_id else None
    )
    context = {**data, "clientes": clientes, "selected_cliente": selected_cliente}
    return render(request, "admin_custom/dashboard.html", context)



def admin_movimentacoes(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    movimentacoes = conta.movimentacoes.all()  # Aqui está o segredo!
    return render(
        request,
        "admin_custom/movimentacoes.html",
        {
            "conta": conta,
            "movimentacoes": movimentacoes,
        },
    )


class NovaMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ["data", "pontos", "valor_pago", "descricao"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.TextInput(attrs={"placeholder": "Descrição"}),
        }


@staff_member_required
def admin_nova_movimentacao(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    if not conta.cliente.ativo:
        return HttpResponse("Cliente inativo", status=403)
    if request.method == "POST":
        form = NovaMovimentacaoForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.conta = conta
            mov.save()
            return redirect("admin_movimentacoes", conta_id=conta.id)
    else:
        form = NovaMovimentacaoForm()
    return render(
        request,
        "admin_custom/nova_movimentacao.html",
        {
            "form": form,
            "conta": conta,
        },
    )


@login_required
@user_passes_test(admin_required)
def api_dashboard(request):
    cliente_id = request.GET.get("cliente_id")
    data = build_dashboard_metrics(cliente_id)
    return JsonResponse(data)


