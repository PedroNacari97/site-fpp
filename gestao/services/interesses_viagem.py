from __future__ import annotations

from typing import Iterable

from gestao.models import AlertaViagem, InteresseViagemCliente, InteresseViagemMatch


def _normalize(value):
    text = (value or "").strip().lower()
    return (
        text.replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )


def _month_numbers(raw_dates: Iterable[str]) -> set[int]:
    months = set()
    for raw in raw_dates or []:
        if not isinstance(raw, str):
            continue
        parts = raw.split("-")
        if len(parts) < 2:
            continue
        try:
            months.add(int(parts[1]))
        except ValueError:
            continue
    return months


def _day_numbers(raw_dates: Iterable[str]) -> set[int]:
    days = set()
    for raw in raw_dates or []:
        if not isinstance(raw, str):
            continue
        parts = raw.split("-")
        if len(parts) < 3:
            continue
        try:
            days.add(int(parts[2]))
        except ValueError:
            continue
    return days


def _semester_numbers(raw_dates: Iterable[str]) -> set[int]:
    semesters = set()
    for month in _month_numbers(raw_dates):
        semesters.add(1 if month <= 6 else 2)
    return semesters


def match_interesse_viagem(alerta: AlertaViagem, interesse: InteresseViagemCliente):
    reasons = []

    if not interesse.ativo or not alerta.ativo or not alerta.deve_aparecer_na_vitrine():
        return False, reasons

    comparisons = [
        ("continente", alerta.continente, interesse.continente, "Continente"),
        ("pais", alerta.pais, interesse.pais, "País"),
        ("cidade_destino", alerta.cidade_destino, interesse.cidade_destino, "Cidade"),
        ("origem", alerta.origem, interesse.origem, "Origem"),
        ("destino", alerta.destino, interesse.destino, "Destino"),
        ("classe", alerta.classe, interesse.classe, "Classe"),
        ("programa_fidelidade", alerta.programa_fidelidade, interesse.programa_fidelidade, "Programa"),
        ("companhia_aerea", alerta.companhia_aerea, interesse.companhia_aerea, "Companhia"),
    ]

    for _, alerta_value, interesse_value, label in comparisons:
        if not interesse_value:
            continue
        if _normalize(alerta_value) != _normalize(interesse_value):
            return False, []
        reasons.append(label)

    if interesse.meses_ida:
        months = _month_numbers(alerta.datas_ida)
        expected = {int(month) for month in interesse.meses_ida}
        if not months.intersection(expected):
            return False, []
        reasons.append("Mês de ida")

    if interesse.meses_volta:
        months = _month_numbers(alerta.datas_volta)
        expected = {int(month) for month in interesse.meses_volta}
        if not months.intersection(expected):
            return False, []
        reasons.append("Mês de volta")

    if interesse.dias_ida:
        days = _day_numbers(alerta.datas_ida)
        expected = {int(day) for day in interesse.dias_ida}
        if not days.intersection(expected):
            return False, []
        reasons.append("Dia de ida")

    if interesse.dias_volta:
        days = _day_numbers(alerta.datas_volta)
        expected = {int(day) for day in interesse.dias_volta}
        if not days.intersection(expected):
            return False, []
        reasons.append("Dia de volta")

    if interesse.semestres_ida:
        semesters = _semester_numbers(alerta.datas_ida)
        expected = {int(semester) for semester in interesse.semestres_ida}
        if not semesters.intersection(expected):
            return False, []
        reasons.append("Semestre de ida")

    if interesse.semestres_volta:
        semesters = _semester_numbers(alerta.datas_volta)
        expected = {int(semester) for semester in interesse.semestres_volta}
        if not semesters.intersection(expected):
            return False, []
        reasons.append("Semestre de volta")

    return True, reasons


def sync_alerta_interest_matches(alerta: AlertaViagem):
    existing = {
        match.interesse_id: match
        for match in InteresseViagemMatch.objects.filter(alerta=alerta).select_related("interesse")
    }
    valid_ids = set()

    interesses = InteresseViagemCliente.objects.filter(
        ativo=True,
        cliente__ativo=True,
        cliente__perfil="cliente",
    ).select_related("cliente", "cliente__usuario", "cliente__empresa")

    for interesse in interesses:
        matched, reasons = match_interesse_viagem(alerta, interesse)
        if not matched:
            continue
        valid_ids.add(interesse.id)
        match = existing.get(interesse.id)
        if match:
            if match.motivos != reasons:
                match.motivos = reasons
                match.save(update_fields=["motivos"])
            continue
        InteresseViagemMatch.objects.create(
            interesse=interesse,
            alerta=alerta,
            motivos=reasons,
        )

    stale_ids = [interesse_id for interesse_id in existing if interesse_id not in valid_ids]
    if stale_ids:
        InteresseViagemMatch.objects.filter(alerta=alerta, interesse_id__in=stale_ids).delete()
