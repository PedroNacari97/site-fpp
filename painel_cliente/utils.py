from gestao.models import ContaFidelidade, EmissaoPassagem, EmissaoHotel


def generate_dashboard_context(user):
    """Aggregate loyalty account, emissions and hotel data for dashboard."""

    contas = ContaFidelidade.objects.filter(cliente__usuario=user).select_related("programa")
    emissoes = EmissaoPassagem.objects.filter(cliente__usuario=user)
    hoteis = EmissaoHotel.objects.filter(cliente__usuario=user)

    accounts = []
    for conta in contas:
        saldo = conta.saldo_pontos or 0
        valor_medio = conta.valor_medio_por_mil or 0
        valor_total = (saldo / 1000) * valor_medio
        accounts.append(
            {
                "id": conta.id,
                "programa": conta.programa.nome,
                "saldo_pontos": saldo,
                "valor_total": valor_total,
                "valor_medio": valor_medio,
                "valor_referencia": conta.programa.preco_medio_milheiro,
            }
        )

    return {
        "contas_info": accounts,
        "qtd_emissoes": emissoes.count(),
        "pontos_totais_utilizados": sum(e.pontos_utilizados or 0 for e in emissoes),
        "valor_total_referencia": sum(float(e.valor_referencia or 0) for e in emissoes),
        "valor_total_pago": sum(float(e.valor_pago or 0) for e in emissoes),
        "valor_total_economizado": sum(float(e.valor_referencia or 0) for e in emissoes)
        - sum(float(e.valor_pago or 0) for e in emissoes),
        "qtd_hoteis": hoteis.count(),
        "valor_total_hoteis": sum(float(h.valor_pago or 0) for h in hoteis),
        "valor_total_hoteis_referencia": sum(
            float(h.valor_referencia or 0) for h in hoteis
        ),
        "valor_total_hoteis_economia": sum(
            float(h.economia_obtida or (h.valor_referencia - h.valor_pago))
            for h in hoteis
        ),
    }
