from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from gestao.models import ContaFidelidade, EmissaoPassagem, ValorMilheiro
from gestao.models import ContaFidelidade, EmissaoPassagem, EmissaoHotel, ValorMilheiro

# VIEW LOGIN CUSTOMIZADA
def login_custom_view(request):
    error_message = None
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        tipo_acesso = request.POST.get('tipo_acesso')
        if form.is_valid():
            user = form.get_user()
            if tipo_acesso == 'admin':
                if user.is_staff or user.is_superuser:
                    login(request, user)
                    return redirect('admin_dashboard')  # <-- Aqui, faz o redirect certo!
                else:
                    error_message = "Você não tem permissão de administrador."
            else:  # Cliente comum
                if not (user.is_staff or user.is_superuser):
                    login(request, user)
                    return redirect('painel_dashboard')
                else:
                    error_message = "Selecione 'Administrador' para acessar o painel admin."
        else:
            error_message = "Usuário ou senha inválidos."
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form, 'error_message': error_message})


# LOGOUT
@login_required
def sair(request):
    logout(request)
    return redirect('login_custom')

# DASHBOARD DO CLIENTE
@login_required
def dashboard(request):
    contas = ContaFidelidade.objects.filter(cliente__usuario=request.user).select_related("programa")
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=request.user)
    valor_milheiros = {v.programa_nome: v.valor_mercado for v in ValorMilheiro.objects.all()}

    contas_info = []
    for conta in contas:
        saldo = conta.saldo_pontos
        valor_medio = conta.valor_medio_por_mil
        valor_total = (saldo / 1000) * valor_medio if saldo else 0
        contas_info.append({
            'id': conta.id,
            'programa': conta.programa.nome,
            'saldo_pontos': saldo,
            'valor_total': valor_total,
            'valor_medio': valor_medio,
            'valor_referencia': valor_milheiros.get(conta.programa.nome, 0),
        })

    qtd_emissoes = emissoes.count()
    pontos_totais_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_total_referencia = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    valor_total_economizado = valor_total_referencia - valor_total_pago

    context = {
        'contas_info': contas_info,
        'qtd_emissoes': qtd_emissoes,
        'pontos_totais_utilizados': pontos_totais_utilizados,
        'valor_total_referencia': valor_total_referencia,
        'valor_total_economizado': valor_total_economizado,
    }
    return render(request, 'painel_cliente/dashboard.html', context)


@login_required
def movimentacoes_programa(request, conta_id):
    conta = get_object_or_404(ContaFidelidade, id=conta_id, cliente__usuario=request.user)
    movimentacoes = conta.movimentacoes.all().order_by('-data')
    return render(request, 'painel_cliente/movimentacoes.html', {
        'movimentacoes': movimentacoes,
        'conta': conta,
    })

# EMISSÕES DETALHADAS
@login_required
def painel_emissoes(request):
    conta = ContaFidelidade.objects.filter(cliente__usuario=request.user).first()
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=request.user)
    total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    return render(request, 'painel_cliente/emissoes.html', {
        'emissoes': emissoes,
        'conta': conta,
        'total_pago': total_pago,
    })


@login_required
def painel_hoteis(request):
    emissoes = EmissaoHotel.objects.filter(cliente__usuario=request.user)
    total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    return render(request, 'painel_cliente/hoteis.html', {
        'emissoes': emissoes,
        'total_pago': total_pago,
    })

