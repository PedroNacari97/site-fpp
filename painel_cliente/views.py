from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from gestao.models import ContaFidelidade, EmissaoPassagem

# Login customizado na raiz
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

# Dashboard do cliente
@login_required
def dashboard(request):
    conta = ContaFidelidade.objects.filter(cliente__usuario=request.user).first()
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=request.user) if conta else []
    qtd_emissoes = emissoes.count()
    pontos_totais_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_total_referencia = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_total_gasto = sum(float(e.valor_pago or 0) for e in emissoes)
    valor_total_economizado = sum(float(e.economia_obtida or 0) for e in emissoes)
    context = {
        'conta': conta,
        'saldo_pontos': conta.saldo_pontos if conta else 0,
        'valor_total_pago': conta.valor_total_pago if conta else 0,
        'valor_medio': (conta.valor_total_pago / (conta.saldo_pontos / 1000)) if conta and conta.saldo_pontos > 0 else 0,
        'qtd_emissoes': qtd_emissoes,
        'pontos_totais_utilizados': pontos_totais_utilizados,
        'valor_total_referencia': valor_total_referencia,
        'valor_total_gasto': valor_total_gasto,
        'valor_total_economizado': valor_total_economizado,
    }
    return render(request, 'painel_cliente/dashboard.html', context)

# Emissões detalhadas
@login_required
def emissoes(request):
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=request.user)
    return render(request, 'painel_cliente/emissoes.html', {'emissoes': emissoes})

