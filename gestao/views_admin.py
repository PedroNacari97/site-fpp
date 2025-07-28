from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
import csv

from .models import (
    ContaFidelidade,
    Cliente,
    ProgramaFidelidade,
    EmissaoPassagem,
    Aeroporto
)
from .forms import (
    ContaFidelidadeForm,
    ProgramaFidelidadeForm,
    ClienteForm,
    AeroportoForm
)

def admin_required(user):
    return user.is_staff or user.is_superuser

# ---- CRUD ContaFidelidade ----

def listar_contas(request):
    contas = ContaFidelidade.objects.all()
    return render(request, 'admin_custom/contas_list.html', {'contas': contas})

def criar_conta(request):
    if request.method == 'POST':
        form = ContaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_contas')
    else:
        form = ContaFidelidadeForm()
    return render(request, 'admin_custom/contas_form.html', {'form': form})

# ---- CRUD Cliente ----

def criar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_clientes')
    else:
        form = ClienteForm()
    return render(request, 'admin_custom/cliente_form.html', {'form': form})

def editar_cliente(request, cliente_id):
    cliente = Cliente.objects.get(id=cliente_id)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('admin_clientes')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'admin_custom/cliente_form.html', {'form': form})

# ---- Valor Milheiro ----

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_valor_milheiro(request):
    return render(request, "admin_custom/valor_milheiro.html")

# ---- Programas ----

@login_required
@user_passes_test(admin_required)
def admin_programas(request):
    if request.method == "POST":
        form = ProgramaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_programas')
    else:
        form = ProgramaFidelidadeForm()
    programas = ProgramaFidelidade.objects.all().order_by('nome')
    return render(request, "admin_custom/programas.html", {
        "programas": programas,
        "form": form,
    })

@login_required
@user_passes_test(admin_required)
def editar_programa(request, programa_id):
    programa = ProgramaFidelidade.objects.get(id=programa_id)
    if request.method == "POST":
        form = ProgramaFidelidadeForm(request.POST, instance=programa)
        if form.is_valid():
            form.save()
            return redirect('admin_programas')
    else:
        form = ProgramaFidelidadeForm(instance=programa)
    return render(request, "admin_custom/programas_form.html", {"form": form})

# ---- Aeroportos ----

@login_required
@user_passes_test(admin_required)
def admin_aeroportos(request):
    if request.method == 'POST':
        form = AeroportoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_aeroportos')
    else:
        form = AeroportoForm()
    aeroportos = Aeroporto.objects.all()
    return render(request, 'admin_custom/aeroportos.html', {
        'form': form,
        'aeroportos': aeroportos,
    })

@login_required
@user_passes_test(admin_required)
def editar_aeroporto(request, aeroporto_id):
    aeroporto = Aeroporto.objects.get(id=aeroporto_id)
    if request.method == 'POST':
        form = AeroportoForm(request.POST, instance=aeroporto)
        if form.is_valid():
            form.save()
            return redirect('admin_aeroportos')
    else:
        form = AeroportoForm(instance=aeroporto)
    return render(request, 'admin_custom/aeroportos_form.html', {'form': form})

# ---- Dashboard ----

@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    total_clientes = Cliente.objects.count()
    total_contas = ContaFidelidade.objects.count()
    total_emissoes = EmissaoPassagem.objects.count()
    total_pontos = sum([c.saldo_pontos for c in ContaFidelidade.objects.all()])
    return render(request, 'admin_custom/dashboard.html', {
        'total_clientes': total_clientes,
        'total_contas': total_contas,
        'total_emissoes': total_emissoes,
        'total_pontos': total_pontos,
    })

# ---- Lista de Clientes ----

@login_required
@user_passes_test(admin_required)
def admin_clientes(request):
    if 'toggle' in request.GET:
        cli = Cliente.objects.get(id=request.GET['toggle'])
        cli.ativo = not cli.ativo
        cli.save()
        return redirect('admin_clientes')

    busca = request.GET.get("busca", "")
    clientes = Cliente.objects.all().select_related("usuario")
    if busca:
        clientes = clientes.filter(
            Q(usuario__username__icontains=busca) |
            Q(usuario__first_name__icontains=busca)
        )
    paginator = Paginator(clientes, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_custom/clientes.html', {
        'page_obj': page_obj,
        'busca': busca,
        'total_clientes': clientes.count(),
    })

# ---- Lista de Contas Fidelidade ----

@login_required
@user_passes_test(admin_required)
def admin_contas(request):
    busca = request.GET.get("busca", "")
    contas = ContaFidelidade.objects.select_related("cliente__usuario", "programa")
    if busca:
        contas = contas.filter(
            Q(cliente__usuario__username__icontains=busca) |
            Q(cliente__usuario__first_name__icontains=busca)
        )
    paginator = Paginator(contas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_custom/contas.html', {
        'page_obj': page_obj,
        'busca': busca,
        'total_contas': contas.count(),
    })

# ---- Lista de Emissões ----

@login_required
@user_passes_test(admin_required)
def admin_emissoes(request):
    programa_id = request.GET.get("programa")
    cliente_id = request.GET.get("cliente")
    q = request.GET.get("q")
    data_ini = request.GET.get("data_ini")
    data_fim = request.GET.get("data_fim")

    emissoes = EmissaoPassagem.objects.all().select_related(
        'cliente', 'programa', 'aeroporto_partida', 'aeroporto_destino'
    )
    if programa_id:
        emissoes = emissoes.filter(programa_id=programa_id)
    if cliente_id:
        emissoes = emissoes.filter(cliente_id=cliente_id)
    if q:
        emissoes = emissoes.filter(
            Q(aeroporto_partida__sigla__icontains=q) |
            Q(aeroporto_destino__sigla__icontains=q) |
            Q(aeroporto_partida__nome__icontains=q) |
            Q(aeroporto_destino__nome__icontains=q) |
            Q(cliente__usuario__username__icontains=q)
        )
    if data_ini:
        emissoes = emissoes.filter(data_ida__gte=data_ini)
    if data_fim:
        emissoes = emissoes.filter(data_volta__lte=data_fim)

    # Exportar para CSV
    if request.GET.get("export") == "excel":
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="emissoes.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Cliente', 'Programa', 'Aeroporto Partida', 'Aeroporto Destino', 'Data Ida', 'Data Volta',
            'Qtd Passageiros', 'Valor Referência', 'Valor Pago', 'Pontos Usados', 'Economia', 'Detalhes'
        ])
        for e in emissoes:
            writer.writerow([
                str(e.cliente), str(e.programa), e.aeroporto_partida, e.aeroporto_destino,
                e.data_ida, e.data_volta, e.qtd_passageiros, e.valor_referencia, e.valor_pago,
                e.pontos_utilizados, e.economia_obtida, e.detalhes
            ])
        return response

    programas = ProgramaFidelidade.objects.all()
    clientes = Cliente.objects.all()
    return render(request, "admin_custom/emissoes.html", {
        "emissoes": emissoes,
        "programas": programas,
        "clientes": clientes,
        "params": request.GET
    })
