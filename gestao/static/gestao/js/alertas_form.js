const dateFormat = "Y-m-d";
const flagCountryMap = {
  br: { pais: "Brasil", continente: "América do Sul" },
  ar: { pais: "Argentina", continente: "América do Sul" },
  cl: { pais: "Chile", continente: "América do Sul" },
  us: { pais: "Estados Unidos", continente: "América do Norte" },
  ca: { pais: "Canadá", continente: "América do Norte" },
  mx: { pais: "México", continente: "América do Norte" },
  es: { pais: "Espanha", continente: "Europa" },
  pt: { pais: "Portugal", continente: "Europa" },
  fr: { pais: "França", continente: "Europa" },
  it: { pais: "Itália", continente: "Europa" },
  gb: { pais: "Reino Unido", continente: "Europa" },
  jp: { pais: "Japão", continente: "Ásia" },
};

const regionalIndicatorStart = 0x1f1e6;
const regionalIndicatorEnd = 0x1f1ff;

const monthMap = {
  jan: 1,
  fev: 2,
  feb: 2,
  mar: 3,
  abr: 4,
  apr: 4,
  mai: 5,
  may: 5,
  jun: 6,
  jul: 7,
  ago: 8,
  aug: 8,
  set: 9,
  sep: 9,
  out: 10,
  oct: 10,
  nov: 11,
  dez: 12,
  dec: 12,
};

const normalizeLooseText = (value) =>
  (value || "")
    .replace(/Ã¡/g, "a")
    .replace(/Ã /g, "a")
    .replace(/Ã¢/g, "a")
    .replace(/Ã£/g, "a")
    .replace(/Ã©/g, "e")
    .replace(/Ãª/g, "e")
    .replace(/Ã­/g, "i")
    .replace(/Ã³/g, "o")
    .replace(/Ã´/g, "o")
    .replace(/Ãµ/g, "o")
    .replace(/Ãº/g, "u")
    .replace(/Ã§/g, "c")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();

const airportData = (() => {
  const element = document.getElementById("alerta-aeroportos-data");
  if (!element) {
    return [];
  }
  try {
    return JSON.parse(element.textContent || "[]");
  } catch (error) {
    return [];
  }
})();

const normalizeText = (value) =>
  (value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();

const parseValue = (input) => {
  if (!input || !input.value) {
    return [];
  }
  try {
    const parsed = JSON.parse(input.value);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
};

const formatDate = (dateObj) => dateObj.toISOString().slice(0, 10);

const expandRange = (rangeDates) => {
  if (!rangeDates || rangeDates.length < 2) {
    return [];
  }
  const [start, end] = rangeDates;
  const dates = [];
  const current = new Date(start);
  while (current <= end) {
    dates.push(formatDate(current));
    current.setDate(current.getDate() + 1);
  }
  return dates;
};

const renderChips = (container, dates) => {
  container.innerHTML = "";
  if (!dates.length) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "Nenhuma data selecionada.";
    container.appendChild(empty);
    return;
  }
  dates.forEach((date) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "date-chip is-removable";
    chip.dataset.dateValue = date;
    chip.innerHTML = `<span>${date}</span><span class="remove">×</span>`;
    container.appendChild(chip);
  });
};

const setupDateGroup = (groupEl) => {
  const hiddenInput = groupEl.querySelector("input[type='hidden']");
  const chipsContainer = groupEl.querySelector("[data-chips]");
  const calendarInput = groupEl.querySelector("[data-calendar]");
  const rangeInput = groupEl.querySelector("[data-range]");
  const confirmButton = groupEl.querySelector("[data-confirm]");

  let selectedDates = parseValue(hiddenInput);

  const syncHidden = () => {
    hiddenInput.value = JSON.stringify(selectedDates);
    renderChips(chipsContainer, selectedDates);
  };

  groupEl.__setDates = (dates) => {
    selectedDates = Array.from(new Set((dates || []).filter(Boolean))).sort();
    syncHidden();
  };

  syncHidden();

  const calendar = flatpickr(calendarInput, {
    mode: "multiple",
    dateFormat,
    allowInput: false,
  });

  const rangePicker = flatpickr(rangeInput, {
    mode: "range",
    dateFormat,
    allowInput: false,
  });

  confirmButton.addEventListener("click", () => {
    const multipleDates = calendar.selectedDates.map(formatDate);
    const rangeDates = expandRange(rangePicker.selectedDates);
    const merged = Array.from(new Set([...selectedDates, ...multipleDates, ...rangeDates]));
    selectedDates = merged.sort();
    calendar.clear();
    rangePicker.clear();
    syncHidden();
  });

  chipsContainer.addEventListener("click", (event) => {
    const target = event.target.closest(".date-chip.is-removable");
    if (!target) {
      return;
    }
    const value = target.dataset.dateValue;
    selectedDates = selectedDates.filter((item) => item !== value);
    syncHidden();
  });
};

const parseDatesLine = (line) => {
  const match = line.match(/([A-Za-z]{3})\/(\d{2})\s*:\s*`?([0-9,\s]+)`?/);
  if (!match) {
    return [];
  }
  const month = monthMap[(match[1] || "").toLowerCase()];
  if (!month) {
    return [];
  }
  const year = 2000 + Number(match[2]);
  return (match[3] || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => /^\d+$/.test(item))
    .map((day) => `${year}-${String(month).padStart(2, "0")}-${String(Number(day)).padStart(2, "0")}`);
};

const extractFlagCountry = (rawText) => {
  const text = rawText || "";
  const textualMatch = text.match(/flag-([a-z]{2})/i);
  if (textualMatch) {
    return (textualMatch[1] || "").toLowerCase();
  }

  const regional = Array.from(text.slice(0, 8))
    .map((char) => char.codePointAt(0))
    .filter((codepoint) => codepoint >= regionalIndicatorStart && codepoint <= regionalIndicatorEnd);

  if (regional.length >= 2) {
    return regional
      .slice(0, 2)
      .map((codepoint) => String.fromCharCode(codepoint - regionalIndicatorStart + 65))
      .join("")
      .toLowerCase();
  }
  return "";
};

const findAirportByIata = (iata) => {
  const code = (iata || "").toUpperCase();
  if (!code) {
    return null;
  }
  return airportData.find((airport) => String(airport.sigla || "").toUpperCase() === code) || null;
};

const parseAlertaBruto = (rawText) => {
  const text = rawText || "";
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.replace(/:[a-z0-9_+\-]+:/gi, "").trim())
    .filter(Boolean);

  const parsed = {
    titulo: "",
    conteudo: "",
    continente: "",
    pais: "",
    cidade_destino: "",
    origem: "",
    destino: "",
    classe: "",
    programa_fidelidade: "",
    companhia_aerea: "",
    valor_milhas: "",
    datas_ida: [],
    datas_volta: [],
  };

  const flagCode = extractFlagCountry(text);
  if (flagCode) {
    const country = flagCountryMap[flagCode];
    if (country) {
      parsed.pais = country.pais;
      parsed.continente = country.continente;
    }
  }

  const firstLine = lines[0] || "";
  const milesMatch = firstLine.match(/(.+?)\s+\(([A-Z]{3})\)\s+([\d\.]+)\s+milhas/i);
  if (milesMatch) {
    parsed.cidade_destino = milesMatch[1].trim();
    parsed.destino = milesMatch[2].toUpperCase();
    parsed.valor_milhas = milesMatch[3].replace(/\./g, "");
  }

  let currentDatesTarget = "";
  let idaRouteLabel = "";

  lines.forEach((line) => {
    const normalized = normalizeText(line);

    if (!parsed.classe && normalized.includes("econom")) {
      parsed.classe = "economica";
      return;
    }
    if (!parsed.classe && (normalized.includes("execut") || normalized.includes("business"))) {
      parsed.classe = "executiva";
      return;
    }

    const programMatch = line.match(/Programa\s+(.+)$/i);
    if (programMatch && !parsed.programa_fidelidade) {
      parsed.programa_fidelidade = programMatch[1].trim();
      return;
    }

    const companyMatch = line.match(/Voando\s+(.+)$/i);
    if (companyMatch && !parsed.companhia_aerea) {
      const companyRaw = companyMatch[1].trim();
      parsed.companhia_aerea = normalizeText(companyRaw) === "latam" ? "LATAM" : companyRaw;
      return;
    }

    const routeMatch = line.match(/(.+?)\s+\(([A-Z]{3})\)\s*>\s*(.+?)\s+\(([A-Z]{3})\)/);
    if (routeMatch) {
      if (!parsed.origem) {
        parsed.origem = routeMatch[2].toUpperCase();
        parsed.destino = parsed.destino || routeMatch[4].toUpperCase();
        parsed.cidade_destino = parsed.cidade_destino || routeMatch[3].trim();
        idaRouteLabel = `${routeMatch[1].trim()} (${routeMatch[2].toUpperCase()}) → ${routeMatch[3].trim()} (${routeMatch[4].toUpperCase()})`;
      }
      return;
    }

    if (normalized.includes("disponibilidade de ida")) {
      currentDatesTarget = "datas_ida";
      return;
    }
    if (normalized.includes("disponibilidade de volta")) {
      currentDatesTarget = "datas_volta";
      return;
    }
    if (currentDatesTarget && /[A-Za-z]{3}\/\d{2}\s*:/.test(line)) {
      parsed[currentDatesTarget] = [
        ...parsed[currentDatesTarget],
        ...parseDatesLine(line),
      ];
    }
  });

  if (parsed.cidade_destino && parsed.valor_milhas) {
    parsed.titulo = `${parsed.cidade_destino} por ${Number(parsed.valor_milhas).toLocaleString("pt-BR")} milhas + taxas`;
  }

  const destinationAirport = findAirportByIata(parsed.destino);
  if (destinationAirport) {
    parsed.cidade_destino =
      parsed.cidade_destino ||
      destinationAirport.cidade_resolvida ||
      destinationAirport.cidade ||
      destinationAirport.nome ||
      "";
    parsed.pais = parsed.pais || destinationAirport.pais || "";
    parsed.continente = parsed.continente || destinationAirport.continente || "";
  }

  const resumo = [];
  if (parsed.valor_milhas) {
    resumo.push(`Custo do trecho: ${Number(parsed.valor_milhas).toLocaleString("pt-BR")} milhas + taxas`);
  }
  if (parsed.classe === "economica") {
    resumo.push("Classe Econômica");
  } else if (parsed.classe === "executiva") {
    resumo.push("Classe Executiva");
  }
  if (parsed.companhia_aerea) {
    resumo.push(`Voando ${parsed.companhia_aerea}`);
  }
  if (parsed.programa_fidelidade) {
    resumo.push(`Programa ${parsed.programa_fidelidade}`);
  }
  if (idaRouteLabel) {
    resumo.push(idaRouteLabel);
  }
  if (parsed.datas_ida.length) {
    resumo.push(`Ida: ${parsed.datas_ida.join(", ")}`);
  }
  if (parsed.datas_volta.length) {
    resumo.push(`Volta: ${parsed.datas_volta.join(", ")}`);
  }
  parsed.conteudo = resumo.join("\n");

  return parsed;
};

const fillField = (form, name, value) => {
  const field = form.querySelector(`[name="${name}"]`);
  if (!field || value === undefined || value === null || value === "") {
    return;
  }
  if (field.tagName === "SELECT") {
    const desired = normalizeLooseText(String(value));
    const matchingOption = Array.from(field.options).find((option) => {
      const optionValue = normalizeLooseText(option.value);
      const optionText = normalizeLooseText(option.textContent || "");
      return optionValue === desired || optionText === desired || optionText.includes(desired) || desired.includes(optionText);
    });
    field.value = matchingOption ? matchingOption.value : value;
  } else {
    field.value = value;
  }
  field.dispatchEvent(new Event("change", { bubbles: true }));
};

const setupAutopreenchimento = () => {
  const form = document.querySelector("[data-alerta-form]");
  const trigger = document.querySelector("[data-alerta-autopreencher]");
  if (!form || !trigger) {
    return;
  }

  trigger.addEventListener("click", () => {
    const rawField = form.querySelector('[name="alerta_bruto"]');
    const parsed = parseAlertaBruto(rawField ? rawField.value : "");
    if (!parsed.titulo && !parsed.origem && !parsed.destino && !parsed.programa_fidelidade) {
      window.alert("Não foi possível interpretar esse alerta nesse formato.");
      return;
    }

    fillField(form, "titulo", parsed.titulo);
    fillField(form, "conteudo", parsed.conteudo);
    fillField(form, "continente", parsed.continente);
    fillField(form, "pais", parsed.pais);
    fillField(form, "cidade_destino", parsed.cidade_destino);
    fillField(form, "origem", parsed.origem);
    fillField(form, "destino", parsed.destino);
    fillField(form, "classe", parsed.classe);
    fillField(form, "programa_fidelidade", parsed.programa_fidelidade);
    fillField(form, "companhia_aerea", parsed.companhia_aerea);
    fillField(form, "valor_milhas", parsed.valor_milhas);

    document.querySelectorAll("[data-date-group]").forEach((groupEl) => {
      const groupType = groupEl.dataset.dateGroup;
      if (groupType === "ida" && typeof groupEl.__setDates === "function") {
        groupEl.__setDates(parsed.datas_ida);
      }
      if (groupType === "volta" && typeof groupEl.__setDates === "function") {
        groupEl.__setDates(parsed.datas_volta);
      }
    });
  });
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-date-group]").forEach(setupDateGroup);
  setupAutopreenchimento();
});
