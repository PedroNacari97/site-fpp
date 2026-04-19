from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from gestao.services.empresa_contact import (
    build_empresa_contact_context,
    get_empresa_from_operational_record,
)
from gestao.services.acompanhamento_passagem import build_acompanhamento_summary
from gestao.utils import format_cpf_display


def format_currency_brl(value):
    try:
        amount = Decimal(value or 0)
    except Exception:
        amount = Decimal("0")
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _localtime(value):
    if not value:
        return None
    try:
        return timezone.localtime(value)
    except Exception:
        return value


def _format_datetime(value):
    value = _localtime(value)
    return value.strftime("%d/%m/%Y %H:%M") if value else "A confirmar"


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


def _resolve_company_text(empresa, field_name, fallback):
    value = getattr(empresa, field_name, "") if empresa else ""
    value = (value or "").strip()
    return value or fallback


def _resolve_company_text_list(empresa, field_name, fallback):
    items = empresa.get_text_list(field_name) if empresa else []
    return items or fallback


def _resolve_cta_label(empresa, companhia_nome):
    value = _resolve_company_text(empresa, "emissao_cta_companhia", "")
    if not value:
        return f"Acessar Minhas Viagens - {companhia_nome}"
    try:
        return value.format(companhia=companhia_nome, companhia_nome=companhia_nome)
    except Exception:
        return value


def _get_tipo_cliente_context(emissao):
    cliente = getattr(emissao, "cliente", None)
    tipo = getattr(cliente, "tipo_cliente", "") or "passageiro_direto"
    tipo_operacao = getattr(emissao, "tipo_operacao", "") or "venda_direta"
    mapping = {
        "passageiro_direto": {
            "tone": "blue",
            "label": "Voucher de Emissão",
            "description": "Passageiro direto",
            "hide_referencia": False,
            "hide_economia": False,
            "mostrar_lucro": False,
            "observacao_extra": "",
        },
        "concierge": {
            "tone": "purple",
            "label": "Voucher VIP Concierge",
            "description": "Pontos do próprio cliente (conta gerida)",
            "hide_referencia": False,
            "hide_economia": False,
            "mostrar_lucro": False,
            "observacao_extra": "Emissão realizada com pontos do cliente concierge. A agência repassa apenas as taxas aéreas cabíveis.",
        },
        "conta_administrada": {
            "tone": "gold",
            "label": "Voucher Conta Administrada",
            "description": "Titular cedente da conta para a agência",
            "hide_referencia": False,
            "hide_economia": False,
            "mostrar_lucro": False,
            "observacao_extra": "Emissão operada com conta administrada cedida pelo titular. Contratação de milhas conforme termo vigente.",
        },
        "intermediario": {
            "tone": "green",
            "label": "Voucher de Revenda (B2B)",
            "description": "Emissão para agência revendedora",
            "hide_referencia": True,
            "hide_economia": True,
            "mostrar_lucro": False,
            "observacao_extra": "Documento destinado a agência parceira. Valor de referência e comparativos não são exibidos.",
        },
    }
    info = mapping.get(tipo, mapping["passageiro_direto"])
    info["codigo"] = tipo
    info["tipo_operacao"] = tipo_operacao
    return info


def _get_status_context(emissao):
    if emissao.localizador:
        return {
            "label": "Confirmada",
            "tone": "success",
            "description": "Bilhete emitido com localizador disponivel.",
        }
    return {
        "label": "Pendente",
        "tone": "warning",
        "description": "Aguardando confirmacao final da emissao.",
    }


def _build_passageiros_context(emissao):
    passageiros = []
    for passageiro in emissao.passageiros.all().order_by("categoria", "nome"):
        passageiros.append(
            {
                "nome": passageiro.nome,
                "categoria": passageiro.get_categoria_display(),
                "fields": [
                    {"label": "CPF", "value": format_cpf_display(passageiro.cpf or "", fallback="Nao informado")},
                    {
                        "label": "Data Nascimento",
                        "value": _format_date(passageiro.data_nascimento),
                    },
                    {"label": "RG", "value": passageiro.rg or "Nao informado"},
                    {
                        "label": "Passaporte",
                        "value": passageiro.passaporte or "Nao informado",
                    },
                    {"label": "Email", "value": passageiro.email or "Nao informado"},
                    {
                        "label": "Telefone",
                        "value": passageiro.telefone or "Nao informado",
                    },
                ],
            }
        )
    return passageiros


def _build_flight_context(emissao, empresa):
    companhia = getattr(emissao, "companhia_aerea", None)
    companhia_nome = getattr(companhia, "nome", None) or "Companhia a confirmar"
    companhia_url = getattr(companhia, "site_url", None) or ""
    localizador = emissao.localizador or "A confirmar"
    voos = []

    ida_escalas = list(emissao.escalas.filter(tipo="ida").select_related("aeroporto"))
    ida_duracao = getattr(emissao, "duracao_voo_ida_minutos", 0) or 0
    ida_fuso = getattr(emissao, "fuso_horario_ida", 0) or 0
    ida_chegada = _calculate_arrival(emissao.data_ida, ida_duracao, ida_fuso)
    ida_duration_label = _format_duration_minutes(ida_duracao)
    ida_timezone_label = _format_timezone_offset(ida_fuso)
    ida_hint_parts = ["Voo direto" if not ida_escalas else f"{len(ida_escalas)} escala(s)"]
    if ida_duration_label != "Duracao a confirmar":
        ida_hint_parts.append(ida_duration_label)
    if ida_timezone_label:
        ida_hint_parts.append(ida_timezone_label)

    voos.append(
        {
            "label": "Ida",
            "tone": "outbound",
            "companhia_nome": companhia_nome,
            "companhia_aux": f"PNR {localizador}",
            "origem_label": _format_airport_label(emissao.aeroporto_partida, fallback="Origem a confirmar"),
            "origem_data": _format_date(emissao.data_ida),
            "origem_hora": _format_time(emissao.data_ida),
            "destino_label": _format_airport_label(emissao.aeroporto_destino, fallback="Destino a confirmar"),
            "destino_data": _format_date(ida_chegada or emissao.data_ida),
            "destino_hora": _format_time(ida_chegada) if ida_chegada else "--:--",
            "trajeto_hint": " • ".join(ida_hint_parts),
            "duracao_label": ida_duration_label,
            "timezone_label": ida_timezone_label,
            "cta_url": companhia_url,
            "cta_label": _resolve_cta_label(empresa, companhia_nome),
            "escalas": [
                {
                    "label": _format_airport_label(escala.aeroporto, fallback="Escala"),
                    "hint": str(escala.duracao).split(".")[0] if escala.duracao else "Duracao a confirmar",
                }
                for escala in ida_escalas
            ],
        }
    )

    if emissao.data_volta:
        volta_escalas = list(emissao.escalas.filter(tipo="volta").select_related("aeroporto"))
        volta_duracao = getattr(emissao, "duracao_voo_volta_minutos", 0) or 0
        volta_fuso = getattr(emissao, "fuso_horario_volta", 0) or 0
        volta_chegada = _calculate_arrival(emissao.data_volta, volta_duracao, volta_fuso)
        volta_duration_label = _format_duration_minutes(volta_duracao)
        volta_timezone_label = _format_timezone_offset(volta_fuso)
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
                "companhia_aux": f"PNR {localizador}",
                "origem_label": _format_airport_label(emissao.aeroporto_destino, fallback="Origem a confirmar"),
                "origem_data": _format_date(emissao.data_volta),
                "origem_hora": _format_time(emissao.data_volta),
                "destino_label": _format_airport_label(emissao.aeroporto_partida, fallback="Destino a confirmar"),
                "destino_data": _format_date(volta_chegada or emissao.data_volta),
                "destino_hora": _format_time(volta_chegada) if volta_chegada else "--:--",
                "trajeto_hint": " • ".join(volta_hint_parts),
                "duracao_label": volta_duration_label,
                "timezone_label": volta_timezone_label,
                "cta_url": companhia_url,
                "cta_label": _resolve_cta_label(empresa, companhia_nome),
                "escalas": [
                    {
                        "label": _format_airport_label(escala.aeroporto, fallback="Escala"),
                        "hint": str(escala.duracao).split(".")[0] if escala.duracao else "Duracao a confirmar",
                    }
                    for escala in volta_escalas
                ],
            }
        )

    return voos


def _build_valores_context(emissao, empresa):
    total = (
        emissao.valor_total_final
        or emissao.valor_venda_final
        or emissao.valor_cobrado_cliente
        or emissao.custo_total
        or emissao.valor_referencia
        or 0
    )
    total = Decimal(total or 0)
    taxas = Decimal(emissao.valor_taxas or 0)
    taxa_servico = Decimal(emissao.custo_emissor or 0)
    if taxa_servico <= 0:
        taxa_servico = total - taxas if total > taxas else Decimal(emissao.custo_total or 0)
    if taxa_servico < 0:
        taxa_servico = Decimal("0")

    return {
        "items": [
            {
                "label": "Taxas de embarque",
                "hint": _resolve_company_text(
                    empresa,
                    "emissao_hint_taxa_embarque",
                    "Impostos e taxas aeroportuarias",
                ),
                "value": format_currency_brl(taxas),
            },
            {
                "label": "Taxa de servico",
                "hint": _resolve_company_text(
                    empresa,
                    "emissao_hint_taxa_servico",
                    "Consultoria e emissao",
                ),
                "value": format_currency_brl(taxa_servico),
            },
        ],
        "total_value": format_currency_brl(total),
        "total_hint": _resolve_company_text(
            empresa,
            "emissao_hint_valor_total",
            "Valor final consolidado da emissao",
        ),
    }


def _build_bagagem_context(emissao, empresa):
    bagagem_mao = getattr(emissao, "get_bagagem_mao_display", lambda: "")() or "Sob consulta"
    bagagem_despachada = getattr(emissao, "get_bagagem_despachada_display", lambda: "")() or "Sob consulta"

    return [
        {
            "label": "Bagagem de Mao",
            "value": bagagem_mao,
            "hint": _resolve_company_text(
                empresa,
                "emissao_bagagem_mao_hint",
                "Franquia definida na emissao."
                if getattr(emissao, "bagagem_mao", "")
                else "Confirmar regra da tarifa emitida.",
            ),
        },
        {
            "label": "Bagagem Despachada",
            "value": bagagem_despachada,
            "hint": _resolve_company_text(
                empresa,
                "emissao_bagagem_despachada_hint",
                "Franquia validada para a tarifa emitida."
                if getattr(emissao, "bagagem_despachada", "")
                else "Validar regra da tarifa emitida.",
            ),
        },
    ]


def build_emissao_preview_context(emissao, *, for_pdf=False):
    _for_pdf = for_pdf
    status = _get_status_context(emissao)
    empresa = get_empresa_from_operational_record(emissao)
    localizador = emissao.localizador or "A confirmar"
    acompanhamento = build_acompanhamento_summary(getattr(emissao, "acompanhamento", None))
    observacao_confirmada = _resolve_company_text(
        empresa,
        "emissao_observacao_confirmada",
        "Emissao confirmada. Bilhetes enviados por e-mail. Recomendamos check-in online 24h antes do voo.",
    )
    observacao_pendente = _resolve_company_text(
        empresa,
        "emissao_observacao_pendente",
        "Emissao em analise. Assim que o bilhete for confirmado, os detalhes finais serao enviados.",
    )
    observacao = (
        emissao.detalhes.strip()
        if emissao.detalhes and emissao.detalhes.strip()
        else (observacao_confirmada if emissao.localizador else observacao_pendente)
    )
    orientacoes = _resolve_company_text_list(
        empresa,
        "emissao_orientacoes",
        [
            "Chegue ao aeroporto com 3 horas de antecedencia para voos internacionais.",
            "Faca o check-in online entre 48h e 1h antes do horario do voo.",
            "Apresente documento original com foto e passaporte valido, quando aplicavel.",
            "Verifique as restricoes de bagagem e itens proibidos antes do embarque.",
            "Em caso de duvidas ou necessidade de alteracao, entre em contato com nossa equipe.",
            f"Guarde o localizador ({localizador}) para consultas e alteracoes.",
        ],
    )

    tipo_cliente_info = _get_tipo_cliente_context(emissao)
    if tipo_cliente_info.get("observacao_extra"):
        observacao = f"{tipo_cliente_info['observacao_extra']}\n\n{observacao}".strip()
    return {
        "emissao_numero": f"EM-{emissao.criado_em.year}-{emissao.id:03d}",
        "status": status,
        "tipo_cliente": tipo_cliente_info,
        "created_display": _format_datetime(emissao.criado_em),
        "localizador_display": localizador,
        "pnr_display": localizador,
        "passageiros": _build_passageiros_context(emissao),
        "voos": _build_flight_context(emissao, empresa),
        "bagagem_items": _build_bagagem_context(emissao, empresa),
        "valores": _build_valores_context(emissao, empresa),
        "acompanhamento": acompanhamento,
        "empresa_contato": build_empresa_contact_context(empresa, for_pdf=_for_pdf),
        "observacao_importante": observacao,
        "orientacoes": orientacoes,
    }
