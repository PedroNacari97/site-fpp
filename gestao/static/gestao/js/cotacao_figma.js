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
    dataIda: qs("#id_data_ida"),
    dataVolta: qs("#id_data_volta"),
    possuiVolta: qs("#possui-volta"),
    horarioVolta: qs("#horario-volta"),
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
    routeOrigin: qs("#route-preview-origin"),
    routeDestination: qs("#route-preview-destination"),
    resumoTrechos: qs("#resumo-trechos"),
    resumoDatas: qs("#resumo-datas"),
    resumoPassageiros: qs("#resumo-passageiros"),
    resumoValores: qs("#resumo-valores"),
    resumoFinanceiro: qs("#resumo-financeiro"),
    previewBase: qs("#preview-base"),
    previewParcelado: qs("#preview-parcelado"),
    previewVista: qs("#preview-vista"),
    previewEconomia: qs("#preview-economia"),
  };

  const toNumber = (value) => {
    if (value === null || value === undefined || value === "") return 0;
    return Number(String(value).replace(",", ".")) || 0;
  };

  const formatCurrency = (value) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(toNumber(value));

  const getSelectedText = (select) => select?.selectedOptions?.[0]?.textContent?.trim() || "-";

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
    const saldo = selected.saldo === null || selected.saldo === undefined ? "Saldo nao informado" : `Saldo: ${selected.saldo} pontos`;
    const custo = `Custo medio: ${formatCurrency(selected.valor_medio || 0)}`;
    refs.programaInfo.textContent = `${saldo} | ${custo}`;
    if (refs.valorMilheiro && !refs.valorMilheiro.value) {
      refs.valorMilheiro.value = String(toNumber(selected.valor_medio || 0).toFixed(2));
    }
  }

  function updateProgramaOptions() {
    if (!refs.programa) return;
    const previous = refs.programa.value;
    refs.programa.innerHTML = '<option value=""></option>';
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
    if (refs.contaAdmWrapper) refs.contaAdmWrapper.style.display = tipo === "administrada" ? "block" : "none";
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
      if (refs.voltaTemEscala) refs.voltaTemEscala.checked = false;
      if (refs.escalaVoltaWrapper) refs.escalaVoltaWrapper.classList.remove("is-visible");
      const qtdEscalasVolta = qs("#id_qtd_escalas_volta");
      if (qtdEscalasVolta) qtdEscalasVolta.value = "0";
      const totalEscalasVolta = qs("#id_total_escalas_volta");
      if (totalEscalasVolta) totalEscalasVolta.value = "0";
      const container = qs("#escalas-volta-container");
      if (container) container.innerHTML = "";
    }
  }

  function buildScaleRow(tipo, index, data) {
    const row = document.createElement("div");
    row.className = "quote-scale-row";
    row.dataset.index = String(index);
    const options = ['<option value=""></option>']
      .concat(aeroportos.map((airport) => `<option value="${airport.id}">${airport.sigla} - ${airport.nome}</option>`))
      .join("");
    row.innerHTML = `
      <div class="quote-scale-row__head">
        <span class="quote-scale-row__title">Escala ${index + 1}</span>
        <button type="button" class="quote-scale-row__remove" data-remove-escala="${tipo}" data-index="${index}">Remover</button>
      </div>
      <div class="quote-scale-row__grid">
        <div>
          <label class="quote-label">Aeroporto</label>
          <select name="escala-${tipo}-${index}-aeroporto">${options}</select>
        </div>
        <div>
          <label class="quote-label">Horario da escala</label>
          <input type="time" name="escala-${tipo}-${index}-duracao" value="${data?.duracao || ""}">
        </div>
        <div>
          <label class="quote-label">Cidade / pais</label>
          <input type="text" name="escala-${tipo}-${index}-cidade" value="${data?.cidade || ""}">
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

  function updateResumoVisual() {
    const origem = getSelectedText(refs.origem);
    const destino = getSelectedText(refs.destino);
    const dataIda = refs.dataIda?.value || "";
    const dataVolta = refs.dataVolta?.value || "";
    const idaEscalas = Number(qs("#id_qtd_escalas_ida")?.value || 0);
    const voltaEscalas = Number(qs("#id_qtd_escalas_volta")?.value || 0);
    const qtdPassageiros = refs.qtdPassageiros?.value || "0";
    const classe = getSelectedText(refs.classe);
    const valorPassagem = toNumber(refs.valorPassagem?.value);
    const taxas = toNumber(refs.taxas?.value);
    const milhas = toNumber(refs.milhas?.value);
    const valorMilheiro = toNumber(refs.valorMilheiro?.value);
    const juros = toNumber(refs.juros?.value || 1);
    const desconto = toNumber(refs.desconto?.value || 1);

    const base = (milhas / 1000) * valorMilheiro + taxas;
    const parcelado = base * (juros || 1);
    const vista = parcelado * (desconto || 1);
    const economia = valorPassagem - vista;

    if (refs.routeOrigin) refs.routeOrigin.textContent = origem;
    if (refs.routeDestination) refs.routeDestination.textContent = destino;
    if (refs.resumoTrechos) {
      refs.resumoTrechos.textContent =
        origem !== "-" && destino !== "-"
          ? `${origem} -> ${destino}${idaEscalas ? ` | Ida com ${idaEscalas} escala(s)` : ""}${voltaEscalas ? ` | Volta com ${voltaEscalas} escala(s)` : ""}`
          : "Preencha origem e destino.";
    }
    if (refs.resumoDatas) {
      refs.resumoDatas.textContent = `${dataIda ? `Ida: ${dataIda}` : "Ida pendente"} | ${hasVolta() ? (dataVolta ? `Volta: ${dataVolta}` : "Volta pendente") : "Somente ida"}`;
    }
    if (refs.resumoPassageiros) {
      refs.resumoPassageiros.textContent = `${qtdPassageiros} passageiro(s) | ${classe !== "-" ? classe : "Classe nao informada"}`;
    }
    if (refs.resumoValores) {
      refs.resumoValores.textContent = `${valorPassagem ? `Passagem ${formatCurrency(valorPassagem)}` : "Valor da passagem nao informado"} | ${taxas ? `Taxas ${formatCurrency(taxas)}` : "Taxas nao informadas"} | ${milhas ? `${milhas} pontos` : "Pontos nao informados"}`;
    }
    if (refs.resumoFinanceiro) refs.resumoFinanceiro.textContent = `A vista estimado: ${formatCurrency(vista)}`;
    if (refs.previewBase) refs.previewBase.textContent = formatCurrency(base);
    if (refs.previewParcelado) refs.previewParcelado.textContent = formatCurrency(parcelado);
    if (refs.previewVista) refs.previewVista.textContent = formatCurrency(vista);
    if (refs.previewEconomia) refs.previewEconomia.textContent = formatCurrency(economia);
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
    updateResumoVisual();
  });
  refs.dataVolta?.addEventListener("change", () => {
    setVoltaVisibility();
    updateResumoVisual();
  });

  qsa("#id_origem, #id_destino, #id_companhia_aerea, #id_data_ida, #id_qtd_passageiros, #id_classe, #id_valor_passagem, #id_taxas, #id_milhas, #id_valor_milheiro, #id_parcelas, #id_juros, #id_desconto")
    .forEach((field) => field.addEventListener("input", updateResumoVisual));
  qsa("#id_origem, #id_destino, #id_companhia_aerea, #id_data_ida, #id_qtd_passageiros, #id_classe, #id_status, #id_validade")
    .forEach((field) => field.addEventListener("change", updateResumoVisual));

  toggleTitularFields();
  setVoltaVisibility();
  initEscalaSection("ida", escalasIdaData);
  initEscalaSection("volta", escalasVoltaData);
  updateProgramaOptions();
  updateResumoVisual();
})();
