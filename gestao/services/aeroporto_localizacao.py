import re
import unicodedata


BRAZIL_STATES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
    "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
    "RR", "SC", "SP", "SE", "TO",
}

IATA_LOCATION_OVERRIDES = {
    "AJU": ("Brasil", "América do Sul"),
    "BEL": ("Brasil", "América do Sul"),
    "BPS": ("Brasil", "América do Sul"),
    "BSB": ("Brasil", "América do Sul"),
    "CGB": ("Brasil", "América do Sul"),
    "CGH": ("Brasil", "América do Sul"),
    "CGR": ("Brasil", "América do Sul"),
    "CNF": ("Brasil", "América do Sul"),
    "CWB": ("Brasil", "América do Sul"),
    "FLN": ("Brasil", "América do Sul"),
    "FOR": ("Brasil", "América do Sul"),
    "GIG": ("Brasil", "América do Sul"),
    "GRU": ("Brasil", "América do Sul"),
    "GYN": ("Brasil", "América do Sul"),
    "IGU": ("Brasil", "América do Sul"),
    "JPA": ("Brasil", "América do Sul"),
    "MCZ": ("Brasil", "América do Sul"),
    "MCZ": ("Brasil", "América do Sul"),
    "MAO": ("Brasil", "América do Sul"),
    "MAB": ("Brasil", "América do Sul"),
    "NAT": ("Brasil", "América do Sul"),
    "POA": ("Brasil", "América do Sul"),
    "PVH": ("Brasil", "América do Sul"),
    "RAO": ("Brasil", "América do Sul"),
    "REC": ("Brasil", "América do Sul"),
    "SDU": ("Brasil", "América do Sul"),
    "SLZ": ("Brasil", "América do Sul"),
    "SSA": ("Brasil", "América do Sul"),
    "THE": ("Brasil", "América do Sul"),
    "VCP": ("Brasil", "América do Sul"),
    "VIX": ("Brasil", "América do Sul"),
    "AEP": ("Argentina", "América do Sul"),
    "EZE": ("Argentina", "América do Sul"),
    "MVD": ("Uruguai", "América do Sul"),
    "SCL": ("Chile", "América do Sul"),
    "BOG": ("Colômbia", "América do Sul"),
    "CTG": ("Colômbia", "América do Sul"),
    "LIM": ("Peru", "América do Sul"),
    "ASU": ("Paraguai", "América do Sul"),
    "ATL": ("Estados Unidos", "América do Norte"),
    "BOS": ("Estados Unidos", "América do Norte"),
    "BNA": ("Estados Unidos", "América do Norte"),
    "BHM": ("Estados Unidos", "América do Norte"),
    "BDL": ("Estados Unidos", "América do Norte"),
    "DFW": ("Estados Unidos", "América do Norte"),
    "EWR": ("Estados Unidos", "América do Norte"),
    "FLL": ("Estados Unidos", "América do Norte"),
    "IAD": ("Estados Unidos", "América do Norte"),
    "IAH": ("Estados Unidos", "América do Norte"),
    "JFK": ("Estados Unidos", "América do Norte"),
    "LAS": ("Estados Unidos", "América do Norte"),
    "LAX": ("Estados Unidos", "América do Norte"),
    "MCO": ("Estados Unidos", "América do Norte"),
    "MIA": ("Estados Unidos", "América do Norte"),
    "ORD": ("Estados Unidos", "América do Norte"),
    "SFO": ("Estados Unidos", "América do Norte"),
    "YUL": ("Canadá", "América do Norte"),
    "YYZ": ("Canadá", "América do Norte"),
    "YVR": ("Canadá", "América do Norte"),
    "MEX": ("México", "América do Norte"),
    "AMS": ("Holanda", "Europa"),
    "ARN": ("Suécia", "Europa"),
    "ATH": ("Grécia", "Europa"),
    "BCN": ("Espanha", "Europa"),
    "BHX": ("Reino Unido", "Europa"),
    "BUD": ("Hungria", "Europa"),
    "BRU": ("Bélgica", "Europa"),
    "CDG": ("França", "Europa"),
    "CPH": ("Dinamarca", "Europa"),
    "DUB": ("Irlanda", "Europa"),
    "FCO": ("Itália", "Europa"),
    "FRA": ("Alemanha", "Europa"),
    "HEL": ("Finlândia", "Europa"),
    "IST": ("Turquia", "Europa"),
    "LGW": ("Reino Unido", "Europa"),
    "LHR": ("Reino Unido", "Europa"),
    "LIS": ("Portugal", "Europa"),
    "MAD": ("Espanha", "Europa"),
    "MAN": ("Reino Unido", "Europa"),
    "MUC": ("Alemanha", "Europa"),
    "MXP": ("Itália", "Europa"),
    "OPO": ("Portugal", "Europa"),
    "OSL": ("Noruega", "Europa"),
    "VIE": ("Áustria", "Europa"),
    "ZRH": ("Suíça", "Europa"),
    "ADD": ("Etiópia", "África"),
    "JNB": ("África do Sul", "África"),
    "CPT": ("África do Sul", "África"),
    "AUH": ("Emirados Árabes Unidos", "Ásia"),
    "BKK": ("Tailândia", "Ásia"),
    "BLR": ("Índia", "Ásia"),
    "BOM": ("Índia", "Ásia"),
    "DEL": ("Índia", "Ásia"),
    "DOH": ("Catar", "Ásia"),
    "DXB": ("Emirados Árabes Unidos", "Ásia"),
    "HKG": ("Hong Kong", "Ásia"),
    "ICN": ("Coreia do Sul", "Ásia"),
    "KIX": ("Japão", "Ásia"),
    "NRT": ("Japão", "Ásia"),
    "HND": ("Japão", "Ásia"),
    "SIN": ("Singapura", "Ásia"),
    "BNE": ("Austrália", "Oceania"),
    "MEL": ("Austrália", "Oceania"),
    "SYD": ("Austrália", "Oceania"),
    "AKL": ("Nova Zelândia", "Oceania"),
}

LOCATION_KEYWORDS = [
    (("sao paulo", "guarulhos", "congonhas", "campinas", "viracopos", "ribeirao preto", "rio de janeiro", "brasilia", "fortaleza", "salvador", "porto alegre", "florianopolis", "foz do iguacu", "belo horizonte", "recife", "manaus", "belem", "natal", "porto seguro", "vitoria", "goiania", "curitiba", "joinville", "sao jose dos campos", "aracaju"), ("Brasil", "América do Sul")),
    (("buenos aires",), ("Argentina", "América do Sul")),
    (("montevideo",), ("Uruguai", "América do Sul")),
    (("santiago",), ("Chile", "América do Sul")),
    (("bogota",), ("Colômbia", "América do Sul")),
    (("cartagena",), ("Colômbia", "América do Sul")),
    (("lima",), ("Peru", "América do Sul")),
    (("paraguai", "assuncao", "asuncion"), ("Paraguai", "América do Sul")),
    (("miami", "nova york", "new york", "atlanta", "boston", "hartford", "los angeles", "orlando", "las vegas", "washington", "san francisco", "fort lauderdale", "houston", "dallas", "chicago", "nashville", "birmingham"), ("Estados Unidos", "América do Norte")),
    (("toronto", "montreal", "vancouver"), ("Canadá", "América do Norte")),
    (("cidade do mexico", "mexico city"), ("México", "América do Norte")),
    (("lisboa", "porto"), ("Portugal", "Europa")),
    (("barcelona", "madrid"), ("Espanha", "Europa")),
    (("paris",), ("França", "Europa")),
    (("roma", "milan", "milao"), ("Itália", "Europa")),
    (("londres", "london", "manchester", "birmingham"), ("Reino Unido", "Europa")),
    (("amsterda", "amsterdam"), ("Holanda", "Europa")),
    (("frankfurt", "munique", "munich"), ("Alemanha", "Europa")),
    (("zurique", "zurich"), ("Suíça", "Europa")),
    (("estocolmo", "stockholm"), ("Suécia", "Europa")),
    (("atenas",), ("Grécia", "Europa")),
    (("copenhague", "copenhagen"), ("Dinamarca", "Europa")),
    (("helsinque", "helsinki"), ("Finlândia", "Europa")),
    (("dublin",), ("Irlanda", "Europa")),
    (("abu dhabi",), ("Emirados Árabes Unidos", "Ásia")),
    (("dubai",), ("Emirados Árabes Unidos", "Ásia")),
    (("doha",), ("Catar", "Ásia")),
    (("bangkok",), ("Tailândia", "Ásia")),
    (("hong kong",), ("Hong Kong", "Ásia")),
    (("singapura", "singapore"), ("Singapura", "Ásia")),
    (("toquio", "tokyo", "osaka"), ("Japão", "Ásia")),
    (("seul", "seoul"), ("Coreia do Sul", "Ásia")),
    (("mumbai", "bangalore", "delhi"), ("Índia", "Ásia")),
    (("addis ababa",), ("Etiópia", "África")),
    (("joanesburgo", "johannesburg", "cidade do cabo", "cape town"), ("África do Sul", "África")),
    (("sydney", "melbourne", "brisbane"), ("Austrália", "Oceania")),
    (("auckland",), ("Nova Zelândia", "Oceania")),
]


def normalize_location_text(value):
    text = (value or "")
    text = (
        text.replace("Ã¡", "a")
        .replace("Ã ", "a")
        .replace("Ã¢", "a")
        .replace("Ã£", "a")
        .replace("Ã©", "e")
        .replace("Ãª", "e")
        .replace("Ã­", "i")
        .replace("Ã³", "o")
        .replace("Ã´", "o")
        .replace("Ãµ", "o")
        .replace("Ãº", "u")
        .replace("Ã§", "c")
        .replace("â€“", "-")
    )
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower().strip()


def clean_airport_city(value):
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^Aeroporto de\s+", "", text, flags=re.IGNORECASE).strip()
    if "(" in text:
        text = text.split("(", 1)[0].strip()
    return text


def infer_airport_location(airport):
    if not airport:
        return {"cidade": "", "pais": "", "continente": ""}

    code = str(getattr(airport, "sigla", "") or "").strip().upper()
    nome = str(getattr(airport, "nome", "") or "").strip()
    cidade = str(getattr(airport, "cidade", "") or "").strip()
    estado = str(getattr(airport, "estado", "") or "").strip().upper()
    city_label = clean_airport_city(cidade or nome)

    if code in IATA_LOCATION_OVERRIDES:
        pais, continente = IATA_LOCATION_OVERRIDES[code]
        return {"cidade": city_label, "pais": pais, "continente": continente}

    haystack = normalize_location_text(" ".join([code, nome, cidade, estado]))
    if estado in BRAZIL_STATES:
        return {"cidade": city_label, "pais": "Brasil", "continente": "América do Sul"}

    for keywords, (pais, continente) in LOCATION_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return {"cidade": city_label, "pais": pais, "continente": continente}

    return {"cidade": city_label, "pais": "", "continente": ""}


def serialize_airport_for_alerts(airport):
    resolved = infer_airport_location(airport)
    return {
        "sigla": airport.sigla,
        "nome": airport.nome,
        "cidade": airport.cidade,
        "estado": airport.estado,
        "cidade_resolvida": resolved["cidade"],
        "pais": resolved["pais"],
        "continente": resolved["continente"],
    }
