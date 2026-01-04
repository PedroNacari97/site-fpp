from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from gestao.models import (
    AlertaViagem,
    Cliente,
    ContaFidelidade,
    CotacaoVoo,
    EmissaoPassagem,
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


def build_operational_dashboard_context(
    *,
    user,
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

    return {
        "perfil_dashboard": perfil,
        "resumo_cards": resumo_cards,
        "programas_info": programas_info,
        "alertas_info": alertas_info,
        "alert_filters": alert_filter_data,
        "emissoes_recentes": emissoes_recentes,
        "notifications": notifications,
    }
