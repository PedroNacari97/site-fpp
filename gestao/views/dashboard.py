from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Cliente,
    ContaAdministrada,
    ContaFidelidade,
    EmissaoHotel,
    EmissaoPassagem,
    EmissorParceiro,
    Empresa,
    CotacaoVoo,
    Movimentacao,
    Passageiro,
)
from ..services.dashboard import (
    build_operational_dashboard_context,
    _current_management_filters,
    _management_filter_list,
    _management_filter_value,
)
from ..value_utils import build_valor_milheiro_map, get_valor_referencia_from_map
from .permissions import require_admin_or_operator


def _default_metrics(total_titulares):
    return {
        "total_titulares": total_titulares,
        "total_emissoes": 0,
        "total_pontos": 0,
        "total_economizado": 0,
        "programas": [],
        "emissoes": {
            "qtd": 0,
            "pontos": 0,
            "valor_referencia": 0,
            "valor_taxas": 0,
            "custo_total": 0,
            "valor_economizado": 0,
        },
        "hoteis": {"qtd": 0, "valor_referencia": 0, "valor_pago": 0, "valor_economizado": 0},
        "emissoes_programa": [],
        "parceiros": {"lucro": 0, "vendas": 0, "milhas": 0, "valor_pago": 0, "valor_medio_milheiro": 0},
        "parceiros_cards": [],
    }


def build_dashboard_metrics(view_type="clientes", entity_id=None):
    clientes_qs = Cliente.objects.filter(perfil="cliente", ativo=True)
    contas_qs = ContaAdministrada.objects.filter(ativo=True)
    parceiros_qs = EmissorParceiro.objects.filter(ativo=True)

    contas = ContaFidelidade.objects.select_related(
        "programa", "programa__programa_base"
    )
    emissoes = EmissaoPassagem.objects.all()
    hoteis = EmissaoHotel.objects.all()
    parceiros_cards = []

    if view_type == "clientes":
        contas = contas.filter(cliente__perfil="cliente", cliente__ativo=True, conta_administrada__isnull=True)
        emissoes = emissoes.filter(cliente__perfil="cliente", cliente__ativo=True)
        hoteis = hoteis.filter(cliente__perfil="cliente", cliente__ativo=True)
        if entity_id:
            cliente = clientes_qs.filter(id=entity_id).first()
            if not cliente:
                return _default_metrics(clientes_qs.count())
            contas = contas.filter(cliente_id=entity_id)
            emissoes = emissoes.filter(cliente_id=entity_id)
            hoteis = hoteis.filter(cliente_id=entity_id)
    elif view_type == "contas":
        contas = contas.filter(conta_administrada__isnull=False, conta_administrada__ativo=True)
        emissoes = emissoes.filter(conta_administrada__isnull=False)
        hoteis = hoteis.none()
        if entity_id:
            conta = contas_qs.filter(id=entity_id).first()
            if not conta:
                return _default_metrics(contas_qs.count())
            contas = contas.filter(conta_administrada_id=entity_id)
            emissoes = emissoes.filter(conta_administrada_id=entity_id)
    else:
        emissoes = emissoes.filter(emissor_parceiro__isnull=False)
        hoteis = hoteis.none()
        contas = contas.none()
        if entity_id:
            emissor = parceiros_qs.filter(id=entity_id).first()
            if not emissor:
                return _default_metrics(parceiros_qs.count())
            emissoes = emissoes.filter(emissor_parceiro_id=entity_id)
        emissoes_por_parceiro = {}
        for emissao in emissoes.select_related("emissor_parceiro"):
            emissor = emissao.emissor_parceiro
            if not emissor:
                continue
            entry = emissoes_por_parceiro.setdefault(
                emissor.id,
                {
                    "id": emissor.id,
                    "nome": emissor.nome,
                    "total_emissoes": 0,
                    "total_milhas": Decimal("0"),
                    "valor_pago": Decimal("0"),
                    "valor_medio_milheiro": Decimal("0"),
                },
            )
            entry["total_emissoes"] += 1
            entry["total_milhas"] += Decimal(emissao.pontos_utilizados or 0)
            entry["valor_pago"] += Decimal(emissao.custo_total or 0)
        for entry in emissoes_por_parceiro.values():
            if entry["total_milhas"]:
                entry["valor_medio_milheiro"] = entry["valor_pago"] / entry["total_milhas"]
        parceiros_cards = list(emissoes_por_parceiro.values())

    programas_data = []
    total_pontos = 0
    if view_type in {"clientes", "contas"}:
        valor_referencia_map = build_valor_milheiro_map()
        total_pontos_unicos = {}
        for conta in contas:
            conta_base = conta.conta_saldo()
            pontos = conta_base.saldo_pontos
            valor_medio_programa = float(conta.valor_medio_por_mil or 0)
            valor_referencia_programa = float(
                get_valor_referencia_from_map(conta.programa, valor_referencia_map)
            )
            programas_data.append(
                {
                    "id": conta.programa.id,
                    "nome": conta.programa.nome,
                    "pontos": pontos,
                    "valor_total": (Decimal(pontos) / Decimal(1000))
                    * Decimal(valor_referencia_programa),
                    "valor_medio": valor_medio_programa,
                    "valor_referencia": valor_referencia_programa,
                    "conta_id": conta.id,
                    "conta_base_id": conta_base.id,
                }
            )
            total_pontos_unicos[conta_base.id] = pontos
        total_pontos = sum(total_pontos_unicos.values())

    total_emissoes = emissoes.count()
    pontos_utilizados = sum(e.pontos_utilizados or 0 for e in emissoes)
    valor_ref_emissoes = sum(float(e.valor_referencia or 0) for e in emissoes)
    valor_taxas_emissoes = sum(float(e.valor_taxas or 0) for e in emissoes)
    custo_total_emissoes = sum(float(e.custo_total or 0) for e in emissoes)
    valor_economizado_emissoes = sum(float(e.economia_obtida or 0) for e in emissoes)
    total_pago_parceiro = Decimal("0")
    total_lucro = Decimal("0")
    total_vendas = Decimal("0")
    valor_medio_milheiro = Decimal("0")
    if view_type == "parceiros":
        total_milhas = Decimal("0")
        for emissao in emissoes:
            pontos = Decimal(emissao.pontos_utilizados or 0)
            total_pago_parceiro += Decimal(emissao.custo_total or 0)
            total_milhas += pontos
            valor_total_final = getattr(emissao, "valor_total_final", None)
            if valor_total_final not in (None, ""):
                total_vendas += Decimal(valor_total_final or 0)
            elif emissao.valor_venda_final is not None:
                total_vendas += Decimal(emissao.valor_venda_final or 0)
            total_lucro += Decimal(emissao.lucro or 0)
        if total_milhas:
            valor_medio_milheiro = total_pago_parceiro / total_milhas

    qtd_hoteis = hoteis.count()
    valor_ref_hoteis = sum(float(h.valor_referencia or 0) for h in hoteis)
    valor_pago_hoteis = sum(float(h.valor_pago or 0) for h in hoteis)
    valor_economizado_hoteis = valor_ref_hoteis - valor_pago_hoteis

    total_titulares = {
        "clientes": clientes_qs.count(),
        "contas": contas_qs.count(),
        "parceiros": parceiros_qs.count(),
    }.get(view_type, 0)
    if entity_id:
        total_titulares = 1
    total_economizado = valor_economizado_emissoes + valor_economizado_hoteis
    if view_type != "parceiros":
        total_vendas = sum(
            float(
                getattr(e, "valor_total_final", None)
                if getattr(e, "valor_total_final", None) not in (None, "")
                else (e.valor_venda_final or 0)
            )
            for e in emissoes
        )
        total_lucro = sum(float(e.lucro or 0) for e in emissoes)

    emissoes_programa_qs = (
        emissoes.values("programa__nome").annotate(qtd=Count("id")).order_by("programa__nome")
    )
    emissoes_programa = [
        {"programa": e["programa__nome"] or "N/D", "quantidade": e["qtd"]}
        for e in emissoes_programa_qs
    ]

    return {
        "total_titulares": total_titulares,
        "total_emissoes": total_emissoes,
        "total_pontos": total_pontos,
        "total_economizado": total_economizado,
        "programas": programas_data,
        "emissoes": {
            "qtd": total_emissoes,
            "pontos": pontos_utilizados,
            "valor_referencia": valor_ref_emissoes,
            "valor_taxas": valor_taxas_emissoes,
            "custo_total": custo_total_emissoes,
            "valor_economizado": valor_economizado_emissoes,
        },
        "hoteis": {
            "qtd": qtd_hoteis,
            "valor_referencia": valor_ref_hoteis,
            "valor_pago": valor_pago_hoteis,
            "valor_economizado": valor_economizado_hoteis,
        },
        "emissoes_programa": emissoes_programa,
        "parceiros": {
            "lucro": total_lucro,
            "vendas": total_vendas,
            "milhas": pontos_utilizados,
            "valor_pago": total_pago_parceiro,
            "valor_medio_milheiro": valor_medio_milheiro,
        },
        "parceiros_cards": parceiros_cards,
    }


def _build_home_context(*, user, empresa=None, request=None):
    active_filters = _current_management_filters(request) if request else {}
    today = timezone.localdate()
    start_date = today - timedelta(days=29)
    if request:
        start_date = timezone.datetime.strptime(_management_filter_value(active_filters, "data_inicio"), "%Y-%m-%d").date() if _management_filter_value(active_filters, "data_inicio") else start_date
        today = timezone.datetime.strptime(_management_filter_value(active_filters, "data_fim"), "%Y-%m-%d").date() if _management_filter_value(active_filters, "data_fim") else today
    selected_emissores = _management_filter_list(active_filters, "emissor") if request else []
    selected_clientes = _management_filter_list(active_filters, "cliente") if request else []
    selected_companhias = _management_filter_list(active_filters, "companhia") if request else []
    selected_programas = _management_filter_list(active_filters, "programa") if request else []
    selected_contas = _management_filter_list(active_filters, "conta") if request else []
    emissoes_qs = EmissaoPassagem.objects.select_related("cliente__usuario", "companhia_aerea", "aeroporto_partida", "aeroporto_destino")
    cotacoes_qs = CotacaoVoo.objects.select_related("cliente__usuario", "origem", "destino", "programa")
    contas_qs = ContaAdministrada.objects.all()
    clientes_qs = Cliente.objects.filter(perfil="cliente")
    movimentacoes_qs = Movimentacao.objects.select_related("conta", "conta__programa", "conta__cliente__usuario")
    if empresa:
        emissoes_qs = emissoes_qs.filter(Q(cliente__empresa=empresa) | Q(conta_administrada__empresa=empresa))
        cotacoes_qs = cotacoes_qs.filter(Q(cliente__empresa=empresa) | Q(conta_administrada__empresa=empresa))
        contas_qs = contas_qs.filter(empresa=empresa)
        clientes_qs = clientes_qs.filter(empresa=empresa)
        movimentacoes_qs = movimentacoes_qs.filter(Q(conta__cliente__empresa=empresa) | Q(conta__conta_administrada__empresa=empresa))


    if selected_emissores:
        emissoes_qs = emissoes_qs.filter(emissor_parceiro_id__in=selected_emissores)
    if selected_clientes:
        emissoes_qs = emissoes_qs.filter(cliente_id__in=selected_clientes)
        cotacoes_qs = cotacoes_qs.filter(cliente_id__in=selected_clientes)
        clientes_qs = clientes_qs.filter(id__in=selected_clientes)
    if selected_companhias:
        emissoes_qs = emissoes_qs.filter(companhia_aerea_id__in=selected_companhias)
    if selected_programas:
        emissoes_qs = emissoes_qs.filter(programa_id__in=selected_programas)
        cotacoes_qs = cotacoes_qs.filter(programa_id__in=selected_programas)
    if selected_contas:
        emissoes_qs = emissoes_qs.filter(conta_administrada_id__in=selected_contas)
        cotacoes_qs = cotacoes_qs.filter(conta_administrada_id__in=selected_contas)
        contas_qs = contas_qs.filter(id__in=selected_contas)
    selected_status = _management_filter_value(active_filters, "status") if request else ""
    if selected_status == "emitido":
        emissoes_qs = emissoes_qs.exclude(localizador="").exclude(localizador__isnull=True)
    elif selected_status == "pendente":
        emissoes_qs = emissoes_qs.filter(Q(localizador="") | Q(localizador__isnull=True))

    emissoes_hoje = emissoes_qs.filter(criado_em__date=today)
    emissoes_periodo = emissoes_qs.filter(criado_em__date__gte=start_date, criado_em__date__lte=today)
    lucro_hoje = sum(float(e.lucro or 0) for e in emissoes_hoje)
    lucro_periodo = sum(float(e.lucro or 0) for e in emissoes_periodo)
    milhas_periodo = sum(int(e.pontos_utilizados or 0) for e in emissoes_periodo)
    receita_periodo = sum(float((e.valor_total_final if e.valor_total_final not in (None, '') else (e.valor_venda_final or 0)) or 0) for e in emissoes_periodo)
    custo_periodo = sum(float(e.custo_total or 0) for e in emissoes_periodo)
    ticket_medio = (receita_periodo / emissoes_periodo.count()) if emissoes_periodo.count() else 0

    alerts = []
    low_balance = []
    for conta in ContaFidelidade.objects.select_related("programa", "cliente__usuario", "conta_administrada")[:30]:
        saldo = getattr(conta.conta_saldo(), 'saldo_pontos', 0)
        if saldo and saldo < 10000:
            titular = conta.cliente or conta.conta_administrada
            low_balance.append({
                'titulo': 'Conta com saldo baixo',
                'descricao': f'{titular} em {conta.programa.nome} com {saldo} pontos',
                'url': reverse("admin_alertas_passagens"),
                'tone': 'yellow',
            })
            if len(low_balance) >= 2:
                break
    alerts.extend(low_balance)
    loss_emission = emissoes_periodo.filter(lucro__lt=0).first()
    if loss_emission:
        alerts.append({'titulo': 'Emissão com prejuízo', 'descricao': str(loss_emission), 'url': reverse("admin_alertas_passagens"), 'tone': 'red'})
    upcoming = emissoes_qs.filter(data_ida__date__gte=today).order_by('data_ida')[:3]
    if upcoming:
        alerts.append({'titulo': 'Embarques próximos', 'descricao': f'{upcoming.count()} embarques previstos para os próximos dias', 'url': reverse("admin_emissoes"), 'tone': 'blue'})
    pending_quote = cotacoes_qs.filter(status='pendente').first()
    if pending_quote:
        alerts.append({'titulo': 'Cotações sem retorno', 'descricao': str(pending_quote), 'url': reverse("admin_alertas_passagens"), 'tone': 'purple'})

    quick_actions = [
        {'label': 'Nova emissão', 'url': 'admin_nova_emissao'},
        {'label': 'Nova cotação', 'url': 'admin_nova_cotacao_voo'},
        {'label': 'Novo cliente', 'url': 'admin_novo_cliente'},
        {'label': 'Nova conta fidelidade', 'url': 'admin_nova_conta'},
        {'label': 'Nova conta administrativa', 'url': 'admin_nova_conta_administrada'},
        {'label': 'Emissões do dia', 'url': 'admin_emissoes'},
        {'label': 'Auditorias', 'url': 'admin_auditoria'},
    ]

    latest_movements = []
    for emissao in emissoes_qs.order_by('-criado_em')[:4]:
        latest_movements.append({'tipo': 'Emissão', 'titulo': str(emissao), 'meta': timezone.localtime(emissao.criado_em).strftime('%d/%m/%Y %H:%M')})
    for cotacao in cotacoes_qs.order_by('-criado_em')[:3]:
        latest_movements.append({'tipo': 'Cotação', 'titulo': str(cotacao), 'meta': timezone.localtime(cotacao.criado_em).strftime('%d/%m/%Y %H:%M')})
    for mov in movimentacoes_qs.order_by('-data')[:3]:
        latest_movements.append({'tipo': 'Pontos', 'titulo': mov.descricao, 'meta': mov.data.strftime('%d/%m/%Y')})
    latest_movements = sorted(latest_movements, key=lambda item: item['meta'], reverse=True)[:8]

    upcoming_boardings = [
        {
            'cliente': (e.cliente or e.conta_administrada),
            'rota': f"{getattr(e.aeroporto_partida, 'sigla', '—')} → {getattr(e.aeroporto_destino, 'sigla', '—')}",
            'data': e.data_ida.strftime('%d/%m/%Y %H:%M') if e.data_ida else '—',
            'companhia': getattr(e.companhia_aerea, 'nome', '—'),
            'localizador': e.localizador or '—',
            'status': 'Emitido' if e.localizador else 'Pendente',
            'url': reverse("admin_emissoes"),
        }
        for e in upcoming
    ]

    return {
        'home_period_label': f'{start_date.strftime("%d/%m/%Y")} a {today.strftime("%d/%m/%Y")}',
        'home_kpis': [
            {'label': 'Emissões hoje', 'value': emissoes_hoje.count()},
            {'label': 'Emissões no período', 'value': emissoes_periodo.count()},
            {'label': 'Lucro hoje', 'value': f'R$ {lucro_hoje:,.2f}'},
            {'label': 'Lucro no período', 'value': f'R$ {lucro_periodo:,.2f}'},
            {'label': 'Milhas no período', 'value': milhas_periodo},
            {'label': 'Clientes ativos', 'value': clientes_qs.filter(ativo=True).count()},
            {'label': 'Contas administrativas ativas', 'value': contas_qs.filter(ativo=True).count()},
            {'label': 'Cotações pendentes', 'value': cotacoes_qs.filter(status='pendente').count()},
        ],
        'home_alerts': alerts,
        'home_actions': quick_actions,
        'home_latest_movements': latest_movements,
        'home_upcoming_boardings': upcoming_boardings,
        'home_financial': {
            'receita': f'R$ {receita_periodo:,.2f}',
            'custo': f'R$ {custo_periodo:,.2f}',
            'lucro': f'R$ {lucro_periodo:,.2f}',
            'ticket_medio': f'R$ {ticket_medio:,.2f}',
        },
        'home_counts': {
            'contas_fidelidade': ContaFidelidade.objects.count(),
            'passageiros': Passageiro.objects.count(),
            'viagens': emissoes_periodo.count(),
            'clientes_ativos': clientes_qs.filter(ativo=True).count(),
            'contas_administrativas_ativas': contas_qs.filter(ativo=True).count(),
        },
    }


@login_required
def admin_home(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    empresa = None
    empresa_id = request.GET.get("empresa_id")
    empresas = None
    if request.user.is_superuser:
        empresas = Empresa.objects.all().order_by("nome")
        if empresa_id:
            empresa = empresas.filter(id=empresa_id).first()
    else:
        empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)

    context = build_operational_dashboard_context(
        user=request.user,
        request=request,
        empresa=empresa,
        selected_continente=request.GET.get("continente"),
        selected_pais=request.GET.get("pais"),
        selected_cidade=request.GET.get("cidade"),
    )
    context.update(
        {
            "dashboard_base": "admin_custom/base_admin.html",
            "dashboard_title": "Dashboard Operacional",
            "dashboard_subtitle": "Visão operacional com alertas, emissões e ações prioritárias.",
            "menu_ativo": "home",
            "empresas": empresas,
            "empresa_selecionada": empresa,
            "empresa_id": empresa_id,
        }
    )
    context.update(_build_home_context(user=request.user, empresa=empresa, request=request))
    return render(request, "admin_custom/home.html", context)


@login_required
def admin_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    empresa = None
    empresa_id = request.GET.get("empresa_id")
    empresas = None
    if request.user.is_superuser:
        empresas = Empresa.objects.all().order_by("nome")
        if empresa_id:
            empresa = empresas.filter(id=empresa_id).first()
    else:
        empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)

    context = build_operational_dashboard_context(
        user=request.user,
        request=request,
        empresa=empresa,
        selected_continente=request.GET.get("continente"),
        selected_pais=request.GET.get("pais"),
        selected_cidade=request.GET.get("cidade"),
    )
    context.update(
        {
            "dashboard_base": "admin_custom/base_admin.html",
            "dashboard_title": "Dashboard Operacional",
            "dashboard_subtitle": "Visão operacional com alertas, emissões e ações prioritárias.",
            "menu_ativo": "dashboard",
            "empresas": empresas,
            "empresa_selecionada": empresa,
            "empresa_id": empresa_id,
        }
    )
    context.update(_build_home_context(user=request.user, empresa=empresa, request=request))
    return render(request, "admin_custom/dashboard.html", context)


@login_required
def api_dashboard(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    view_type = request.GET.get("view", "clientes")
    entity_id = request.GET.get("cliente_id") if view_type == "clientes" else request.GET.get("conta_id") if view_type == "contas" else request.GET.get("emissor_id")
    data = build_dashboard_metrics(view_type, entity_id)
    return JsonResponse(data)
