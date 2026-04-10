import json
import re

from gestao.models import Aeroporto, AlertaViagem
from gestao.services.aeroporto_localizacao import infer_airport_location


FLAG_COUNTRY_MAP = {
    "br": ("Brasil", "América do Sul"),
    "ar": ("Argentina", "América do Sul"),
    "cl": ("Chile", "América do Sul"),
    "uy": ("Uruguai", "América do Sul"),
    "py": ("Paraguai", "América do Sul"),
    "pe": ("Peru", "América do Sul"),
    "co": ("Colômbia", "América do Sul"),
    "us": ("Estados Unidos", "América do Norte"),
    "ca": ("Canadá", "América do Norte"),
    "mx": ("México", "América do Norte"),
    "es": ("Espanha", "Europa"),
    "pt": ("Portugal", "Europa"),
    "fr": ("França", "Europa"),
    "it": ("Itália", "Europa"),
    "gb": ("Reino Unido", "Europa"),
    "de": ("Alemanha", "Europa"),
    "jp": ("Japão", "Ásia"),
    "ae": ("Emirados Árabes Unidos", "Ásia"),
    "au": ("Austrália", "Oceania"),
    "za": ("África do Sul", "África"),
}

REGIONAL_INDICATOR_START = 0x1F1E6
REGIONAL_INDICATOR_END = 0x1F1FF

MONTH_MAP = {
    "jan": 1,
    "fev": 2,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "apr": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "aug": 8,
    "set": 9,
    "sep": 9,
    "out": 10,
    "oct": 10,
    "nov": 11,
    "dez": 12,
    "dec": 12,
}

CLASSE_MAP = {
    "econômica": AlertaViagem.CLASSE_ECONOMICA,
    "economica": AlertaViagem.CLASSE_ECONOMICA,
    "executiva": AlertaViagem.CLASSE_EXECUTIVA,
    "business": AlertaViagem.CLASSE_EXECUTIVA,
}

def _repair_mojibake(value):
    text = str(value or "")
    if not text:
        return ""
    fixed = text
    for _ in range(3):
        if not any(token in fixed for token in ("Ã", "Â", "â")):
            break
        try:
            repaired = fixed.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if repaired == fixed:
            break
        fixed = repaired
    return fixed


def _clean_line(line):
    text = _repair_mojibake(line).strip()
    text = re.sub(r":[a-z0-9_+-]+:", "", text, flags=re.IGNORECASE).strip()
    return text


def _extract_flag_country(raw_text):
    text = _repair_mojibake(raw_text)
    flag_match = re.search(r"flag-([a-z]{2})", text, re.IGNORECASE)
    if flag_match:
        return flag_match.group(1).lower()

    regional = [
        ord(char)
        for char in text[:8]
        if REGIONAL_INDICATOR_START <= ord(char) <= REGIONAL_INDICATOR_END
    ]
    if len(regional) >= 2:
        return "".join(
            chr(codepoint - REGIONAL_INDICATOR_START + ord("A"))
            for codepoint in regional[:2]
        ).lower()
    return ""


def _normalize_text(value):
    text = _repair_mojibake(value).strip().lower()
    return (
        text.replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ã", "a")
        .replace("Ã¡", "a")
        .replace("Ã ", "a")
        .replace("Ã¢", "a")
        .replace("Ã£", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("Ã©", "e")
        .replace("Ãª", "e")
        .replace("í", "i")
        .replace("Ã­", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("Ã³", "o")
        .replace("Ã´", "o")
        .replace("Ãµ", "o")
        .replace("ú", "u")
        .replace("Ãº", "u")
        .replace("ç", "c")
        .replace("Ã§", "c")
    )


def _normalize_company(value):
    text = (value or "").strip()
    if not text:
        return ""
    aliases = {
        "latam": "LATAM",
        "gol": "GOL",
        "azul": "Azul",
        "american airlines": "American Airlines",
        "delta": "Delta Air Lines",
    }
    return aliases.get(text.lower(), text)


def _lookup_airport(iata):
    if not iata:
        return None
    airport = (
        Aeroporto.objects.filter(sigla__iexact=iata)
        .exclude(cidade="")
        .exclude(cidade__isnull=True)
        .order_by("id")
        .first()
    )
    if airport:
        return airport
    return Aeroporto.objects.filter(sigla__iexact=iata).order_by("id").first()


def _infer_location_from_airport(iata):
    airport = _lookup_airport(iata)
    if not airport:
        return "", "", ""
    resolved = infer_airport_location(airport)
    return resolved["cidade"], resolved["pais"], resolved["continente"]


def _parse_route(line):
    match = re.search(
        r"(?P<origem_cidade>.+?)\s+\((?P<origem>[A-Z]{3})\)\s*>\s*(?P<destino_cidade>.+?)\s+\((?P<destino>[A-Z]{3})\)",
        line,
    )
    return match.groupdict() if match else None


def _parse_dates_line(line):
    match = re.search(r"([A-Za-z]{3})/(\d{2})\s*:\s*`?([0-9,\s]+)`?", line)
    if not match:
        return []
    month_token = match.group(1).lower()
    month = MONTH_MAP.get(month_token)
    if not month:
        return []
    year = 2000 + int(match.group(2))
    days = [chunk.strip() for chunk in match.group(3).split(",") if chunk.strip()]
    parsed = []
    for day in days:
        if not day.isdigit():
            continue
        parsed.append(f"{year:04d}-{month:02d}-{int(day):02d}")
    return parsed


def _normalize_milhas_value(value):
    raw = _normalize_text(value)
    compact = raw.replace(" ", "")
    if not compact:
        return ""

    kilo_match = re.search(r"(?P<number>\d+(?:[.,]\d+)?)k\b", compact, re.IGNORECASE)
    if kilo_match:
        normalized_number = kilo_match.group("number").replace(".", "").replace(",", ".")
        try:
            return str(int(float(normalized_number) * 1000))
        except ValueError:
            return ""

    digits = re.sub(r"\D", "", compact)
    return digits or ""


def _extract_milhas_from_line(line):
    text = _repair_mojibake(line)
    patterns = [
        r"custo\s*(?:do|de)?\s*trecho\s*:\s*(?P<milhas>[\d\.,\skK]+)\s*(?:milhas|pontos|pts?)?",
        r"a partir de\s*(?P<milhas>[\d\.,\skK]+)\s*(?:milhas|pontos|pts?)",
        r"(?P<milhas>[\d\.,\skK]+)\s*(?:milhas|pontos|pts?)",
        r"custo\s*(?:do|de)?\s*trecho\s*:\s*(?P<milhas>[\d\.,\skK]+)\s*\+\s*taxas",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        milhas = _normalize_milhas_value(match.group("milhas"))
        if milhas:
            return milhas
    return ""


def parse_alerta_bruto(raw_text):
    lines = [_clean_line(line) for line in (raw_text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return {}

    parsed = {
        "titulo": "",
        "conteudo": "",
        "continente": "",
        "pais": "",
        "cidade_destino": "",
        "origem": "",
        "destino": "",
        "classe": "",
        "programa_fidelidade": "",
        "companhia_aerea": "",
        "valor_milhas": "",
        "valor_reais": "",
        "datas_ida": [],
        "datas_volta": [],
    }

    notes = []
    ida_route = None
    volta_route = None
    current_dates_target = None

    first_line = lines[0]
    flag_code = _extract_flag_country(raw_text)
    if flag_code:
        country_info = FLAG_COUNTRY_MAP.get(flag_code)
        if country_info:
            parsed["pais"], parsed["continente"] = country_info

    miles_match = re.search(
        r"(?P<cidade>.+?)\s+\((?P<destino>[A-Z]{3})\)\s+(?P<milhas>[\d\.,\skK]+)\s*(?:milhas|pontos|pts?)",
        first_line,
        re.IGNORECASE,
    )
    if miles_match:
        parsed["cidade_destino"] = miles_match.group("cidade").strip()
        parsed["destino"] = miles_match.group("destino").strip().upper()
        parsed["valor_milhas"] = _normalize_milhas_value(miles_match.group("milhas"))
    elif not parsed["valor_milhas"]:
        parsed["valor_milhas"] = _extract_milhas_from_line(first_line)

    for idx, line in enumerate(lines):
        lowered = line.lower()
        normalized_line = _normalize_text(line)
        if not parsed["classe"] and ("econom" in normalized_line or "econ" == normalized_line):
            parsed["classe"] = AlertaViagem.CLASSE_ECONOMICA
            continue
        if not parsed["classe"] and ("execut" in normalized_line or "business" in normalized_line):
            parsed["classe"] = AlertaViagem.CLASSE_EXECUTIVA
            continue

        if not parsed["valor_milhas"]:
            parsed["valor_milhas"] = _extract_milhas_from_line(line)

        program_match = re.search(r"programa\s+(.+)$", line, re.IGNORECASE)
        if program_match:
            parsed["programa_fidelidade"] = program_match.group(1).strip()
            continue

        company_match = re.search(r"voando\s+(.+)$", line, re.IGNORECASE)
        if company_match:
            parsed["companhia_aerea"] = _normalize_company(company_match.group(1))
            continue

        route_data = _parse_route(line)
        if route_data:
            if not ida_route:
                ida_route = route_data
            else:
                volta_route = route_data
            continue

        if "disponibilidade de ida" in lowered:
            current_dates_target = "datas_ida"
            continue

        if "disponibilidade de volta" in lowered:
            current_dates_target = "datas_volta"
            continue

        if current_dates_target and re.search(r"[A-Za-z]{3}/\d{2}\s*:", line):
            parsed[current_dates_target].extend(_parse_dates_line(line))
            continue

        if line.startswith("Pesquisar ida e volta"):
            notes.append(line)
            continue

        if normalized_line.startswith("custo trecho:") or normalized_line.startswith("classe "):
            continue

        if line.startswith("@"):
            continue

        if line and idx > 0:
            notes.append(line)

    if ida_route:
        parsed["origem"] = ida_route["origem"].upper()
        parsed["destino"] = ida_route["destino"].upper()
        if not parsed["cidade_destino"]:
            parsed["cidade_destino"] = ida_route["destino_cidade"].strip()

    if parsed["destino"] and (not parsed["pais"] or not parsed["continente"] or not parsed["cidade_destino"]):
        city, country, continent = _infer_location_from_airport(parsed["destino"])
        parsed["cidade_destino"] = parsed["cidade_destino"] or city
        parsed["pais"] = parsed["pais"] or country
        parsed["continente"] = parsed["continente"] or continent

    if not parsed["cidade_destino"] and ida_route:
        parsed["cidade_destino"] = ida_route["destino_cidade"].strip()

    classe_label = dict(AlertaViagem.CLASSE_CHOICES).get(parsed["classe"], "")
    program = parsed["programa_fidelidade"] or "Programa não informado"
    company = parsed["companhia_aerea"] or "Companhia não informada"
    route_label = ""
    if ida_route:
        route_label = (
            f"{ida_route['origem_cidade'].strip()} ({ida_route['origem'].upper()}) → "
            f"{ida_route['destino_cidade'].strip()} ({ida_route['destino'].upper()})"
        )

    if parsed["cidade_destino"] and parsed["valor_milhas"]:
        parsed["titulo"] = (
            f"{parsed['cidade_destino']} a partir de {int(parsed['valor_milhas']):,} milhas + taxas"
        ).replace(",", ".")
    elif route_label:
        parsed["titulo"] = route_label

    content_blocks = []
    if parsed["valor_milhas"]:
        content_blocks.append(
            f"A partir de {int(parsed['valor_milhas']):,} milhas + taxas".replace(",", ".")
        )
    if classe_label:
        content_blocks.append(f"Classe {classe_label}")
    if company:
        content_blocks.append(f"Voando {company}")
    if program:
        content_blocks.append(f"Programa {program}")
    if route_label:
        content_blocks.append(route_label)
    if parsed["datas_ida"]:
        content_blocks.append(f"Ida: {', '.join(parsed['datas_ida'])}")
    if parsed["datas_volta"]:
        content_blocks.append(f"Volta: {', '.join(parsed['datas_volta'])}")
    content_blocks.extend(notes)
    parsed["conteudo"] = "\n".join(block for block in content_blocks if block)

    return parsed


def backfill_alerta_post_data(post_data, parsed):
    updated = post_data.copy()
    if not parsed:
        return updated

    mapping = {
        "titulo": "titulo",
        "conteudo": "conteudo",
        "continente": "continente",
        "pais": "pais",
        "cidade_destino": "cidade_destino",
        "origem": "origem",
        "destino": "destino",
        "classe": "classe",
        "programa_fidelidade": "programa_fidelidade",
        "companhia_aerea": "companhia_aerea",
        "valor_milhas": "valor_milhas",
        "valor_reais": "valor_reais",
    }
    for target, source in mapping.items():
        if not updated.get(target) and parsed.get(source) not in (None, "", []):
            updated[target] = parsed[source]

    if parsed.get("datas_ida"):
        updated["datas_ida"] = json.dumps(parsed["datas_ida"])
    if parsed.get("datas_volta"):
        updated["datas_volta"] = json.dumps(parsed["datas_volta"])
    return updated
