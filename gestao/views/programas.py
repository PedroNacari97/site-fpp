from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages

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


def verificar_admin(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    return None


# --- PROGRAMAS ---
@login_required
def admin_programas(request):
    if (resp := verificar_admin(request)):
        return resp
    busca = request.GET.get("busca", "")
    programas = ProgramaFidelidade.objects.all().order_by("nome")
    if busca:
        programas = programas.filter(nome__icontains=busca)
    return render(
        request,
        "admin_custom/programas.html",
        {"programas": programas, "busca": busca},
    )


@login_required
def criar_programa(request):
    if (resp := verificar_admin(request)):
        return resp
    if request.method == "POST":
        form = ProgramaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_programas")
    else:
        form = ProgramaFidelidadeForm()
    return render(request, "admin_custom/form_programa.html", {"form": form})


@login_required
def editar_programa(request, programa_id):
    if (resp := verificar_admin(request)):
        return resp
    programa = ProgramaFidelidade.objects.get(id=programa_id)
    if request.method == "POST":
        form = ProgramaFidelidadeForm(request.POST, instance=programa)
        if form.is_valid():
            form.save()
            return redirect("admin_programas")
    else:
        form = ProgramaFidelidadeForm(instance=programa)
    return render(request, "admin_custom/form_programa.html", {"form": form})


@login_required
def deletar_programa(request, programa_id):
    if (resp := verificar_admin(request)):
        return resp
    ProgramaFidelidade.objects.filter(id=programa_id).delete()
    messages.success(request, "Programa deletado com sucesso.")
    return redirect("admin_programas")



