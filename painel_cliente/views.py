from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from gestao.pdf_emissao import gerar_pdf_emissao
from gestao.models import (
    ContaFidelidade,
    EmissaoPassagem,
    EmissaoHotel,
    ValorMilheiro,
    Cliente,
)
from gestao.models import AcessoClienteLog

# VIEW LOGIN CUSTOMIZADA
def login_custom_view(request):
    error_message = None
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        tipo_acesso = request.POST.get('tipo_acesso')
        if form.is_valid():
            user = form.get_user()
            cliente_obj = Cliente.objects.filter(usuario=user).first()
            if tipo_acesso == 'admin':
                if user.is_staff or user.is_superuser:
                    login(request, user)
                    return redirect('admin_dashboard')  # <-- Aqui, faz o redirect certo!
                else:
                    error_message = "Você não tem permissão de administrador."
            else:  # Cliente comum
                if not (user.is_staff or user.is_superuser):
                    if cliente_obj and not cliente_obj.ativo:
                        error_message = "Sua conta está inativa. Entre em contato com o administrador."
                    else:
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
def build_dashboard_context(user):
    contas = ContaFidelidade.objects.filter(cliente__usuario=user).select_related("programa")
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=user)
    hoteis = EmissaoHotel.objects.filter(cliente__usuario=user)

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
            'valor_referencia': conta.programa.preco_medio_milheiro,
        })

    qtd_emissoes = emissoes.count()
    pontos_totais_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_total_referencia = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    valor_total_economizado = valor_total_referencia - valor_total_pago
    qtd_hoteis = hoteis.count()
    valor_total_hoteis = sum(float(h.valor_pago or 0) for h in hoteis)
    valor_total_hoteis_referencia = sum(float(h.valor_referencia or 0) for h in hoteis)
    valor_total_hoteis_economia = sum(float(h.economia_obtida or (h.valor_referencia - h.valor_pago)) for h in hoteis)

    return {
        'contas_info': contas_info,
        'qtd_emissoes': qtd_emissoes,
        'pontos_totais_utilizados': pontos_totais_utilizados,
        'valor_total_referencia': valor_total_referencia,
        'valor_total_economizado': valor_total_economizado,
        'valor_total_pago': valor_total_pago,
        'qtd_hoteis': qtd_hoteis,
        'valor_total_hoteis': valor_total_hoteis,
        'valor_total_hoteis_referencia': valor_total_hoteis_referencia,
        'valor_total_hoteis_economia': valor_total_hoteis_economia,
    }


@login_required
def dashboard(request):
    cliente = get_object_or_404(Cliente, usuario=request.user)
    if not cliente.ativo:
        return render(request, 'painel_cliente/inativo.html')
    context = build_dashboard_context(request.user)
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
def emissao_pdf(request, emissao_id):
    emissao = get_object_or_404(EmissaoPassagem, id=emissao_id, cliente__usuario=request.user)
    pdf = gerar_pdf_emissao(emissao)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="emissao_{emissao.id}.pdf"'
    return response

@login_required
def painel_hoteis(request):
    emissoes = EmissaoHotel.objects.filter(cliente__usuario=request.user)
    total_pago = sum(float(e.valor_pago or 0) for e in emissoes)
    total_referencia = sum(float(e.valor_referencia or 0) for e in emissoes)
    total_economia = sum(float(e.economia_obtida or (e.valor_referencia - e.valor_pago)) for e in emissoes)
    return render(request, 'painel_cliente/hoteis.html', {
        'emissoes': emissoes,
        'total_pago': total_pago,
        'total_referencia': total_referencia,
        'total_economia': total_economia,
    })

