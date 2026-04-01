from decimal import Decimal

from django.utils import timezone

from gestao.services.empresa_contact import (
    build_empresa_contact_context,
    get_empresa_from_operational_record,
)


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


def _format_airport_label(aeroporto, *, fallback):
    if not aeroporto:
        return fallback
    cidade = getattr(aeroporto, "cidade", "") or getattr(aeroporto, "nome", "")
    sigla = getattr(aeroporto, "sigla", "") or "-"
    return f"{cidade} ({sigla})"


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
                    {"label": "CPF", "value": passageiro.cpf or "Nao informado"},
                    {
                        "label": "Data Nascimento",
                        "value": _format_date(passageiro.data_nascimento),
                    },
                    {"label": "RG", "value": passageiro.rg or "Nao informado"},
                    {
                        "label": "Passaporte",
                        "value": passageiro.passaporte or "Nao informado",
                    },
                ],
            }
        )
    return passageiros


def _build_flight_context(emissao):
    companhia = getattr(emissao, "companhia_aerea", None)
    companhia_nome = getattr(companhia, "nome", None) or "Companhia a confirmar"
    companhia_url = getattr(companhia, "site_url", None) or ""
    localizador = emissao.localizador or "A confirmar"
    voos = []

    ida_escalas = list(emissao.escalas.filter(tipo="ida").select_related("aeroporto"))
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
            "destino_data": _format_date(emissao.data_ida),
            "destino_hora": "--:--",
            "trajeto_hint": "Voo direto" if not ida_escalas else f"{len(ida_escalas)} escala(s)",
            "cta_url": companhia_url,
            "cta_label": f"Acessar Minhas Viagens - {companhia_nome}",
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
                "destino_data": _format_date(emissao.data_volta),
                "destino_hora": "--:--",
                "trajeto_hint": "Voo direto" if not volta_escalas else f"{len(volta_escalas)} escala(s)",
                "cta_url": companhia_url,
                "cta_label": f"Acessar Minhas Viagens - {companhia_nome}",
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


def _build_valores_context(emissao):
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
                "hint": "Impostos e taxas aeroportuarias",
                "value": format_currency_brl(taxas),
            },
            {
                "label": "Taxa de servico",
                "hint": "Consultoria e emissao",
                "value": format_currency_brl(taxa_servico),
            },
        ],
        "total_value": format_currency_brl(total),
        "total_hint": (
            format_currency_brl(emissao.valor_venda_final)
            if emissao.valor_venda_final not in (None, "")
            else "Valor final consolidado da emissao"
        ),
    }


def _build_bagagem_context(emissao):
    bagagem_mao = getattr(emissao, "get_bagagem_mao_display", lambda: "")() or "Sob consulta"
    bagagem_despachada = getattr(emissao, "get_bagagem_despachada_display", lambda: "")() or "Sob consulta"

    return [
        {
            "label": "Bagagem de Mao",
            "value": bagagem_mao,
            "hint": (
                "Franquia definida na emissao."
                if getattr(emissao, "bagagem_mao", "")
                else "Confirmar regra da tarifa emitida."
            ),
        },
        {
            "label": "Bagagem Despachada",
            "value": bagagem_despachada,
            "hint": (
                "Franquia validada para a tarifa emitida."
                if getattr(emissao, "bagagem_despachada", "")
                else "Validar regra da tarifa emitida."
            ),
        },
    ]


def build_emissao_preview_context(emissao):
    status = _get_status_context(emissao)
    empresa = get_empresa_from_operational_record(emissao)
    localizador = emissao.localizador or "A confirmar"
    observacao = (
        emissao.detalhes.strip()
        if emissao.detalhes and emissao.detalhes.strip()
        else (
            "Emissao confirmada. Bilhetes enviados por e-mail. Recomendamos check-in online 24h antes do voo."
            if emissao.localizador
            else "Emissao em analise. Assim que o bilhete for confirmado, os detalhes finais serao enviados."
        )
    )

    return {
        "emissao_numero": f"EM-{emissao.criado_em.year}-{emissao.id:03d}",
        "status": status,
        "created_display": _format_datetime(emissao.criado_em),
        "localizador_display": localizador,
        "pnr_display": localizador,
        "passageiros": _build_passageiros_context(emissao),
        "voos": _build_flight_context(emissao),
        "bagagem_items": _build_bagagem_context(emissao),
        "valores": _build_valores_context(emissao),
        "empresa_contato": build_empresa_contact_context(empresa),
        "observacao_importante": observacao,
        "orientacoes": [
            "Chegue ao aeroporto com 3 horas de antecedencia para voos internacionais.",
            "Faca o check-in online entre 48h e 1h antes do horario do voo.",
            "Apresente documento original com foto e passaporte valido, quando aplicavel.",
            "Verifique as restricoes de bagagem e itens proibidos antes do embarque.",
            "Em caso de duvidas ou necessidade de alteracao, entre em contato com nossa equipe.",
            f"Guarde o localizador ({localizador}) para consultas e alteracoes.",
        ],
    }
