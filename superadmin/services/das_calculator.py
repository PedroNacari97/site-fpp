"""
Calculo do DAS do Simples Nacional - Anexo III (servicos, inclui SaaS).

Formula oficial (LC 123/2006 art. 18):

    aliquota_efetiva = ((RBT12 * aliquota_nominal) - parcela_deduzir) / RBT12
    DAS_mes          = receita_bruta_do_mes * aliquota_efetiva

RBT12 = Receita Bruta Total dos 12 meses ANTERIORES ao periodo de apuracao.

Empresa nova (menos de 12 meses desde abertura): usa RBT12 proporcional =
(receita_media_mensal_historica * 12).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


# Anexo III — 2024/2025/2026 (tabela vigente; atualize se a LC mudar)
ANEXO_III_FAIXAS: list[tuple[Decimal, Decimal, Decimal]] = [
    # (teto_da_faixa, aliquota_nominal, parcela_a_deduzir)
    (Decimal("180000.00"),  Decimal("0.0600"), Decimal("0.00")),
    (Decimal("360000.00"),  Decimal("0.1120"), Decimal("9360.00")),
    (Decimal("720000.00"),  Decimal("0.1350"), Decimal("17640.00")),
    (Decimal("1800000.00"), Decimal("0.1600"), Decimal("35640.00")),
    (Decimal("3600000.00"), Decimal("0.2100"), Decimal("125640.00")),
    (Decimal("4800000.00"), Decimal("0.3300"), Decimal("648000.00")),
]

# Limite total do Simples Nacional (EPP). Acima disso desenquadra.
LIMITE_SIMPLES = Decimal("4800000.00")


@dataclass
class ResultadoDAS:
    rbt12: Decimal
    faixa: int  # 1..6 ou 0 se desenquadrado
    aliquota_nominal: Decimal
    parcela_deduzir: Decimal
    aliquota_efetiva: Decimal  # fracao (0.06 = 6%)
    faturamento_mes: Decimal
    das_mes: Decimal
    desenquadrado: bool
    aviso: str = ""


def _quantize(v: Decimal, casas: str = "0.01") -> Decimal:
    return v.quantize(Decimal(casas), rounding=ROUND_HALF_UP)


def descobrir_faixa(rbt12: Decimal) -> tuple[int, Decimal, Decimal]:
    """Retorna (numero_faixa_1_a_6, aliquota_nominal, parcela_deduzir).

    Faixa 0 = desenquadrado (acima de R$ 4,8M).
    """
    rbt12 = Decimal(rbt12 or 0)
    if rbt12 <= 0:
        # sem historico -> comeca na Faixa 1
        aliq, ded = ANEXO_III_FAIXAS[0][1], ANEXO_III_FAIXAS[0][2]
        return 1, aliq, ded
    if rbt12 > LIMITE_SIMPLES:
        return 0, Decimal("0.33"), Decimal("0")
    for i, (teto, aliq, ded) in enumerate(ANEXO_III_FAIXAS, start=1):
        if rbt12 <= teto:
            return i, aliq, ded
    # fallback — nao deveria chegar aqui
    return 0, Decimal("0.33"), Decimal("0")


def aliquota_efetiva(rbt12: Decimal) -> Decimal:
    """Retorna a aliquota efetiva como fracao (0.06 = 6%)."""
    rbt12 = Decimal(rbt12 or 0)
    faixa, aliq, ded = descobrir_faixa(rbt12)
    if faixa == 0:
        return Decimal("0.33")
    if rbt12 <= 0:
        return aliq  # primeira operacao
    efetiva = ((rbt12 * aliq) - ded) / rbt12
    if efetiva < 0:
        return Decimal("0")
    return efetiva


def calcular_das(
    rbt12: Decimal,
    faturamento_mes: Decimal,
) -> ResultadoDAS:
    """Calcula o DAS do mes dado RBT12 e faturamento do mes."""
    rbt12 = Decimal(rbt12 or 0)
    faturamento_mes = Decimal(faturamento_mes or 0)
    faixa, aliq_nom, ded = descobrir_faixa(rbt12)
    desenquadrado = faixa == 0
    aviso = ""
    if desenquadrado:
        aviso = "RBT12 acima de R$ 4,8M — fora do Simples. Procure o contador."
    efetiva = aliquota_efetiva(rbt12)
    das = faturamento_mes * efetiva
    return ResultadoDAS(
        rbt12=_quantize(rbt12),
        faixa=faixa,
        aliquota_nominal=_quantize(aliq_nom, "0.0001"),
        parcela_deduzir=_quantize(ded),
        aliquota_efetiva=_quantize(efetiva, "0.0001"),
        faturamento_mes=_quantize(faturamento_mes),
        das_mes=_quantize(das),
        desenquadrado=desenquadrado,
        aviso=aviso,
    )


def calcular_rbt12(
    faturamentos_por_mes: dict[date, Decimal],
    mes_referencia: date,
    data_abertura: date | None = None,
) -> tuple[Decimal, bool]:
    """Soma os 12 meses ANTERIORES ao mes_referencia.

    Se a empresa tem menos de 12 meses desde abertura, usa RBT12 proporcional:
    media mensal historica x 12.

    Retorna (rbt12, usou_proporcional).
    """
    mes_referencia = mes_referencia.replace(day=1)

    # 12 meses anteriores
    meses_anteriores: list[date] = []
    m = mes_referencia
    for _ in range(12):
        # subtrair um mes
        if m.month == 1:
            m = date(m.year - 1, 12, 1)
        else:
            m = date(m.year, m.month - 1, 1)
        meses_anteriores.append(m)

    total = Decimal("0")
    for m_ant in meses_anteriores:
        total += Decimal(faturamentos_por_mes.get(m_ant, Decimal("0")) or 0)

    # Proporcional para empresa nova
    if data_abertura:
        abertura_mes = data_abertura.replace(day=1)
        meses_operando = 0
        m = abertura_mes
        while m < mes_referencia:
            meses_operando += 1
            if m.month == 12:
                m = date(m.year + 1, 1, 1)
            else:
                m = date(m.year, m.month + 1, 1)
        if 0 < meses_operando < 12:
            # receita media x 12
            total_historico = Decimal("0")
            m = abertura_mes
            while m < mes_referencia:
                total_historico += Decimal(
                    faturamentos_por_mes.get(m, Decimal("0")) or 0
                )
                if m.month == 12:
                    m = date(m.year + 1, 1, 1)
                else:
                    m = date(m.year, m.month + 1, 1)
            if meses_operando > 0:
                media = total_historico / Decimal(meses_operando)
                return _quantize(media * Decimal("12")), True

    return _quantize(total), False


def serie_mensal(
    faturamentos_por_mes: dict[date, Decimal],
    meses: Iterable[date],
    data_abertura: date | None = None,
) -> list[dict]:
    """Para cada mes na iteracao, devolve o DAS calculado.

    Retorna lista de dicts: {mes, faturamento, rbt12, aliquota_efetiva, das}.
    """
    out = []
    for m in meses:
        m0 = m.replace(day=1)
        rbt12, proporcional = calcular_rbt12(faturamentos_por_mes, m0, data_abertura)
        res = calcular_das(rbt12, faturamentos_por_mes.get(m0, Decimal("0")))
        out.append({
            "mes": m0,
            "faturamento": res.faturamento_mes,
            "rbt12": res.rbt12,
            "rbt12_proporcional": proporcional,
            "faixa": res.faixa,
            "aliquota_efetiva": res.aliquota_efetiva,
            "das": res.das_mes,
            "desenquadrado": res.desenquadrado,
        })
    return out
