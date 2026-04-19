from datetime import timedelta
from decimal import Decimal

from gestao.services.empresa_contact import (
    build_empresa_contact_context,
    get_empresa_from_operational_record,
)
from gestao.utils import normalize_cpf


def format_currency_brl(value):
    try:
        amount = Decimal(value or 0)
    except Exception:
        amount = Decimal("0")
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _localtime(value):
    try:
        from django.utils import timezone

        return timezone.localtime(value) if value else None
    except Exception:
        return value


def _format_date(value):
    value = _localtime(value)
    return value.strftime("%d/%m/%Y") if value else "Nao informado"


def _format_time(value):
    value = _localtime(value)
    return value.strftime("%H:%M") if value else "--:--"


def _format_duration_minutes(total_minutes):
    minutes = int(total_minutes or 0)
    if minutes <= 0:
        return "Duracao a confirmar"
    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours:02d}h{remaining_minutes:02d}"


def _format_timezone_offset(offset):
    hours = int(offset or 0)
    if hours == 0:
        return ""
    return f"Fuso {hours:+d}h"


def _calculate_arrival(departure, duration_minutes, timezone_offset):
    if not departure or not duration_minutes:
        return None
    return departure + timedelta(minutes=int(duration_minutes or 0)) + timedelta(hours=int(timezone_offset or 0))


def _format_airport_label(aeroporto, *, fallback):
    if not aeroporto:
        return fallback
    cidade = getattr(aeroporto, "cidade", "") or getattr(aeroporto, "nome", "")
    sigla = getattr(aeroporto, "sigla", "") or "-"
    return f"{cidade} ({sigla})"


def _is_valid_cpf_for_display(value):
    digits = normalize_cpf(value)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    def _digit(partial):
        total = sum(int(number) * weight for number, weight in zip(partial, range(len(partial) + 1, 1, -1)))
        remainder = (total * 10) % 11
        return "0" if remainder == 10 else str(remainder)

    return digits[-2:] == f"{_digit(digits[:9])}{_digit(digits[:10])}"


def _displayable_cpf(value):
    digits = normalize_cpf(value)
    if not digits:
        return ""
    if digits.startswith("9"):
        return ""
    return digits if _is_valid_cpf_for_display(digits) else ""


def _resolve_company_text(empresa, field_name, fallback):
    value = getattr(empresa, field_name, "") if empresa else ""
    value = (value or "").strip()
    return value or fallback


def _resolve_company_text_list(empresa, field_name, fallback):
    items = empresa.get_text_list(field_name) if empresa else []
    return items or fallback


def _build_escalas_context(escalas):
    return [
        {
            "label": _format_airport_label(escala.aeroporto, fallback="Escala"),
            "hint": str(escala.duracao).split(".")[0] if escala.duracao else "Duracao a confirmar",
        }
        for escala in escalas
    ]


def _build_voos_context(cotacao):
    companhia_nome = cotacao.companhia_aerea or "Companhia a confirmar"
    programa_label = cotacao.programa.nome if cotacao.programa else "Programa a confirmar"
    origem_label = _format_airport_label(cotacao.origem, fallback="Origem a confirmar")
    destino_label = _format_airport_label(cotacao.destino, fallback="Destino a confirmar")
    ida_escalas = list(cotacao.escalas.filter(tipo="ida").select_related("aeroporto"))
    ida_chegada = _calculate_arrival(
        cotacao.data_ida,
        getattr(cotacao, "duracao_voo_ida_minutos", 0),
        getattr(cotacao, "fuso_horario_ida", 0),
    )
    ida_duration_label = _format_duration_minutes(getattr(cotacao, "duracao_voo_ida_minutos", 0))
    ida_timezone_label = _format_timezone_offset(getattr(cotacao, "fuso_horario_ida", 0))
    ida_hint_parts = ["Voo direto" if not ida_escalas else f"{len(ida_escalas)} escala(s)"]
    if ida_duration_label != "Duracao a confirmar":
        ida_hint_parts.append(ida_duration_label)
    if ida_timezone_label:
        ida_hint_parts.append(ida_timezone_label)

    voos = [
        {
            "label": "Ida",
            "tone": "outbound",
            "companhia_nome": companhia_nome,
            "companhia_aux": programa_label,
            "origem_label": origem_label,
            "origem_data": _format_date(cotacao.data_ida),
            "origem_hora": _format_time(cotacao.data_ida),
            "destino_label": destino_label,
            "destino_data": _format_date(ida_chegada or cotacao.data_ida),
            "destino_hora": _format_time(ida_chegada),
            "trajeto_hint": " • ".join(ida_hint_parts),
            "duracao_label": ida_duration_label,
            "timezone_label": ida_timezone_label,
            "escalas": _build_escalas_context(ida_escalas),
        }
    ]

    if cotacao.data_volta:
        volta_escalas = list(cotacao.escalas.filter(tipo="volta").select_related("aeroporto"))
        volta_chegada = _calculate_arrival(
            cotacao.data_volta,
            getattr(cotacao, "duracao_voo_volta_minutos", 0),
            getattr(cotacao, "fuso_horario_volta", 0),
        )
        volta_duration_label = _format_duration_minutes(getattr(cotacao, "duracao_voo_volta_minutos", 0))
        volta_timezone_label = _format_timezone_offset(getattr(cotacao, "fuso_horario_volta", 0))
        volta_hint_parts = ["Voo direto" if not volta_escalas else f"{len(volta_escalas)} escala(s)"]
        if volta_duration_label != "Duracao a confirmar":
            volta_hint_parts.append(volta_duration_label)
        if volta_timezone_label:
            volta_hint_parts.append(volta_timezone_label)
        voos.append(
            {
                "label": "Volta",
                "tone": "return",
                "companhia_nome": companhia_nome,
                "companhia_aux": programa_label,
                "origem_label": destino_label,
                "origem_data": _format_date(cotacao.data_volta),
                "origem_hora": _format_time(cotacao.data_volta),
                "destino_label": origem_label,
                "destino_data": _format_date(volta_chegada or cotacao.data_volta),
                "destino_hora": _format_time(volta_chegada),
                "trajeto_hint": " • ".join(volta_hint_parts),
                "duracao_label": volta_duration_label,
                "timezone_label": volta_timezone_label,
                "escalas": _build_escalas_context(volta_escalas),
            }
        )

    return voos


def get_cotacao_titular_info(cotacao):
    titular = cotacao.cliente or cotacao.conta_administrada
    if hasattr(titular, "usuario"):
        return {
            "nome": titular.usuario.get_full_name() or titular.usuario.username,
            "cpf": _displayable_cpf(getattr(titular, "cpf", "")),
            "email": titular.usuario.email or "-",
            "telefone": getattr(titular, "telefone", "") or "-",
        }
    return {
        "nome": getattr(titular, "nome", str(titular)) if titular else "-",
        "cpf": "-",
        "email": "-",
        "telefone": "-",
    }


def build_cotacao_preview_context(cotacao, *, for_pdf=False):
    cotacao.calcular_valores()
    titular = get_cotacao_titular_info(cotacao)
    empresa = get_empresa_from_operational_record(cotacao)
    voos = _build_voos_context(cotacao)
    qtd_passageiros = max(cotacao.qtd_passageiros or 1, 1)
    custo_milhas_unitario = (Decimal(cotacao.milhas or 0) / Decimal("1000")) * Decimal(
        cotacao.valor_milheiro or 0
    )
    taxas_total = Decimal(cotacao.taxas or 0) * qtd_passageiros
    valor_referencia_total = Decimal(cotacao.valor_passagem or 0) * qtd_passageiros
    custo_milhas_total = custo_milhas_unitario * qtd_passageiros
    valor_vista_total = Decimal(cotacao.valor_vista or 0) * qtd_passageiros
    valor_parcelado_total = Decimal(cotacao.valor_parcelado or 0) * qtd_passageiros
    economia_total = Decimal(cotacao.economia or 0) * qtd_passageiros
    parcelas = cotacao.parcelas or 1
    valor_parcela = valor_parcelado_total / Decimal(parcelas) if parcelas else valor_parcelado_total
    observacao_padrao = _resolve_company_text(
        empresa,
        "cotacao_observacao_padrao",
        "Emissao sujeita a disponibilidade de assentos. Valores de taxas podem sofrer alteracao ate a emissao.",
    )
    observacao_importante = (
        cotacao.observacoes.strip()
        if cotacao.observacoes and cotacao.observacoes.strip()
        else observacao_padrao
    )
    condicoes_gerais = _resolve_company_text_list(
        empresa,
        "cotacao_condicoes_gerais",
        [
            f"Esta cotacao tem validade ate {cotacao.validade.strftime('%d/%m/%Y')}."
            if cotacao.validade
            else "A validade desta cotacao sera confirmada no atendimento.",
            "A emissao esta sujeita a disponibilidade de assentos no programa de fidelidade.",
            "As taxas de embarque podem sofrer alteracao ate o momento da emissao.",
            "Regras de alteracao e cancelamento seguem as politicas da companhia aerea.",
            "Recomendamos a contratacao de seguro viagem para maior tranquilidade.",
        ],
    )

    return {
        "cotacao_numero": f"{cotacao.id:03d}/{cotacao.criado_em.year}",
        "titular_info": titular,
        "origem_sigla": getattr(cotacao.origem, "sigla", "-") or "-",
        "origem_nome": str(cotacao.origem) if cotacao.origem else "Origem nao informada",
        "destino_sigla": getattr(cotacao.destino, "sigla", "-") or "-",
        "destino_nome": str(cotacao.destino) if cotacao.destino else "Destino nao informado",
        "tem_volta": bool(cotacao.data_volta),
        "voos": voos,
        "escalas_ida": list(cotacao.escalas.filter(tipo="ida").select_related("aeroporto")),
        "escalas_volta": list(cotacao.escalas.filter(tipo="volta").select_related("aeroporto")),
        "qtd_passageiros_label": f"{qtd_passageiros} PAX",
        "classe_label": cotacao.classe or "Nao informada",
        "companhia_label": cotacao.companhia_aerea or "Nao informada",
        "programa_label": cotacao.programa.nome if cotacao.programa else "Nao informado",
        "valor_items": [
            {
                "label": "Valor de referencia",
                "hint": _resolve_company_text(
                    empresa,
                    "cotacao_hint_valor_referencia",
                    "Valor de mercado usado como comparativo",
                ),
                "value": format_currency_brl(valor_referencia_total),
                "value_raw": valor_referencia_total,
            },
            {
                "label": "Valor encontrado",
                "hint": _resolve_company_text(
                    empresa,
                    "cotacao_hint_valor_encontrado",
                    "Valor da passagem encontrada na cotacao",
                ),
                "value": format_currency_brl(custo_milhas_total),
                "value_raw": custo_milhas_total,
            },
            {
                "label": "Taxa de embarque",
                "hint": _resolve_company_text(
                    empresa,
                    "cotacao_hint_taxa_embarque",
                    "Impostos e taxas aeroportuarias",
                ),
                "value": format_currency_brl(taxas_total),
                "value_raw": taxas_total,
            },
        ],
        "valor_vista_total": format_currency_brl(valor_vista_total),
        "valor_vista_total_raw": valor_vista_total,
        "mostrar_valor_parcelado": bool(getattr(cotacao, "mostrar_valor_parcelado", True)),
        "valor_parcelado_total": format_currency_brl(valor_parcelado_total),
        "valor_parcelado_total_raw": valor_parcelado_total,
        "valor_parcelado_hint": f"{parcelas}x de {format_currency_brl(valor_parcela)}",
        "valor_parcela_raw": valor_parcela,
        "economia_total": format_currency_brl(economia_total),
        "economia_total_raw": economia_total,
        "parcelas": parcelas,
        "valor_total_hint": _resolve_company_text(
            empresa,
            "cotacao_hint_valor_total",
            "Valor final da proposta",
        ),
        "valor_parcelado_descricao": _resolve_company_text(
            empresa,
            "cotacao_hint_valor_parcelado",
            "Condicao parcelada apresentada ao cliente",
        ),
        "economia_hint": _resolve_company_text(
            empresa,
            "cotacao_hint_economia",
            "Diferenca entre a referencia e a proposta",
        ),
        "empresa_contato": build_empresa_contact_context(empresa, for_pdf=for_pdf),
        "observacao_importante": observacao_importante,
        "condicoes_gerais": condicoes_gerais,
    }
