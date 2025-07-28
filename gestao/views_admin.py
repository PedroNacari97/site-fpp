from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from .models import ContaFidelidade
from .forms import ContaFidelidadeForm
import csv

from .models import Cliente, ContaFidelidade, ProgramaFidelidade, EmissaoPassagem

def admin_required(user):
    return user.is_staff or user.is_superuser

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

from django.contrib.auth.decorators import login_required, user_passes_test

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_valor_milheiro(request):
    # Apenas uma tela placeholder
    return render(request, "admin_custom/valor_milheiro.html")


@login_required
@user_passes_test(admin_required)
def admin_programas(request):
    # Implemente depois, agora pode só renderizar um template vazio
    return render(request, "admin_custom/programas.html")

# DASHBOARD ADMIN
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

# LISTA DE CLIENTES
@login_required
@user_passes_test(admin_required)
def admin_clientes(request):
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

# LISTA DE CONTAS FIDELIDADE
@login_required
@user_passes_test(admin_required)
def admin_contas(request):
    busca = request.GET.get("busca", "")
    contas = ContaFidelidade.objects.select_related("cliente__usuario", "programa")
    if busca:
        contas = contas.filter(
            Q(cliente__usuario__username__icontains=busca) |
            Q(programa__nome__icontains=busca)
        )
    contas = contas.order_by("-id")
    paginator = Paginator(contas, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "admin_custom/contas.html", {
        "page_obj": page_obj,
        "busca": busca,
        "total_contas": contas.count(),
    })

# GESTÃO DE COTAÇÕES
@login_required
@user_passes_test(admin_required)
def admin_cotacoes(request):
    from gestao.models import ValorMilheiro
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

# LISTA DE EMISSÕES
@login_required
@user_passes_test(admin_required)
def admin_emissoes(request):
    programa_id = request.GET.get("programa")
    cliente_id = request.GET.get("cliente")
    q = request.GET.get("q")
    data_ini = request.GET.get("data_ini")
    data_fim = request.GET.get("data_fim")

    emissoes = EmissaoPassagem.objects.all().select_related('cliente', 'programa')
    if programa_id:
        emissoes = emissoes.filter(programa_id=programa_id)
    if cliente_id:
        emissoes = emissoes.filter(cliente_id=cliente_id)
    if q:
        emissoes = emissoes.filter(
            Q(aeroporto_ida__icontains=q) |
            Q(aeroporto_volta__icontains=q) |
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
            'Cliente', 'Programa', 'Aeroporto Ida', 'Aeroporto Volta', 'Data Ida', 'Data Volta',
            'Qtd Passageiros', 'Valor Referência', 'Valor Pago', 'Pontos Usados', 'Economia', 'Detalhes'
        ])
        for e in emissoes:
            writer.writerow([
                str(e.cliente), str(e.programa), e.aeroporto_ida, e.aeroporto_volta, e.data_ida, e.data_volta,
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
