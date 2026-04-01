from decimal import Decimal

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


def get_cotacao_titular_info(cotacao):
    titular = cotacao.cliente or cotacao.conta_administrada
    if hasattr(titular, "usuario"):
        return {
            "nome": titular.usuario.get_full_name() or titular.usuario.username,
            "cpf": getattr(titular, "cpf", "") or "-",
            "email": titular.usuario.email or "-",
            "telefone": getattr(titular, "telefone", "") or "-",
        }
    return {
        "nome": getattr(titular, "nome", str(titular)) if titular else "-",
        "cpf": "-",
        "email": "-",
        "telefone": "-",
    }


def build_cotacao_preview_context(cotacao):
    cotacao.calcular_valores()
    titular = get_cotacao_titular_info(cotacao)
    empresa = get_empresa_from_operational_record(cotacao)
    qtd_passageiros = max(cotacao.qtd_passageiros or 1, 1)
    custo_milhas_unitario = (Decimal(cotacao.milhas or 0) / Decimal("1000")) * Decimal(
        cotacao.valor_milheiro or 0
    )
    taxas_total = Decimal(cotacao.taxas or 0) * qtd_passageiros
    valor_referencia_total = Decimal(cotacao.valor_passagem or 0) * qtd_passageiros
    custo_milhas_total = custo_milhas_unitario * qtd_passageiros
    valor_vista_total = Decimal(cotacao.valor_vista or 0) * qtd_passageiros
    valor_parcelado_total = Decimal(cotacao.valor_parcelado or 0) * qtd_passageiros
    parcelas = cotacao.parcelas or 1
    valor_parcela = valor_parcelado_total / Decimal(parcelas) if parcelas else valor_parcelado_total
    observacao_importante = (
        cotacao.observacoes.strip()
        if cotacao.observacoes and cotacao.observacoes.strip()
        else "Emissao sujeita a disponibilidade de assentos. Valores de taxas podem sofrer alteracao ate a emissao."
    )

    return {
        "cotacao_numero": f"{cotacao.id:03d}/{cotacao.criado_em.year}",
        "titular_info": titular,
        "origem_sigla": getattr(cotacao.origem, "sigla", "-") or "-",
        "origem_nome": str(cotacao.origem) if cotacao.origem else "Origem nao informada",
        "destino_sigla": getattr(cotacao.destino, "sigla", "-") or "-",
        "destino_nome": str(cotacao.destino) if cotacao.destino else "Destino nao informado",
        "tem_volta": bool(cotacao.data_volta),
        "escalas_ida": list(cotacao.escalas.filter(tipo="ida").select_related("aeroporto")),
        "escalas_volta": list(cotacao.escalas.filter(tipo="volta").select_related("aeroporto")),
        "qtd_passageiros_label": f"{qtd_passageiros} PAX",
        "classe_label": cotacao.classe or "Nao informada",
        "companhia_label": cotacao.companhia_aerea or "Nao informada",
        "programa_label": cotacao.programa.nome if cotacao.programa else "Nao informado",
        "valor_items": [
            {
                "label": "Taxas de embarque",
                "hint": "Impostos e taxas aeroportuarias",
                "value": format_currency_brl(taxas_total),
                "value_raw": taxas_total,
            },
            {
                "label": "Valor da passagem",
                "hint": "Preco base da passagem",
                "value": format_currency_brl(valor_referencia_total),
                "value_raw": valor_referencia_total,
            },
            {
                "label": "Taxa de servico",
                "hint": "Consultoria e emissao",
                "value": format_currency_brl(custo_milhas_total),
                "value_raw": custo_milhas_total,
            },
        ],
        "valor_vista_total": format_currency_brl(valor_vista_total),
        "valor_vista_total_raw": valor_vista_total,
        "valor_parcelado_total": format_currency_brl(valor_parcelado_total),
        "valor_parcelado_total_raw": valor_parcelado_total,
        "valor_parcelado_hint": f"{parcelas}x de {format_currency_brl(valor_parcela)}",
        "valor_parcela_raw": valor_parcela,
        "parcelas": parcelas,
        "empresa_contato": build_empresa_contact_context(empresa),
        "observacao_importante": observacao_importante,
        "condicoes_gerais": [
            f"Esta cotacao tem validade ate {cotacao.validade.strftime('%d/%m/%Y')}."
            if cotacao.validade
            else "A validade desta cotacao sera confirmada no atendimento.",
            "A emissao esta sujeita a disponibilidade de assentos no programa de fidelidade.",
            "As taxas de embarque podem sofrer alteracao ate o momento da emissao.",
            "Regras de alteracao e cancelamento seguem as politicas da companhia aerea.",
            "Recomendamos a contratacao de seguro viagem para maior tranquilidade.",
        ],
    }
