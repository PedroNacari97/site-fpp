from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .models import ContaFidelidade, EmissaoPassagem, ValorMilheiro, ProgramaFidelidade, MovimentacaoPontos

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
                    return redirect('/admin/')
                else:
                    error_message = "Você não tem permissão de administrador."
            else:
                if not (user.is_staff or user.is_superuser):
                    login(request, user)
                    return redirect('/painel/')
                else:
                    error_message = "Selecione 'Administrador' para acessar o painel admin."
        else:
            error_message = "Usuário ou senha inválidos."
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form, 'error_message': error_message})

@login_required
def painel_dashboard(request):
    contas = ContaFidelidade.objects.filter(cliente__usuario=request.user)
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=request.user)
    valores_milheiro = {vm.programa_nome: vm.valor_mercado for vm in ValorMilheiro.objects.all()}
    
    # Cálculos globais
    valor_total_pago = sum(float(c.valor_total_pago) for c in contas)
    saldo_pontos = sum(c.saldo_pontos for c in contas)
    valor_medio = (valor_total_pago / (saldo_pontos/1000)) if saldo_pontos else 0
    
    # Emissões
    qtd_emissoes = emissoes.count()
    pontos_totais_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_total_referencia = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_total_gasto = sum(float(e.valor_pago or 0) for e in emissoes)
    valor_total_economizado = sum(float(e.economia_obtida or 0) for e in emissoes)

    # Para gráficos, tabela, etc
    historico_programas = []
    for conta in contas:
        programa_nome = conta.programa.nome
        valor_mercado = valores_milheiro.get(programa_nome, 0)
        historico_programas.append({
            'programa': programa_nome,
            'milhas': conta.saldo_pontos,
            'valor_total_pago': conta.valor_total_pago,
            'valor_mercado': valor_mercado,
            'media_mercado': valor_mercado,
            'media_pessoal': (conta.valor_total_pago / (conta.saldo_pontos/1000)) if conta.saldo_pontos else 0,
        })

    context = {
        'contas': contas,
        'saldo_pontos': saldo_pontos,
        'valor_total_pago': valor_total_pago,
        'valor_medio': valor_medio,
        'qtd_emissoes': qtd_emissoes,
        'pontos_totais_utilizados': pontos_totais_utilizados,
        'valor_total_referencia': valor_total_referencia,
        'valor_total_gasto': valor_total_gasto,
        'valor_total_economizado': valor_total_economizado,
        'historico_programas': historico_programas,
        'valores_milheiro': valores_milheiro,
        'emissoes': emissoes,
    }
    return render(request, 'painel_cliente/dashboard.html', context)

@login_required
def painel_emissoes(request):
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=request.user).order_by('-data_ida')
    return render(request, 'painel_cliente/emissoes_detalhadas.html', {'emissoes': emissoes})

@login_required
def painel_movimentacoes(request):
    contas = ContaFidelidade.objects.filter(cliente__usuario=request.user)
    movimentacoes = MovimentacaoPontos.objects.filter(conta__in=contas).order_by('-data')
    return render(request, 'painel_cliente/movimentacoes.html', {'movimentacoes': movimentacoes})

@login_required
def logout_view(request):
    logout(request)
    return redirect('/accounts/login/')
