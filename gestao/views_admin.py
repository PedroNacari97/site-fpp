from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from gestao.models import ContaFidelidade, Movimentacao
from django import forms
from django.db import models

from .forms import (
    ContaFidelidadeForm,
    ProgramaFidelidadeForm,
    ClienteForm,
    NovoClienteForm,
    AeroportoForm,
    EmissaoPassagemForm,
)
from django.contrib.auth.models import User
from .models import Cliente, ContaFidelidade, ProgramaFidelidade, EmissaoPassagem, Aeroporto, ValorMilheiro
import csv

def admin_required(user):
    return user.is_staff or user.is_superuser

# --- CONTAS ---
@login_required
@user_passes_test(admin_required)
def listar_contas(request):
    contas = ContaFidelidade.objects.all()
    return render(request, 'admin_custom/contas_list.html', {'contas': contas})

@login_required
@user_passes_test(admin_required)
def criar_conta(request):
    if request.method == 'POST':
        form = ContaFidelidadeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_contas')
    else:
        form = ContaFidelidadeForm()
    return render(request, 'admin_custom/contas_form.html', {'form': form})

@login_required
@user_passes_test(admin_required)
def editar_conta(request, conta_id):
    conta = ContaFidelidade.objects.get(id=conta_id)
    if request.method == 'POST':
        form = ContaFidelidadeForm(request.POST, instance=conta)
        if form.is_valid():
            form.save()
            return redirect('admin_contas')
    else:
        form = ContaFidelidadeForm(instance=conta)
    return render(request, 'admin_custom/contas_form.html', {'form': form})

@login_required
@user_passes_test(admin_required)
def admin_contas(request):
    busca = request.GET.get("busca", "")
    contas = ContaFidelidade.objects.select_related("cliente__usuario", "programa")
    if busca:
        contas = contas.filter(
            Q(cliente__usuario__username__icontains=busca) |
            Q(cliente__usuario__first_name__icontains=busca) |
            Q(programa__nome__icontains=busca)
        )
    paginator = Paginator(contas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_custom/contas.html', {
        'page_obj': page_obj,
        'busca': busca,
        'total_contas': contas.count(),
    })

# --- CLIENTES ---
@login_required
@user_passes_test(admin_required)
def criar_cliente(request):
    if request.method == 'POST':
        form = NovoClienteForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data.get('first_name', ''),
                last_name=form.cleaned_data.get('last_name', ''),
                email=form.cleaned_data.get('email', ''),
            )
            perfil = form.cleaned_data['perfil']
            if perfil in ['admin', 'operador']:
                user.is_staff = True
            if perfil == 'admin':
                user.is_superuser = True
            user.save()
            Cliente.objects.create(
                usuario=user,
                telefone=form.cleaned_data['telefone'],
                data_nascimento=form.cleaned_data['data_nascimento'],
                cpf=form.cleaned_data['cpf'],
                perfil=perfil,
                observacoes=form.cleaned_data['observacoes'],
                ativo=form.cleaned_data['ativo'],
            )
            return redirect('admin_clientes')
    else:
        form = NovoClienteForm()
    return render(request, 'admin_custom/cliente_form.html', {'form': form})

@login_required
@user_passes_test(admin_required)
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

# --- COTAÇÕES ---
@login_required
@user_passes_test(admin_required)
def admin_cotacoes(request):
    if request.method == "POST":
        programa_nome = request.POST.get("programa_nome")
        valor_mercado = request.POST.get("valor_mercado")
        if programa_nome and valor_mercado:
            ValorMilheiro.objects.update_or_create(
                programa_nome=programa_nome,
                defaults={'valor_mercado': valor_mercado}
            )
    cotacoes = ValorMilheiro.objects.all().order_by('programa_nome')
    programas = ProgramaFidelidade.objects.all()
    return render(request, "admin_custom/cotacoes.html", {
        "cotacoes": cotacoes,
        "programas": programas,
    })

# --- PROGRAMAS ---
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

# --- AEROPORTOS ---
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

# --- DASHBOARD ---
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

# --- EMISSÕES ---
@login_required
@user_passes_test(admin_required)
def admin_emissoes(request):
    programa_id = request.GET.get("programa")
    cliente_id = request.GET.get("cliente")
    q = request.GET.get("q")
    data_ini = request.GET.get("data_ini")
    data_fim = request.GET.get("data_fim")

    emissoes = EmissaoPassagem.objects.all().select_related('cliente', 'programa', 'aeroporto_partida', 'aeroporto_destino')
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
                str(e.cliente), str(e.programa), e.aeroporto_partida, e.aeroporto_destino, e.data_ida, e.data_volta,
                e.qtd_passageiros, e.valor_referencia, e.valor_pago, e.pontos_utilizados, e.economia_obtida, e.detalhes
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

@login_required
@user_passes_test(admin_required)
def nova_emissao(request):
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.valor_referencia and emissao.valor_pago:
                emissao.economia_obtida = emissao.valor_referencia - emissao.valor_pago
            emissao.save()
            return redirect('admin_emissoes')
    else:
        form = EmissaoPassagemForm()
    return render(request, "admin_custom/emissoes_form.html", {"form": form})

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
            return redirect('admin_emissoes')
    else:
        form = EmissaoPassagemForm(instance=emissao)
    return render(request, "admin_custom/emissoes_form.html", {"form": form})

@login_required
@user_passes_test(admin_required)
def admin_valor_milheiro(request):
    cotacoes = ValorMilheiro.objects.all().order_by('programa_nome')
    return render(request, "admin_custom/valor_milheiro.html", {"cotacoes": cotacoes})

from django.db import models

def programas_do_cliente(request, cliente_id):
    cliente = Cliente.objects.get(pk=cliente_id)
    contas = ContaFidelidade.objects.filter(cliente=cliente)

    lista_contas = []
    for conta in contas:
        saldo_pontos = conta.movimentacoes.aggregate(total=models.Sum('pontos'))['total'] or 0
        valor_pago = conta.movimentacoes.aggregate(total=models.Sum('valor_pago'))['total'] or 0

        # Preço médio por milheiro
        if saldo_pontos and valor_pago:
            valor_medio_milheiro = (valor_pago / saldo_pontos) * 1000
        else:
            valor_medio_milheiro = 0

        lista_contas.append({
            'conta': conta,
            'saldo_pontos': saldo_pontos,
            'valor_pago': valor_pago,
            'valor_medio_milheiro': valor_medio_milheiro,
        })

    return render(request, 'admin_custom/programas_do_cliente.html', {
        'cliente': cliente,
        'lista_contas': lista_contas,
    })


@login_required
@user_passes_test(admin_required)
def admin_movimentacoes(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    movimentacoes = conta.movimentacoes.all()  # Aqui está o segredo!
    return render(request, "admin_custom/movimentacoes.html", {
        "conta": conta,
        "movimentacoes": movimentacoes,
    })

class NovaMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ['data', 'pontos', 'valor_pago', 'descricao']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'descricao': forms.TextInput(attrs={'placeholder': 'Descrição'}),
        }

@staff_member_required
def admin_nova_movimentacao(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    if request.method == 'POST':
        form = NovaMovimentacaoForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.conta = conta
            mov.save()
            return redirect('admin_movimentacoes', conta_id=conta.id)
    else:
        form = NovaMovimentacaoForm()
    return render(request, 'admin_custom/nova_movimentacao.html', {
        'form': form,
        'conta': conta,
    })
