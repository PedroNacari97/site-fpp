from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.http import HttpResponse

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


# --- PROGRAMAS ---
@login_required
@user_passes_test(admin_required)
def admin_programas(request):
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
@user_passes_test(admin_required)
def criar_programa(request):
    if request.method == "POST":
        form = ProgramaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_programas")
    else:
        form = ProgramaFidelidadeForm()
    return render(request, "admin_custom/form_programa.html", {"form": form})


@login_required
@user_passes_test(admin_required)
def editar_programa(request, programa_id):
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
    if not getattr(request.user, "cliente_gestao", None) or request.user.cliente_gestao.perfil != "admin":
        return HttpResponse("Você não tem permissão para deletar este item")
    ProgramaFidelidade.objects.filter(id=programa_id).delete()
    return redirect("admin_programas")



