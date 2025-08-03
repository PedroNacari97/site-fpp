from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from gestao.pdf_emissao import gerar_pdf_emissao
from gestao.models import (
    ContaFidelidade,
    EmissaoPassagem,
    EmissaoHotel,
    ValorMilheiro,
    Cliente,
    AcessoClienteLog
)

class LoginForm(forms.Form):
    identifier = forms.CharField(label='Usuário/CPF')
    password = forms.CharField(label='Senha', widget=forms.PasswordInput)


def login_custom_view(request):
    error_message = None
    form = LoginForm(request.POST or None)

    mensagens_erro = {
        'invalido': "Usuário ou senha inválidos.",
        'inativo': "Sua conta está inativa. Entre em contato com o administrador.",
        'sem_permissao_admin': "Você não tem permissão de administrador.",
        'sem_permissao_operador': "Você não tem permissão de operador.",
        'sem_permissao_superadmin': "Você não tem permissão de super admin.",
        'acesso_errado': "Selecione 'Administrador' para acessar o painel admin."
    }

    if request.method == 'POST' and form.is_valid():
        identifier = form.cleaned_data['identifier']
        password = form.cleaned_data['password']
        tipo_acesso = request.POST.get('tipo_acesso')
        username = identifier

        cliente_obj = Cliente.objects.filter(cpf=identifier).first() if tipo_acesso == 'cliente' else None
        if cliente_obj and tipo_acesso == 'cliente':
            username = cliente_obj.usuario.username

        user = authenticate(request, username=username, password=password)
        if user:
            cliente_obj = Cliente.objects.filter(usuario=user).first()

            if tipo_acesso == 'admin':
                if user.is_staff and not user.is_superuser and cliente_obj and cliente_obj.perfil == 'admin':
                    login(request, user)
                    return redirect('admin_dashboard')
                error_message = mensagens_erro['sem_permissao_admin']

            elif tipo_acesso == 'operador':
                if user.is_staff and cliente_obj and cliente_obj.perfil == 'operador':
                    login(request, user)
                    return redirect('admin_dashboard')
                error_message = mensagens_erro['sem_permissao_operador']

            elif tipo_acesso == 'superadmin':
                if user.is_superuser:
                    login(request, user)
                    return redirect('admin_dashboard')
                error_message = mensagens_erro['sem_permissao_superadmin']

            else:  # Cliente comum
                if not (user.is_staff or user.is_superuser):
                    if cliente_obj and not cliente_obj.ativo:
                        error_message = mensagens_erro['inativo']
                    else:
                        login(request, user)
                        return redirect('painel_dashboard')
                else:
                    error_message = mensagens_erro['acesso_errado']
        else:
            error_message = mensagens_erro['invalido']

    return render(request, 'registration/login.html', {'form': form, 'error_message': error_message})


@login_required
def sair(request):
    logout(request)
    return redirect('login_custom')


def build_dashboard_context(user):
    contas = ContaFidelidade.objects.filter(cliente__usuario=user).select_related("programa")
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=user)
    hoteis = EmissaoHotel.objects.filter(cliente__usuario=user)

    contas_info = []
    for conta in contas:
        saldo = conta.saldo_pontos or 0
        valor_medio = conta.valor_medio_por_mil or 0
        valor_total = (saldo / 1000) * valor_medio
        contas_info.append({
            'id': conta.id,
            'programa': conta.programa.nome,
            'saldo_pontos': saldo,
            'valor_total': valor_total,
            'valor_medio': valor_medio,
            'valor_referencia': conta.programa.preco_medio_milheiro,
        })

    return {
        'contas_info': contas_info,
        'qtd_emissoes': emissoes.count(),
        'pontos_totais_utilizados': sum(e.pontos_utilizados or 0 for e in emissoes),
        'valor_total_referencia': sum(float(e.valor_referencia or 0) for e in emissoes),
        'valor_total_pago': sum(float(e.valor_pago or 0) for e in emissoes),
        'valor_total_economizado': sum(float(e.valor_referencia or 0) for e in emissoes) - sum(float(e.valor_pago or 0) for e in emissoes),
        'qtd_hoteis': hoteis.count(),
        'valor_total_hoteis': sum(float(h.valor_pago or 0) for h in hoteis),
        'valor_total_hoteis_referencia': sum(float(h.valor_referencia or 0) for h in hoteis),
        'valor_total_hoteis_economia': sum(float(h.economia_obtida or (h.valor_referencia - h.valor_pago)) for h in hoteis),
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
