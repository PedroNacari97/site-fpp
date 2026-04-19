(() => {
  const form = document.querySelector(".quote-form-shell");
  if (!form) return;

  const parseScriptJson = (id, fallback) => {
    const node = document.getElementById(id);
    if (!node) return fallback;
    try {
      const parsed = JSON.parse(node.textContent);
      if (typeof parsed === "string") return JSON.parse(parsed);
      return parsed;
    } catch {
      return fallback;
    }
  };

  const escalasIdaData = parseScriptJson("cotacao-escalas-ida", []);
  const escalasVoltaData = parseScriptJson("cotacao-escalas-volta", []);
  const aeroportos = parseScriptJson("cotacao-aeroportos", []);
  const clienteProgramas = parseScriptJson("cotacao-cliente-programas", {});
  const contasAdmProgramas = parseScriptJson("cotacao-contas-programas", {});
  const aeroportosMap = Object.fromEntries(aeroportos.map((airport) => [String(airport.id), airport]));

  const qs = (selector) => document.querySelector(selector);
  const qsa = (selector) => Array.from(document.querySelectorAll(selector));

  const refs = {
    tipoTitular: qs("#id_tipo_titular"),
    cliente: qs("#id_cliente"),
    contaAdm: qs("#id_conta_administrada"),
    programa: qs("#id_programa"),
    programaInfo: qs("#programa-info"),
    clienteWrapper: qs("#cliente-wrapper"),
    contaAdmWrapper: qs("#conta-adm-wrapper"),
    origem: qs("#id_origem"),
    destino: qs("#id_destino"),
    companhia: qs("#id_companhia_aerea"),
    routeCompanhia: qs("#route-preview-companhia"),
    dataIda: qs("#id_data_ida"),
    dataVolta: qs("#id_data_volta"),
    duracaoIda: qs("#id_duracao_voo_ida_minutos"),
    duracaoVolta: qs("#id_duracao_voo_volta_minutos"),
    fusoIda: qs("#id_fuso_horario_ida"),
    fusoVolta: qs("#id_fuso_horario_volta"),
    possuiVolta: qs("#possui-volta"),
    idaTemFuso: qs("#ida-tem-fuso"),
    voltaTemFuso: qs("#volta-tem-fuso"),
    horarioVolta: qs("#horario-volta"),
    idaFusoWrapper: qs("#ida-fuso-wrapper"),
    voltaFusoWrapper: qs("#volta-fuso-wrapper"),
    idaTemEscala: qs("#ida-tem-escala"),
    voltaTemEscala: qs("#volta-tem-escala"),
    escalaIdaWrapper: qs("#escala-ida-wrapper"),
    escalaVoltaWrapper: qs("#escala-volta-wrapper"),
    qtdPassageiros: qs("#id_qtd_passageiros"),
    classe: qs("#id_classe"),
    valorPassagem: qs("#id_valor_passagem"),
    taxas: qs("#id_taxas"),
    milhas: qs("#id_milhas"),
    valorMilheiro: qs("#id_valor_milheiro"),
    parcelas: qs("#id_parcelas"),
    juros: qs("#id_juros"),
    desconto: qs("#id_desconto"),
    mostrarValorParcelado: qs("#id_mostrar_valor_parcelado"),
    status: qs("#id_status"),
    validade: qs("#id_validade"),
    observacoes: qs("#id_observacoes"),
    routeOrigin: qs("#route-preview-origin"),
    routeDestination: qs("#route-preview-destination"),
    routeArrivalIda: qs("#route-preview-arrival-ida"),
    routeArrivalVolta: qs("#route-preview-arrival-volta"),
    heroStatus: qs("#quote-hero-status"),
    summaryClientName: qs("#summary-client-name"),
    summaryProgramName: qs("#summary-program-name"),
    summaryOriginCode: qs("#summary-origin-code"),
    summaryOriginCity: qs("#summary-origin-city"),
    summaryDestinationCode: qs("#summary-destination-code"),
    summaryDestinationCity: qs("#summary-destination-city"),
    resumoDatas: qs("#resumo-datas"),
    resumoPassageiros: qs("#resumo-passageiros"),
    resumoRateio: qs("#resumo-rateio"),
    resumoFinanceiro: qs("#resumo-financeiro"),
    summaryValorPassagem: qs("#summary-valor-passagem"),
    summaryValorTaxas: qs("#summary-valor-taxas"),
    summaryValorMilhas: qs("#summary-valor-milhas"),
    summaryValorTotal: qs("#summary-valor-total"),
    summaryStatusBadge: qs("#summary-status-badge"),
    summaryMissingList: qs("#summary-missing-list"),
    previewBase: qs("#preview-base"),
    previewBaseDetail: qs("#preview-base-detail"),
    previewParcelado: qs("#preview-parcelado"),
    previewParceladoDetail: qs("#preview-parcelado-detail"),
    previewParceladoCard: qs("#preview-parcelado-card"),
    previewVista: qs("#preview-vista"),
    previewVistaDetail: qs("#preview-vista-detail"),
    previewEconomia: qs("#preview-economia"),
    previewEconomiaDetail: qs("#preview-economia-detail"),
    parcelasConfigWrapper: qs("#parcelado-config-wrapper"),
    jurosConfigWrapper: qs("#juros-config-wrapper"),
  };

  const toNumber = (value) => {
    if (value === null || value === undefined || value === "") return 0;
    return Number(String(value).replace(",", ".")) || 0;
  };

  const formatCurrency = (value) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(toNumber(value));

  const getSelectedText = (select, fallback = "-") => {
    const text = select?.selectedOptions?.[0]?.textContent?.trim() || "";
    return text || fallback;
  };

  const formatDateTime = (value) => {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(parsed);
  };

  const parseDurationMinutes = (value) => {
    if (!value) return 0;
    const [hours, minutes] = String(value).split(":").map((item) => Number(item || 0));
    if (Number.isNaN(hours) || Number.isNaN(minutes)) return 0;
    return (hours * 60) + minutes;
  };

  const calculateArrival = (departureValue, durationMinutes, timezoneOffsetHours, escalasMinutes) => {
    if (!departureValue || !durationMinutes) return null;
    const departure = new Date(departureValue);
    if (Number.isNaN(departure.getTime())) return null;
    const escalas = Number(escalasMinutes) || 0;
    return new Date(departure.getTime() + ((durationMinutes + escalas + (timezoneOffsetHours * 60)) * 60000));
  };

  const sumEscalaMinutes = (tipo) => {
    const container = document.querySelector(`#escalas-${tipo}-container`);
    if (!container) return 0;
    let total = 0;
    container.querySelectorAll('input[type="time"][name*="-duracao"]').forEach((input) => {
      total += parseDurationMinutes(input.value);
    });
    return total;
  };

  const getAirportMeta = (select) => {
    const id = select?.value ? String(select.value) : "";
    if (!id) return { code: "---", city: select === refs.origem ? "Origem" : "Destino", label: "---" };
    const airport = aeroportosMap[id];
    if (!airport) {
      const text = getSelectedText(select, "---");
      const parts = text.split(" - ");
      return { code: parts[0] || "---", city: parts.slice(1).join(" - ") || text, label: text };
    }
    return {
      code: airport.sigla || "---",
      city: airport.cidade || airport.nome || "---",
      label: `${airport.sigla || "---"} - ${airport.nome || airport.cidade || "---"}`,
    };
  };

  function getProgramasDisponiveis() {
    if (refs.tipoTitular?.value === "administrada") {
      return refs.contaAdm?.value ? contasAdmProgramas[refs.contaAdm.value] || [] : [];
    }
    return refs.cliente?.value ? clienteProgramas[refs.cliente.value] || [] : [];
  }

  function getCurrentProgram() {
    return getProgramasDisponiveis().find((item) => String(item.id) === String(refs.programa?.value || ""));
  }

  function updateProgramaInfo() {
    const selected = getCurrentProgram();
    if (!refs.programaInfo) return;
    if (!selected) {
      refs.programaInfo.textContent = "";
      return;
    }
    const saldo =
      selected.saldo === null || selected.saldo === undefined
        ? "Saldo nao informado"
        : `Saldo: ${selected.saldo} pontos`;
    const custo = `Custo medio: ${formatCurrency(selected.valor_medio || 0)}`;
    refs.programaInfo.textContent = `${saldo} | ${custo}`;
    if (refs.valorMilheiro && !refs.valorMilheiro.value) {
      refs.valorMilheiro.value = String(toNumber(selected.valor_medio || 0).toFixed(2));
    }
  }

  function updateProgramaOptions() {
    if (!refs.programa) return;
    const previous = refs.programa.value;
    refs.programa.innerHTML = '<option value="">Selecione o programa</option>';
    getProgramasDisponiveis().forEach((programa) => {
      const option = document.createElement("option");
      option.value = programa.id;
      option.textContent = programa.nome;
      refs.programa.appendChild(option);
    });
    if (Array.from(refs.programa.options).some((option) => option.value === previous)) {
      refs.programa.value = previous;
    }
    updateProgramaInfo();
  }

  function toggleTitularFields() {
    const tipo = refs.tipoTitular?.value || "cliente";
    if (refs.clienteWrapper) refs.clienteWrapper.style.display = "block";
    if (refs.contaAdmWrapper) refs.contaAdmWrapper.style.display = tipo === "administrada" ? "grid" : "none";
    if (tipo !== "administrada" && refs.contaAdm) refs.contaAdm.value = "";
    updateProgramaOptions();
  }

  function hasVolta() {
    return Boolean(refs.possuiVolta?.checked || refs.dataVolta?.value);
  }

  function setVoltaVisibility() {
    const shouldShow = hasVolta();
    if (refs.horarioVolta) refs.horarioVolta.classList.toggle("is-visible", shouldShow);
    if (refs.possuiVolta) refs.possuiVolta.checked = shouldShow;
    if (!shouldShow) {
      if (refs.dataVolta) refs.dataVolta.value = "";
      if (refs.duracaoVolta) refs.duracaoVolta.value = "";
      if (refs.voltaTemEscala) refs.voltaTemEscala.checked = false;
      if (refs.voltaTemFuso) refs.voltaTemFuso.checked = false;
      if (refs.escalaVoltaWrapper) refs.escalaVoltaWrapper.classList.remove("is-visible");
      const qtdEscalasVolta = qs("#id_qtd_escalas_volta");
      if (qtdEscalasVolta) qtdEscalasVolta.value = "0";
      const totalEscalasVolta = qs("#id_total_escalas_volta");
      if (totalEscalasVolta) totalEscalasVolta.value = "0";
      const container = qs("#escalas-volta-container");
      if (container) container.innerHTML = "";
    }
  }

  function setFusoVisibility() {
    const idaHasOffset = Boolean(refs.idaTemFuso?.checked || toNumber(refs.fusoIda?.value));
    if (refs.idaFusoWrapper) refs.idaFusoWrapper.classList.toggle("is-visible", idaHasOffset);
    if (refs.idaTemFuso) refs.idaTemFuso.checked = idaHasOffset;
    if (!idaHasOffset && refs.fusoIda) refs.fusoIda.value = "0";

    const voltaEnabled = hasVolta();
    const voltaHasOffset = Boolean(voltaEnabled && (refs.voltaTemFuso?.checked || toNumber(refs.fusoVolta?.value)));
    if (refs.voltaFusoWrapper) refs.voltaFusoWrapper.classList.toggle("is-visible", voltaHasOffset);
    if (refs.voltaTemFuso) refs.voltaTemFuso.checked = voltaHasOffset;
    if ((!voltaEnabled || !voltaHasOffset) && refs.fusoVolta) refs.fusoVolta.value = "0";
  }

  function buildScaleRow(tipo, index, data) {
    const row = document.createElement("div");
    row.className = "quote-scale-row";
    row.dataset.index = String(index);
    const options = ['<option value="">Selecione o aeroporto</option>']
      .concat(aeroportos.map((airport) => `<option value="${airport.id}">${airport.sigla} - ${airport.nome}</option>`))
      .join("");
    row.innerHTML = `
      <div class="quote-scale-row__head">
        <span class="quote-scale-row__title">Escala ${index + 1}</span>
      </div>
      <div class="quote-scale-row__grid">
        <div>
          <label class="quote-label">IATA da escala</label>
          <select name="escala-${tipo}-${index}-aeroporto">${options}</select>
        </div>
        <div>
          <label class="quote-label">Cidade / observacao</label>
          <input type="text" name="escala-${tipo}-${index}-cidade" value="${data?.cidade || ""}">
        </div>
        <div>
          <label class="quote-label">Duracao da escala</label>
          <input type="time" name="escala-${tipo}-${index}-duracao" value="${data?.duracao || ""}">
        </div>
        <div class="quote-scale-row__actions">
          <button type="button" class="quote-scale-row__remove" data-remove-escala="${tipo}" data-index="${index}">Remover</button>
        </div>
      </div>
    `;
    const select = row.querySelector(`[name="escala-${tipo}-${index}-aeroporto"]`);
    if (select) select.value = data?.aeroporto_id || data?.aeroporto || "";
    return row;
  }

  function initEscalaSection(tipo, initialData) {
    const toggle = qs(`#${tipo}-tem-escala`);
    const wrapper = qs(`#escala-${tipo}-wrapper`);
    const container = qs(`#escalas-${tipo}-container`);
    const qtd = qs(`#id_qtd_escalas_${tipo}`);
    const total = qs(`#id_total_escalas_${tipo}`);
    const addButton = qs(`[data-add-escala="${tipo}"]`);
    if (!toggle || !wrapper || !container || !qtd || !total) return;

    const collectRows = () =>
      qsa(`#escalas-${tipo}-container .quote-scale-row`).map((row, index) => ({
        aeroporto: row.querySelector(`[name="escala-${tipo}-${index}-aeroporto"]`)?.value || "",
        duracao: row.querySelector(`[name="escala-${tipo}-${index}-duracao"]`)?.value || "",
        cidade: row.querySelector(`[name="escala-${tipo}-${index}-cidade"]`)?.value || "",
      }));

    const renderRows = (rows) => {
      const visible = tipo === "volta" ? hasVolta() && toggle.checked : toggle.checked;
      wrapper.classList.toggle("is-visible", visible);
      if (!visible) {
        if (tipo !== "volta" && !toggle.checked) container.innerHTML = "";
        qtd.value = "0";
        total.value = "0";
        updateResumoVisual();
        return;
      }
      const nextRows = rows && rows.length ? rows : initialData.length ? initialData : [{}];
      container.innerHTML = "";
      nextRows.forEach((item, index) => container.appendChild(buildScaleRow(tipo, index, item)));
      qtd.value = String(nextRows.length);
      total.value = String(nextRows.length);
      qsa(`[data-remove-escala="${tipo}"]`).forEach((button) =>
        button.addEventListener("click", () => {
          const remaining = collectRows();
          remaining.splice(Number(button.dataset.index), 1);
          if (!remaining.length) toggle.checked = false;
          renderRows(remaining);
        }),
      );
      container.querySelectorAll("select, input").forEach((field) => field.addEventListener("input", updateResumoVisual));
      updateResumoVisual();
    };

    if (initialData.length) toggle.checked = true;
    toggle.addEventListener("change", () => renderRows(collectRows()));
    addButton?.addEventListener("click", () => {
      toggle.checked = true;
      const rows = collectRows();
      rows.push({});
      renderRows(rows);
    });
    renderRows(initialData);
  }

  function getStatusLabel() {
    const selected = getSelectedText(refs.status, "");
    const isNew = form.dataset.isNew === "1";
    if (isNew && (!refs.status?.value || refs.status.value === "pendente")) {
      return "Rascunho";
    }
    return selected || "Rascunho";
  }

  function applyStatusVisual(label) {
    const normalized = String(label || "").toLowerCase();
    const targets = [refs.heroStatus, refs.summaryStatusBadge].filter(Boolean);
    targets.forEach((node) => {
      node.textContent = label || "Rascunho";
      node.classList.remove("is-success", "is-danger", "is-info");
      if (normalized.includes("aceita") || normalized.includes("emissao")) {
        node.classList.add("is-success");
      } else if (normalized.includes("rejeitada")) {
        node.classList.add("is-danger");
      } else if (normalized.includes("pendente") || normalized.includes("rascunho")) {
        node.classList.add("is-info");
      }
    });
  }

  function updateResumoVisual() {
    const origem = getAirportMeta(refs.origem);
    const destino = getAirportMeta(refs.destino);
    const companhia = getSelectedText(refs.companhia);
    const dataIda = refs.dataIda?.value || "";
    const dataVolta = refs.dataVolta?.value || "";
    const duracaoIdaMinutos = parseDurationMinutes(refs.duracaoIda?.value);
    const duracaoVoltaMinutos = parseDurationMinutes(refs.duracaoVolta?.value);
    const fusoIda = refs.idaTemFuso?.checked ? toNumber(refs.fusoIda?.value) : 0;
    const fusoVolta = refs.voltaTemFuso?.checked ? toNumber(refs.fusoVolta?.value) : 0;
    const idaEscalas = Number(qs("#id_qtd_escalas_ida")?.value || 0);
    const voltaEscalas = Number(qs("#id_qtd_escalas_volta")?.value || 0);
    const escalasIdaMinutos = idaEscalas > 0 ? sumEscalaMinutes("ida") : 0;
    const escalasVoltaMinutos = voltaEscalas > 0 ? sumEscalaMinutes("volta") : 0;
    const chegadaIda = calculateArrival(dataIda, duracaoIdaMinutos, fusoIda, escalasIdaMinutos);
    const chegadaVolta = calculateArrival(dataVolta, duracaoVoltaMinutos, fusoVolta, escalasVoltaMinutos);
    const qtdPassageiros = refs.qtdPassageiros?.value || "0";
    const qtdPassageirosNum = Math.max(parseInt(qtdPassageiros, 10) || 0, 0);
    const factor = qtdPassageirosNum || 1;
    const classe = getSelectedText(refs.classe, "Classe nao informada");
    const valorPassagem = toNumber(refs.valorPassagem?.value);
    const taxas = toNumber(refs.taxas?.value);
    const milhas = toNumber(refs.milhas?.value);
    const valorMilheiro = toNumber(refs.valorMilheiro?.value);
    const juros = toNumber(refs.juros?.value || 0);
    const desconto = toNumber(refs.desconto?.value || 0);
    const mostrarValorParcelado = refs.mostrarValorParcelado?.checked ?? true;
    const clienteLabel =
      refs.tipoTitular?.value === "administrada"
        ? getSelectedText(refs.contaAdm, "---")
        : getSelectedText(refs.cliente, "---");
    const programaLabel = getSelectedText(refs.programa, "Nenhum programa selecionado");

    const passagemUnit = valorPassagem;
    const taxasUnit = taxas;
    const valorEncontradoUnit = (milhas / 1000) * valorMilheiro;
    const baseUnit = valorEncontradoUnit + taxasUnit;
    const parceladoUnit = baseUnit * (1 + (juros || 0) / 100);
    const vistaUnit = parceladoUnit * (1 - (desconto || 0) / 100);
    const economiaUnit = passagemUnit - vistaUnit;
    const passagemTotal = passagemUnit * factor;
    const taxasTotal = taxasUnit * factor;
    const milhasTotal = milhas * factor;
    const valorEncontradoTotal = valorEncontradoUnit * factor;
    const baseTotal = baseUnit * factor;
    const parceladoTotal = parceladoUnit * factor;
    const vistaTotal = vistaUnit * factor;
    const economiaTotal = economiaUnit * factor;
    const passengerDetail = qtdPassageirosNum
      ? `${qtdPassageirosNum} passageiro(s)`
      : "quantidade pendente";
    if (refs.routeOrigin) refs.routeOrigin.textContent = origem.label;
    if (refs.routeDestination) refs.routeDestination.textContent = destino.label;
    if (refs.routeArrivalIda) refs.routeArrivalIda.textContent = chegadaIda ? formatDateTime(chegadaIda) : "--";
    if (refs.routeArrivalVolta) refs.routeArrivalVolta.textContent = chegadaVolta ? formatDateTime(chegadaVolta) : "--";
    if (refs.routeCompanhia) refs.routeCompanhia.textContent = companhia;
    if (refs.summaryClientName) refs.summaryClientName.textContent = clienteLabel;
    if (refs.summaryProgramName) refs.summaryProgramName.textContent = programaLabel;
    if (refs.summaryOriginCode) refs.summaryOriginCode.textContent = origem.code;
    if (refs.summaryOriginCity) refs.summaryOriginCity.textContent = origem.city;
    if (refs.summaryDestinationCode) refs.summaryDestinationCode.textContent = destino.code;
    if (refs.summaryDestinationCity) refs.summaryDestinationCity.textContent = destino.city;
    if (refs.resumoDatas) {
      const idaResumo = dataIda
        ? `Ida: ${formatDateTime(dataIda)}${chegadaIda ? ` -> ${formatDateTime(chegadaIda)}` : ""}`
        : "Ida pendente";
      const voltaResumo = hasVolta()
        ? (dataVolta ? `Volta: ${formatDateTime(dataVolta)}${chegadaVolta ? ` -> ${formatDateTime(chegadaVolta)}` : ""}` : "Volta pendente")
        : "Somente ida";
      refs.resumoDatas.textContent = `${idaResumo} | ${voltaResumo}`;
    }
    if (refs.resumoPassageiros) {
      refs.resumoPassageiros.textContent = `${qtdPassageiros} passageiro(s) | ${classe}`;
    }
    if (refs.resumoRateio) {
      refs.resumoRateio.textContent = `Campos monetarios e milhas por pessoa | Totais com ${passengerDetail}.`;
    }
    if (refs.summaryValorPassagem) refs.summaryValorPassagem.textContent = formatCurrency(passagemTotal);
    if (refs.summaryValorTaxas) refs.summaryValorTaxas.textContent = formatCurrency(taxasTotal);
    if (refs.summaryValorMilhas) {
      refs.summaryValorMilhas.textContent = milhas
        ? qtdPassageirosNum
          ? `${milhas.toLocaleString("pt-BR")} por pax | ${milhasTotal.toLocaleString("pt-BR")} total`
          : `${milhas.toLocaleString("pt-BR")} por pax`
        : "0";
    }
    if (refs.summaryValorTotal) refs.summaryValorTotal.textContent = formatCurrency(vistaTotal);
    if (refs.resumoFinanceiro) {
      refs.resumoFinanceiro.textContent = mostrarValorParcelado
        ? `Valor encontrado: ${formatCurrency(valorEncontradoTotal)} | Valor total: ${formatCurrency(vistaTotal)}`
        : `Valor encontrado: ${formatCurrency(valorEncontradoTotal)} | Valor total: ${formatCurrency(vistaTotal)}`;
    }
    if (refs.previewBase) refs.previewBase.textContent = formatCurrency(valorEncontradoTotal);
    if (refs.previewBaseDetail) refs.previewBaseDetail.textContent = `${formatCurrency(valorEncontradoUnit)} por pessoa${qtdPassageirosNum ? ` x ${qtdPassageirosNum} = ${formatCurrency(valorEncontradoTotal)}` : ""}`;
    if (refs.previewParcelado) refs.previewParcelado.textContent = formatCurrency(parceladoTotal);
    if (refs.previewParceladoDetail) refs.previewParceladoDetail.textContent = `${formatCurrency(parceladoUnit)} por pessoa${qtdPassageirosNum ? ` x ${qtdPassageirosNum} = ${formatCurrency(parceladoTotal)}` : ""}`;
    if (refs.previewParceladoCard) refs.previewParceladoCard.classList.toggle("quote-hidden", !mostrarValorParcelado);
    if (refs.previewVista) refs.previewVista.textContent = formatCurrency(vistaTotal);
    if (refs.previewVistaDetail) refs.previewVistaDetail.textContent = `${formatCurrency(vistaUnit)} por pessoa${qtdPassageirosNum ? ` x ${qtdPassageirosNum} = ${formatCurrency(vistaTotal)}` : ""}`;
    if (refs.previewEconomia) refs.previewEconomia.textContent = formatCurrency(economiaTotal);
    if (refs.previewEconomiaDetail) refs.previewEconomiaDetail.textContent = `${formatCurrency(economiaUnit)} por pessoa${qtdPassageirosNum ? ` x ${qtdPassageirosNum} = ${formatCurrency(economiaTotal)}` : ""}`;
    if (refs.parcelasConfigWrapper) refs.parcelasConfigWrapper.classList.toggle("quote-hidden", !mostrarValorParcelado);
    if (refs.jurosConfigWrapper) refs.jurosConfigWrapper.classList.toggle("quote-hidden", !mostrarValorParcelado);

    const statusLabel = getStatusLabel();
    applyStatusVisual(statusLabel);

    const missing = [];
    if (!refs.tipoTitular?.value) missing.push("Tipo de titular");
    if (refs.tipoTitular?.value === "administrada") {
      if (!refs.contaAdm?.value) missing.push("Conta administrada");
    } else if (!refs.cliente?.value) {
      missing.push("Cliente");
    }
    if (!refs.origem?.value) missing.push("Origem");
    if (!refs.destino?.value) missing.push("Destino");
    if (!refs.companhia?.value) missing.push("Companhia");
    if (!refs.dataIda?.value) missing.push("Data da ida");
    if (hasVolta() && !refs.dataVolta?.value) missing.push("Data da volta");
    if (!refs.qtdPassageiros?.value) missing.push("Quantidade de passageiros");
    if (!refs.classe?.value) missing.push("Classe");
    if (!refs.valorPassagem?.value) missing.push("Valor da passagem");
    if (!refs.taxas?.value) missing.push("Taxas");
    if (!refs.status?.value) missing.push("Status");
    if (refs.idaTemEscala?.checked && idaEscalas === 0) missing.push("Escalas da ida");
    if (hasVolta() && refs.voltaTemEscala?.checked && voltaEscalas === 0) missing.push("Escalas da volta");

    if (refs.summaryMissingList) {
      refs.summaryMissingList.innerHTML = "";
      if (!missing.length) {
        const item = document.createElement("li");
        item.textContent = "Tudo pronto para salvar a cotacao.";
        item.className = "is-ok";
        refs.summaryMissingList.appendChild(item);
      } else {
        missing.forEach((label) => {
          const item = document.createElement("li");
          item.textContent = label;
          refs.summaryMissingList.appendChild(item);
        });
      }
    }
  }

  refs.tipoTitular?.addEventListener("change", () => {
    toggleTitularFields();
    updateResumoVisual();
  });
  refs.cliente?.addEventListener("change", () => {
    updateProgramaOptions();
    updateResumoVisual();
  });
  refs.contaAdm?.addEventListener("change", () => {
    updateProgramaOptions();
    updateResumoVisual();
  });
  refs.programa?.addEventListener("change", () => {
    updateProgramaInfo();
    updateResumoVisual();
  });
  refs.possuiVolta?.addEventListener("change", () => {
    setVoltaVisibility();
    setFusoVisibility();
    updateResumoVisual();
  });
  refs.idaTemFuso?.addEventListener("change", () => {
    setFusoVisibility();
    updateResumoVisual();
  });
  refs.voltaTemFuso?.addEventListener("change", () => {
    setFusoVisibility();
    updateResumoVisual();
  });
  refs.mostrarValorParcelado?.addEventListener("change", updateResumoVisual);
  refs.dataVolta?.addEventListener("change", () => {
    setVoltaVisibility();
    setFusoVisibility();
    updateResumoVisual();
  });

  qsa(
    "#id_origem, #id_destino, #id_companhia_aerea, #id_data_ida, #id_data_volta, #id_duracao_voo_ida_minutos, #id_duracao_voo_volta_minutos, #id_fuso_horario_ida, #id_fuso_horario_volta, #id_qtd_passageiros, #id_classe, #id_valor_passagem, #id_taxas, #id_milhas, #id_valor_milheiro, #id_parcelas, #id_juros, #id_desconto, #id_status, #id_validade, #id_observacoes",
  ).forEach((field) => {
    field.addEventListener("input", updateResumoVisual);
    field.addEventListener("change", updateResumoVisual);
  });

  toggleTitularFields();
  setVoltaVisibility();
  setFusoVisibility();
  initEscalaSection("ida", escalasIdaData);
  initEscalaSection("volta", escalasVoltaData);
  updateProgramaOptions();
  updateResumoVisual();
})();
