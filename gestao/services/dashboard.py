from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from gestao.models import (
    AlertaViagem,
    Cliente,
    CompanhiaAerea,
    ContaAdministrada,
    ContaFidelidade,
    CotacaoVoo,
    EmissaoPassagem,
    EmissorParceiro,
    ProgramaFidelidade,
)
from gestao.value_utils import build_valor_milheiro_map, get_valor_referencia_from_map


def _filter_emissoes(queryset, *, cliente=None, empresa=None):
    if cliente:
        return queryset.filter(cliente=cliente)
    if empresa:
        return queryset.filter(
            Q(cliente__empresa=empresa) | Q(conta_administrada__empresa=empresa)
        )
    return queryset


def _filter_contas(queryset, *, cliente=None, empresa=None):
    if cliente:
        return queryset.filter(cliente=cliente)
    if empresa:
        return queryset.filter(
            Q(cliente__empresa=empresa) | Q(conta_administrada__empresa=empresa)
        )
    return queryset


def _filter_cotacoes(queryset, *, cliente=None, empresa=None):
    if cliente:
        return queryset.filter(cliente=cliente)
    if empresa:
        return queryset.filter(
            Q(cliente__empresa=empresa) | Q(conta_administrada__empresa=empresa)
        )
    return queryset


def _get_titular_name(emissao: EmissaoPassagem) -> str:
    titular = emissao.cliente or emissao.conta_administrada
    if hasattr(titular, "usuario"):
        return titular.usuario.get_full_name() or titular.usuario.username
    return str(titular)


def _get_cotacao_titular(cotacao):
    titular = cotacao.cliente or cotacao.conta_administrada
    if hasattr(titular, "usuario"):
        return titular.usuario.get_full_name() or titular.usuario.username
    return str(titular)


def _build_programas_info(contas):
    valor_referencia_map = build_valor_milheiro_map()
    programas = {}
    for conta in contas:
        conta_base = conta.conta_saldo()
        pontos = conta_base.saldo_pontos or 0
        valor_medio = float(conta.valor_medio_por_mil or 0)
        valor_referencia = float(
            get_valor_referencia_from_map(conta.programa, valor_referencia_map)
        )
        valor_total = (pontos / 1000) * valor_referencia
        entry = programas.setdefault(
            conta.programa_id,
            {
                "nome": conta.programa.nome,
                "pontos": 0,
                "valor_total": 0,
                "valor_medio_ponderado": 0,
                "valor_medio_base": 0,
                "valor_referencia": valor_referencia,
            },
        )
        entry["pontos"] += pontos
        entry["valor_total"] += valor_total
        entry["valor_medio_ponderado"] += valor_medio * pontos
        entry["valor_medio_base"] += pontos
        entry["valor_referencia"] = valor_referencia

    programas_info = []
    for entry in programas.values():
        pontos = entry["pontos"]
        valor_medio = (
            entry["valor_medio_ponderado"] / entry["valor_medio_base"]
            if entry["valor_medio_base"]
            else 0
        )
        programas_info.append(
            {
                "nome": entry["nome"],
                "pontos": pontos,
                "valor_total": entry["valor_total"],
                "valor_medio": valor_medio,
                "valor_referencia": entry["valor_referencia"],
            }
        )
    return sorted(programas_info, key=lambda item: item["nome"].lower())


def _format_datas_resumo(datas_ida, datas_volta):
    datas_ida = datas_ida or []
    datas_volta = datas_volta or []
    partes = []
    if datas_ida:
        resumo_ida = ", ".join(datas_ida[:2])
        if len(datas_ida) > 2:
            resumo_ida = f"{resumo_ida} (+{len(datas_ida) - 2})"
        partes.append(f"Ida: {resumo_ida}")
    if datas_volta:
        resumo_volta = ", ".join(datas_volta[:2])
        if len(datas_volta) > 2:
            resumo_volta = f"{resumo_volta} (+{len(datas_volta) - 2})"
        partes.append(f"Volta: {resumo_volta}")
    return " • ".join(partes) if partes else "Datas a combinar"


def _build_alert_filters(selected_continente, selected_pais, selected_cidade):
    base_qs = AlertaViagem.objects.filter(ativo=True)
    continentes = list(
        base_qs.values_list("continente", flat=True).distinct().order_by("continente")
    )
    if selected_continente not in continentes:
        selected_continente = None
    paises = []
    if selected_continente:
        paises = list(
            base_qs.filter(continente=selected_continente)
            .values_list("pais", flat=True)
            .distinct()
            .order_by("pais")
        )
    if selected_pais not in paises:
        selected_pais = None
    cidades = []
    if selected_continente and selected_pais:
        cidades = list(
            base_qs.filter(continente=selected_continente, pais=selected_pais)
            .values_list("cidade_destino", flat=True)
            .distinct()
            .order_by("cidade_destino")
        )
    if selected_cidade not in cidades:
        selected_cidade = None

    alertas = base_qs
    if selected_continente:
        alertas = alertas.filter(continente=selected_continente)
    if selected_pais:
        alertas = alertas.filter(pais=selected_pais)
    if selected_cidade:
        alertas = alertas.filter(cidade_destino=selected_cidade)
    else:
        alertas = alertas.none()

    return {
        "continentes": continentes,
        "paises": paises,
        "cidades": cidades,
        "selected_continente": selected_continente,
        "selected_pais": selected_pais,
        "selected_cidade": selected_cidade,
        "alertas": alertas,
    }


def _build_emissao_status(emissao, now_date):
    if emissao.localizador:
        return "Emitido", "emitido"
    if emissao.data_ida.date() < now_date:
        return "Cancelado", "cancelado"
    return "Pendente", "pendente"


def _build_notifications(*, perfil, emissoes_qs, cotacoes_qs, alertas_qs):
    notifications = []
    now = timezone.now()
    now_date = now.date()
    upcoming_limit = (now + timedelta(days=10)).date()
    upcoming_emissoes = (
        emissoes_qs.filter(data_ida__date__gte=now_date, data_ida__date__lte=upcoming_limit)
        .order_by("data_ida")
        .select_related("cliente__usuario", "conta_administrada")
    )[:3]
    if perfil == "cliente":
        action_url = reverse("painel_emissoes")
    else:
        action_url = reverse("admin_emissoes")
    for emissao in upcoming_emissoes:
        days = (emissao.data_ida.date() - now_date).days
        notifications.append(
            {
                "titulo": "Voo próximo",
                "descricao": f"Cliente {_get_titular_name(emissao)} possui voo em {days} dias — entrar em contato",
                "status": "Urgente" if days <= 3 else "Em análise",
                "status_class": "urgent" if days <= 3 else "review",
                "acao_url": action_url,
                "acao_label": "Ver emissões",
            }
        )

    alertas_ativos = list(alertas_qs)
    destinos_alerta = {
        (alerta.destino or "").upper(): alerta for alerta in alertas_ativos if alerta.destino
    }
    cidades_alerta = {
        (alerta.cidade_destino or "").lower(): alerta for alerta in alertas_ativos if alerta.cidade_destino
    }
    interesses = (
        cotacoes_qs.filter(status__in=["pendente", "aceita", "emissao"])
        .select_related("cliente__usuario", "destino")
        .order_by("data_ida")
    )
    for cotacao in interesses:
        if not cotacao.destino:
            continue
        destino_sigla = (cotacao.destino.sigla or "").upper()
        destino_cidade = (cotacao.destino.cidade or "").lower()
        alerta_match = destinos_alerta.get(destino_sigla) or cidades_alerta.get(destino_cidade)
        if not alerta_match:
            continue
        notifications.append(
            {
                "titulo": "Match de alerta com interesse",
                "descricao": f"Novo alerta compatível com interesse do cliente {_get_cotacao_titular(cotacao)}",
                "status": "Informativo",
                "status_class": "info",
                "acao_url": reverse("alerta_passagem_detalhe", args=[alerta_match.id])
                if perfil != "cliente"
                else None,
                "acao_label": "Ver alerta",
            }
        )
        if len(notifications) >= 6:
            break

    expira_em = now_date + timedelta(days=2)
    for alerta in alertas_ativos:
        expiracao = (alerta.criado_em + timedelta(days=30)).date()
        if now_date <= expiracao <= expira_em:
            delta = (expiracao - now_date).days
            notifications.append(
                {
                    "titulo": "Alerta prestes a expirar",
                    "descricao": f"Alerta para {alerta.continente} vence em {delta} dias",
                    "status": "Urgente",
                    "status_class": "urgent",
                    "acao_url": reverse("alerta_passagem_detalhe", args=[alerta.id])
                    if perfil != "cliente"
                    else None,
                    "acao_label": "Ver alerta",
                }
            )
            break

    pendentes = (
        cotacoes_qs.filter(status="emissao", emissao__isnull=True)
        .select_related("cliente__usuario")
        .order_by("criado_em")
    )[:2]
    for cotacao in pendentes:
        notifications.append(
            {
                "titulo": "Emissão pendente",
                "descricao": f"Emissão aguardando retorno do cliente {_get_cotacao_titular(cotacao)}",
                "status": "Em análise",
                "status_class": "review",
                "acao_url": reverse("admin_cotacoes_voo") if perfil != "cliente" else None,
                "acao_label": "Ver cotações",
            }
        )

    return notifications[:6]


def _parse_date(value, fallback):
    if not value:
        return fallback
    try:
        return timezone.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return fallback


MANAGEMENT_FILTER_KEYS = ("data_inicio", "data_fim", "cliente", "emissor", "companhia", "programa", "conta", "status")
MANAGEMENT_FILTER_MULTI_KEYS = ("cliente", "emissor", "companhia", "programa", "conta")
MANAGEMENT_FILTER_SINGLE_KEYS = ("data_inicio", "data_fim", "status")
MANAGEMENT_FILTER_SESSION_KEY = "management_dashboard_filters"


def _selected_ids(request, key):
    return [value for value in request.GET.getlist(key) if value]


def _normalize_management_filters(raw_filters=None):
    raw_filters = raw_filters or {}
    normalized = {}
    for key in MANAGEMENT_FILTER_MULTI_KEYS:
        value = raw_filters.get(key, [])
        if isinstance(value, (list, tuple)):
            normalized[key] = [str(item) for item in value if item not in (None, "")]
        elif value in (None, ""):
            normalized[key] = []
        else:
            normalized[key] = [str(value)]
    for key in MANAGEMENT_FILTER_SINGLE_KEYS:
        value = raw_filters.get(key, "")
        normalized[key] = "" if value in (None, "") else str(value)
    return normalized


def _current_management_filters(request):
    stored_filters = _normalize_management_filters(request.session.get(MANAGEMENT_FILTER_SESSION_KEY, {}))
    has_management_input = any(
        key in request.GET for key in MANAGEMENT_FILTER_KEYS
    ) or any(request.GET.getlist(key) for key in MANAGEMENT_FILTER_MULTI_KEYS)

    if request.GET.get("clear_management_filters") == "1":
        stored_filters = _normalize_management_filters()
        request.session[MANAGEMENT_FILTER_SESSION_KEY] = stored_filters
        request.session.modified = True
        return stored_filters

    if has_management_input:
        current_filters = {}
        for key in MANAGEMENT_FILTER_MULTI_KEYS:
            current_filters[key] = [value for value in request.GET.getlist(key) if value]
        for key in MANAGEMENT_FILTER_SINGLE_KEYS:
            current_filters[key] = request.GET.get(key, "")
        normalized = _normalize_management_filters(current_filters)
        request.session[MANAGEMENT_FILTER_SESSION_KEY] = normalized
        request.session.modified = True
        return normalized

    return stored_filters


def _management_filter_value(filters, key, fallback=""):
    value = filters.get(key, fallback)
    return fallback if value in (None, "") else value


def _management_filter_list(filters, key):
    value = filters.get(key, [])
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item not in (None, "")]
    return []


def _format_money(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_number(value):
    return f"{int(value):,}".replace(",", ".")


def _percent_change(current, previous):
    if not previous:
        return None
    return ((current - previous) / previous) * 100


def _build_kpi(title, value, description, tone="neutral", delta=None):
    return {
        "titulo": title,
        "valor": value,
        "descricao": description,
        "tone": tone,
        "delta": delta,
    }


def _build_query_string(params):
    cleaned = []
    for key, value in params:
        if value in (None, ""):
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                if item not in (None, ""):
                    cleaned.append((key, item))
        else:
            cleaned.append((key, value))
    return urlencode(cleaned, doseq=True)


def _build_management_dashboard(emissoes_qs, request, *, empresa=None):
    today = timezone.localdate()
    active_filters = _current_management_filters(request)
    end_date = _parse_date(_management_filter_value(active_filters, "data_fim"), today)
    start_date = _parse_date(_management_filter_value(active_filters, "data_inicio"), end_date - timedelta(days=29))
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    filtered_base = emissoes_qs.filter(criado_em__date__gte=start_date, criado_em__date__lte=end_date)
    if empresa:
        filtered_base = filtered_base.filter(
            Q(cliente__empresa=empresa) | Q(conta_administrada__empresa=empresa)
        )

    available_emissores = EmissorParceiro.objects.filter(ativo=True)
    available_clientes = Cliente.objects.filter(perfil="cliente", ativo=True)
    available_companhias = CompanhiaAerea.objects.all()
    available_programas = ProgramaFidelidade.objects.all()
    available_contas = ContaAdministrada.objects.filter(ativo=True)
    if empresa:
        available_emissores = available_emissores.filter(empresa=empresa)
        available_clientes = available_clientes.filter(empresa=empresa)
        available_contas = available_contas.filter(empresa=empresa)

    selected_emissores = _management_filter_list(active_filters, "emissor")
    selected_clientes = _management_filter_list(active_filters, "cliente")
    selected_companhias = _management_filter_list(active_filters, "companhia")
    selected_programas = _management_filter_list(active_filters, "programa")
    selected_contas = _management_filter_list(active_filters, "conta")

    if selected_emissores:
        filtered_base = filtered_base.filter(emissor_parceiro_id__in=selected_emissores)
    if selected_clientes:
        filtered_base = filtered_base.filter(cliente_id__in=selected_clientes)
    if selected_companhias:
        filtered_base = filtered_base.filter(companhia_aerea_id__in=selected_companhias)
    if selected_programas:
        filtered_base = filtered_base.filter(programa_id__in=selected_programas)
    if selected_contas:
        filtered_base = filtered_base.filter(conta_administrada_id__in=selected_contas)
    selected_status = _management_filter_value(active_filters, "status")
    if selected_status == "emitido":
        filtered_base = filtered_base.exclude(localizador="").exclude(localizador__isnull=True)
    elif selected_status == "pendente":
        filtered_base = filtered_base.filter(Q(localizador="") | Q(localizador__isnull=True))

    previous_days = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=previous_days - 1)
    previous_qs = emissoes_qs.filter(criado_em__date__gte=prev_start, criado_em__date__lte=prev_end)
    if empresa:
        previous_qs = previous_qs.filter(Q(cliente__empresa=empresa) | Q(conta_administrada__empresa=empresa))
    if selected_emissores:
        previous_qs = previous_qs.filter(emissor_parceiro_id__in=selected_emissores)
    if selected_clientes:
        previous_qs = previous_qs.filter(cliente_id__in=selected_clientes)
    if selected_companhias:
        previous_qs = previous_qs.filter(companhia_aerea_id__in=selected_companhias)
    if selected_programas:
        previous_qs = previous_qs.filter(programa_id__in=selected_programas)
    if selected_contas:
        previous_qs = previous_qs.filter(conta_administrada_id__in=selected_contas)
    if selected_status == "emitido":
        previous_qs = previous_qs.exclude(localizador="").exclude(localizador__isnull=True)
    elif selected_status == "pendente":
        previous_qs = previous_qs.filter(Q(localizador="") | Q(localizador__isnull=True))

    filtered_emissoes = list(filtered_base.select_related(
        "cliente__usuario", "programa", "emissor_parceiro", "companhia_aerea", "conta_administrada"
    ).order_by("criado_em"))
    previous_emissoes = list(previous_qs)

    def total_of(items, attr):
        return float(sum(Decimal(getattr(item, attr) or 0) for item in items))

    revenue = total_of(filtered_emissoes, "valor_total_final") + total_of(filtered_emissoes, "valor_venda_final")
    # avoid double counting when both fields populated
    revenue = float(sum(
        Decimal(item.valor_total_final if item.valor_total_final not in (None, "") else (item.valor_venda_final or 0))
        for item in filtered_emissoes
    ))
    profit = total_of(filtered_emissoes, "lucro")
    miles = float(sum(Decimal(item.pontos_utilizados or 0) for item in filtered_emissoes))
    fees = total_of(filtered_emissoes, "valor_taxas")
    emissions_count = len(filtered_emissoes)
    avg_mile_price = ((total_of(filtered_emissoes, "custo_total") / miles) if miles else 0)

    previous_revenue = float(sum(
        Decimal(item.valor_total_final if item.valor_total_final not in (None, "") else (item.valor_venda_final or 0))
        for item in previous_emissoes
    ))
    previous_profit = total_of(previous_emissoes, "lucro")
    previous_emissions_count = len(previous_emissoes)
    previous_miles = float(sum(Decimal(item.pontos_utilizados or 0) for item in previous_emissoes))
    previous_fees = total_of(previous_emissoes, "valor_taxas")

    kpis = [
        _build_kpi("Receita total", _format_money(revenue), "Valor vendido no período", "revenue", _percent_change(revenue, previous_revenue)),
        _build_kpi("Lucro líquido", _format_money(profit), "Resultado final após custos e taxas", "profit" if profit >= 0 else "loss", _percent_change(profit, previous_profit)),
        _build_kpi("Total de emissões", _format_number(emissions_count), "Quantidade de bilhetes emitidos", "neutral", _percent_change(emissions_count, previous_emissions_count)),
        _build_kpi("Milhas utilizadas", _format_number(miles), "Consumo total de milhas", "neutral", _percent_change(miles, previous_miles)),
        _build_kpi("Total de taxas", _format_money(fees), "Taxas cobradas nas emissões", "neutral", _percent_change(fees, previous_fees)),
    ]

    time_bucket = "month" if previous_days > 90 else "day"
    timeline = defaultdict(lambda: {"receita": 0.0, "lucro": 0.0})
    for emissao in filtered_emissoes:
        key_date = timezone.localtime(emissao.criado_em).date()
        key = key_date.strftime("%Y-%m") if time_bucket == "month" else key_date.isoformat()
        receita_item = Decimal(emissao.valor_total_final if emissao.valor_total_final not in (None, "") else (emissao.valor_venda_final or 0))
        timeline[key]["receita"] += float(receita_item)
        timeline[key]["lucro"] += float(Decimal(emissao.lucro or 0))
    chart_max = max([max(values["receita"], values["lucro"], 0) for values in timeline.values()] or [1])
    timeline_series = [
        {
            "label": key if time_bucket == "month" else timezone.datetime.strptime(key, "%Y-%m-%d").strftime("%d/%m"),
            "receita": values["receita"],
            "lucro": values["lucro"],
            "receita_height": max((values["receita"] / chart_max) * 100, 2) if values["receita"] else 0,
            "lucro_height": max((values["lucro"] / chart_max) * 100, 2) if values["lucro"] else 0,
        }
        for key, values in sorted(timeline.items())
    ]

    programa_stats = defaultdict(lambda: {"programa": "—", "custo": 0.0, "venda": 0.0, "qtd": 0, "lucro": 0.0})
    emissor_stats = defaultdict(lambda: {"nome": "Sem emissor", "receita": 0.0, "lucro": 0.0, "qtd": 0})
    companhia_stats = defaultdict(lambda: {"nome": "Sem companhia", "receita": 0.0, "lucro": 0.0, "qtd": 0})
    margin_alerts = []
    emissions_rows = []
    for emissao in sorted(filtered_emissoes, key=lambda item: item.criado_em, reverse=True):
        receita_item = float(Decimal(emissao.valor_total_final if emissao.valor_total_final not in (None, "") else (emissao.valor_venda_final or 0)))
        custo_item = float(Decimal(emissao.custo_total or 0))
        lucro_item = float(Decimal(emissao.lucro or 0))
        programa_nome = emissao.programa.nome if emissao.programa else "Sem programa"
        emissor_nome = emissao.emissor_parceiro.nome if emissao.emissor_parceiro else "Sem emissor"
        companhia_nome = emissao.companhia_aerea.nome if emissao.companhia_aerea else "Sem companhia"

        p = programa_stats[programa_nome]
        p["programa"] = programa_nome
        p["custo"] += custo_item
        p["venda"] += receita_item
        p["qtd"] += 1
        p["lucro"] += lucro_item

        e = emissor_stats[emissor_nome]
        e["nome"] = emissor_nome
        e["receita"] += receita_item
        e["lucro"] += lucro_item
        e["qtd"] += 1

        c = companhia_stats[companhia_nome]
        c["nome"] = companhia_nome
        c["receita"] += receita_item
        c["lucro"] += lucro_item
        c["qtd"] += 1

        if lucro_item < 0:
            margin_alerts.append({
                "titulo": f"Prejuízo em {programa_nome}",
                "descricao": f"{_get_titular_name(emissao)} gerou {_format_money(lucro_item)} em {timezone.localtime(emissao.criado_em).strftime('%d/%m/%Y')}",
                "tone": "loss",
            })

        emissions_rows.append({
            "cliente": _get_titular_name(emissao),
            "emissor": emissor_nome,
            "programa": programa_nome,
            "companhia": companhia_nome,
            "conta": str(emissao.conta_administrada) if emissao.conta_administrada else "—",
            "receita": _format_money(receita_item),
            "custo": _format_money(custo_item),
            "lucro": _format_money(lucro_item),
            "lucro_tone": "profit" if lucro_item >= 0 else "loss",
            "data": timezone.localtime(emissao.criado_em).strftime("%d/%m/%Y"),
        })

    cost_vs_sale = []
    max_bar = max([max(v["custo"], v["venda"], 0) for v in programa_stats.values()] or [1])
    for values in sorted(programa_stats.values(), key=lambda item: item["lucro"], reverse=True):
        avg_cost = values["custo"] / values["qtd"] if values["qtd"] else 0
        avg_sale = values["venda"] / values["qtd"] if values["qtd"] else 0
        cost_vs_sale.append({
            "programa": values["programa"],
            "custo_medio": _format_money(avg_cost),
            "venda_media": _format_money(avg_sale),
            "margem_media": _format_money(avg_sale - avg_cost),
            "custo_width": max((avg_cost / max_bar) * 100, 4) if avg_cost else 0,
            "venda_width": max((avg_sale / max_bar) * 100, 4) if avg_sale else 0,
        })

    best_programs = [
        {
            "nome": values["programa"],
            "lucro": _format_money(values["lucro"]),
            "receita": _format_money(values["venda"]),
            "qtd": values["qtd"],
        }
        for values in sorted(programa_stats.values(), key=lambda item: item["lucro"], reverse=True)[:5]
    ]
    worst_programs = [
        {
            "nome": values["programa"],
            "lucro": _format_money(values["lucro"]),
            "receita": _format_money(values["venda"]),
            "qtd": values["qtd"],
        }
        for values in sorted(programa_stats.values(), key=lambda item: item["lucro"])[:5]
    ]
    top_emitters = [
        {
            "nome": values["nome"],
            "lucro": _format_money(values["lucro"]),
            "receita": _format_money(values["receita"]),
            "qtd": values["qtd"],
        }
        for values in sorted(emissor_stats.values(), key=lambda item: item["lucro"], reverse=True)[:5]
    ]
    top_airlines = [
        {
            "nome": values["nome"],
            "lucro": _format_money(values["lucro"]),
            "receita": _format_money(values["receita"]),
            "qtd": values["qtd"],
        }
        for values in sorted(companhia_stats.values(), key=lambda item: item["lucro"], reverse=True)[:5]
    ]

    if not margin_alerts:
        margin_alerts.append({
            "titulo": "Operação sem prejuízos no período",
            "descricao": "Nenhuma emissão com lucro negativo foi encontrada dentro dos filtros aplicados.",
            "tone": "profit",
        })

    base_params = []
    if request.GET.get("empresa_id"):
        base_params.append(("empresa_id", request.GET.get("empresa_id")))
    date_params = base_params + [("data_inicio", start_date.isoformat()), ("data_fim", end_date.isoformat())]
    prev_date_params = base_params + [("data_inicio", prev_start.isoformat()), ("data_fim", prev_end.isoformat())]

    filter_options = {
        "emissores": [
            {"id": item.id, "label": item.nome, "selected": str(item.id) in selected_emissores, "query": _build_query_string(date_params + [("emissor", item.id)] + [("emissor", value) for value in selected_emissores if value != str(item.id)] + [("cliente", value) for value in selected_clientes] + [("companhia", value) for value in selected_companhias] + [("programa", value) for value in selected_programas] + [("conta", value) for value in selected_contas])}
            for item in available_emissores.order_by("nome")
        ],
        "clientes": [
            {"id": item.id, "label": str(item), "selected": str(item.id) in selected_clientes, "query": _build_query_string(date_params + [("cliente", item.id)] + [("cliente", value) for value in selected_clientes if value != str(item.id)] + [("emissor", value) for value in selected_emissores] + [("companhia", value) for value in selected_companhias] + [("programa", value) for value in selected_programas] + [("conta", value) for value in selected_contas])}
            for item in available_clientes.order_by("usuario__first_name", "usuario__username")
        ],
        "companhias": [
            {"id": item.id, "label": item.nome, "selected": str(item.id) in selected_companhias, "query": _build_query_string(date_params + [("companhia", item.id)] + [("companhia", value) for value in selected_companhias if value != str(item.id)] + [("emissor", value) for value in selected_emissores] + [("cliente", value) for value in selected_clientes] + [("programa", value) for value in selected_programas] + [("conta", value) for value in selected_contas])}
            for item in available_companhias.order_by("nome")
        ],
        "programas": [
            {"id": item.id, "label": item.nome, "selected": str(item.id) in selected_programas, "query": _build_query_string(date_params + [("programa", item.id)] + [("programa", value) for value in selected_programas if value != str(item.id)] + [("emissor", value) for value in selected_emissores] + [("cliente", value) for value in selected_clientes] + [("companhia", value) for value in selected_companhias] + [("conta", value) for value in selected_contas])}
            for item in available_programas.order_by("nome")
        ],
        "contas": [
            {"id": item.id, "label": item.nome, "selected": str(item.id) in selected_contas, "query": _build_query_string(date_params + [("conta", item.id)] + [("conta", value) for value in selected_contas if value != str(item.id)] + [("emissor", value) for value in selected_emissores] + [("cliente", value) for value in selected_clientes] + [("companhia", value) for value in selected_companhias] + [("programa", value) for value in selected_programas])}
            for item in available_contas.order_by("nome")
        ],
    }

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "previous_period_label": f"{prev_start.strftime('%d/%m')} a {prev_end.strftime('%d/%m')}",
        "kpis": kpis,
        "summary": {
            "total_emissoes": _format_number(emissions_count),
            "receita_total": _format_money(revenue),
            "lucro_total": _format_money(profit),
            "milhas_utilizadas": _format_number(miles),
            "preco_medio_milha": f"R$ {avg_mile_price:,.4f}",
            "total_taxas": _format_money(fees),
        },
        "timeline_series": timeline_series,
        "cost_vs_sale": cost_vs_sale,
        "best_programs": best_programs,
        "worst_programs": worst_programs,
        "top_emitters": top_emitters,
        "top_airlines": top_airlines,
        "margin_alerts": margin_alerts[:4],
        "emissions_rows": emissions_rows[:10],
        "filter_options": filter_options,
        "selected_status": selected_status,
        "filters_summary": {
            "selected_emissores": len(selected_emissores),
            "selected_clientes": len(selected_clientes),
            "selected_companhias": len(selected_companhias),
            "selected_programas": len(selected_programas),
            "selected_contas": len(selected_contas),
        },
        "clear_filters_query": _build_query_string(base_params + [("clear_management_filters", 1)]),
        "previous_period_query": _build_query_string(prev_date_params),
    }


def build_operational_dashboard_context(
    *,
    user,
    request,
    cliente=None,
    empresa=None,
    selected_continente=None,
    selected_pais=None,
    selected_cidade=None,
):
    perfil = "cliente"
    if user.is_superuser:
        perfil = "superadmin"
    else:
        perfil = getattr(getattr(user, "cliente_gestao", None), "perfil", "cliente")

    contas_qs = _filter_contas(
        ContaFidelidade.objects.select_related("programa", "programa__programa_base"),
        cliente=cliente,
        empresa=empresa,
    )
    emissoes_qs = _filter_emissoes(
        EmissaoPassagem.objects.select_related("cliente__usuario", "conta_administrada", "programa"),
        cliente=cliente,
        empresa=empresa,
    )
    cotacoes_qs = _filter_cotacoes(
        CotacaoVoo.objects.select_related("cliente", "destino", "programa", "conta_administrada"),
        cliente=cliente,
        empresa=empresa,
    )

    alert_filter_data = _build_alert_filters(
        selected_continente, selected_pais, selected_cidade
    )
    alertas = alert_filter_data["alertas"]

    programas_info = _build_programas_info(contas_qs)
    now_date = timezone.now().date()
    total_emissoes = emissoes_qs.count()
    total_economizado = sum(float(e.economia_obtida or 0) for e in emissoes_qs)
    total_clientes = 1
    if not cliente:
        clientes_qs = Cliente.objects.filter(perfil="cliente", ativo=True)
        if empresa:
            clientes_qs = clientes_qs.filter(empresa=empresa)
        total_clientes = clientes_qs.count()

    resumo_cards = [
        {
            "titulo": "Total de Clientes",
            "valor": total_clientes,
            "descricao": "Base ativa de clientes",
        },
        {
            "titulo": "Total de Emissões",
            "valor": total_emissoes,
            "descricao": "Passagens emitidas",
        },
        {
            "titulo": "Total Economizado",
            "valor": f"R$ {total_economizado:,.2f}",
            "descricao": "Economia acumulada",
        },
        {
            "titulo": "Alertas Ativos",
            "valor": AlertaViagem.objects.filter(ativo=True).count(),
            "descricao": "Oportunidades disponíveis",
        },
    ]

    emissoes_recentes = []
    for emissao in emissoes_qs.order_by("-criado_em")[:6]:
        status_label, status_class = _build_emissao_status(emissao, now_date)
        emissoes_recentes.append(
            {
                "cliente": _get_titular_name(emissao),
                "programa": emissao.programa.nome if emissao.programa else "—",
                "pontos": emissao.pontos_utilizados or 0,
                "status": status_label,
                "status_class": status_class,
                "data": emissao.criado_em,
            }
        )

    alertas_info = [
        {
            "id": alerta.id,
            "origem": alerta.origem,
            "destino": alerta.destino,
            "classe": alerta.get_classe_display(),
            "programa": alerta.programa_fidelidade,
            "valor_milhas": alerta.valor_milhas or 0,
            "status": "Ativo" if alerta.ativo else "Inativo",
            "datas_resumo": _format_datas_resumo(alerta.datas_ida, alerta.datas_volta),
        }
        for alerta in alertas
    ]

    notifications = _build_notifications(
        perfil=perfil,
        emissoes_qs=emissoes_qs,
        cotacoes_qs=cotacoes_qs,
        alertas_qs=AlertaViagem.objects.filter(ativo=True),
    )

    management_dashboard = _build_management_dashboard(emissoes_qs, request, empresa=empresa)

    return {
        "perfil_dashboard": perfil,
        "resumo_cards": resumo_cards,
        "programas_info": programas_info,
        "alertas_info": alertas_info,
        "alert_filters": alert_filter_data,
        "emissoes_recentes": emissoes_recentes,
        "notifications": notifications,
        "management_dashboard": management_dashboard,
    }
