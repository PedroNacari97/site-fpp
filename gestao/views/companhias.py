from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
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


def admin_required(user):
    return user.is_staff or user.is_superuser


from ..forms import CompanhiaAereaForm


@login_required
@user_passes_test(admin_required)
def admin_companhias(request):
    busca = request.GET.get("busca", "")
    companhias = CompanhiaAerea.objects.all()
    if busca:
        companhias = companhias.filter(nome__icontains=busca)
    return render(
        request,
        "admin_custom/companhias.html",
        {"companhias": companhias, "busca": busca},
    )

@login_required
@user_passes_test(admin_required)
def criar_companhia(request):
    if request.method == "POST":
        form = CompanhiaAereaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_companhias")
    else:
        form = CompanhiaAereaForm()
    return render(request, "admin_custom/form_companhia_aerea.html", {"form": form})

@login_required
@user_passes_test(admin_required)
def editar_companhia(request, companhia_id):
    companhia = get_object_or_404(CompanhiaAerea, id=companhia_id)
    if request.method == "POST":
        form = CompanhiaAereaForm(request.POST, instance=companhia)
        if form.is_valid():
            form.save()
            return redirect("admin_companhias")
    else:
        form = CompanhiaAereaForm(instance=companhia)
    return render(request, "admin_custom/form_companhia_aerea.html", {"form": form})


@login_required
def deletar_companhia(request, companhia_id):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Você não tem autorização para deletar este item.")
    else:
        CompanhiaAerea.objects.filter(id=companhia_id).delete()
        messages.success(request, "Companhia aérea deletada com sucesso.")
    return redirect("admin_companhias")
