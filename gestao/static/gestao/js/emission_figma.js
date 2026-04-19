(async () => {
  const context = window.emissionWizardContext || {};
  const form = document.querySelector(".emission-form-shell");
  if (!form) return;

  const TOTAL_STEPS = 6;
  const loadedDraft = loadDraft();
  let currentStep = 1;

  const qs = (selector) => document.querySelector(selector);
  const qsa = (selector) => Array.from(document.querySelectorAll(selector));

  const refs = {
    stepButtons: qsa(".wizard-stepper__item"),
    stepBlocks: qsa(".wizard-step"),
    returnStepButton: qs('.wizard-stepper__item[data-go-step="3"]'),
    prevButton: qs("#wizard-prev"),
    nextButton: qs("#wizard-next"),
    finishButton: qs("#submit-emissao"),
    reviewGrid: qs("#review-grid"),
    autosaveLabel: qs("#wizard-autosave"),
    tipoEmissao: qs("#id_tipo_emissao"),
    cliente: qs("#id_cliente"),
    contaAdm: qs("#id_conta_administrada"),
    emissorParceiro: qs("#id_emissor_parceiro"),
    programa: qs("#id_programa"),
    tipoCards: qs("#tipo-emissao-cards"),
    programaCards: qs("#programa-cards"),
    clienteWrapper: qs("#cliente-wrapper"),
    contaAdmWrapper: qs("#conta-adm-wrapper"),
    emissorParceiroWrapper: qs("#emissor-parceiro-wrapper"),
    modeloOperacional: qs("#id_modelo_operacional"),
    modeloOperacionalWrapper: qs("#modelo-operacional-wrapper"),
    tipoOperacao: qs("#id_tipo_operacao"),
    valorReferenciaWrapper: qs("#id_valor_referencia")?.closest("div") || null,
    economiaWrapper: qs("#id_economia_obtida")?.closest("div") || null,
    contaAdmRequired: qs("#conta-adm-required"),
    routeOrigin: qs("#route-preview-origin"),
    routeDestination: qs("#route-preview-destination"),
    resumoTrechos: qs("#resumo-trechos"),
    resumoDatas: qs("#resumo-datas"),
    resumoPassageiros: qs("#resumo-passageiros"),
    resumoValores: qs("#resumo-valores"),
    programaInfo: qs("#programa-info"),
    cpfUsadosInfo: qs("#cpf-usados-info"),
    cpfConsumoInfo: qs("#cpf-consumo-info"),
    cpfStatusBadge: qs("#cpf-status-badge"),
    cpfLimiteError: qs("#cpf-limite-error"),
    origemField: qs("#id_aeroporto_partida"),
    destinoField: qs("#id_aeroporto_destino"),
    companhiaField: qs("#id_companhia_aerea"),
    dataIda: qs("#id_data_ida"),
    duracaoIda: qs("#id_duracao_voo_ida_minutos"),
    fusoIda: qs("#id_fuso_horario_ida"),
    routeArrivalIda: qs("#route-preview-arrival-ida"),
    routeArrivalVolta: qs("#route-preview-arrival-volta"),
    bagagemMao: qs("#id_bagagem_mao"),
    bagagemDespachada: qs("#id_bagagem_despachada"),
    pontos: qs("#id_pontos_utilizados"),
    valorRefPontos: qs("#id_valor_referencia_pontos"),
    valorTaxas: qs("#id_valor_taxas"),
    valorReferencia: qs("#id_valor_referencia"),
    economia: qs("#id_economia_obtida"),
    custoParceiro: qs("#id_valor_milheiro_parceiro"),
    vendaFinal: qs("#id_valor_venda_final"),
    valorTotalFinal: qs("#id_valor_total_final"),
    lucro: qs("#id_lucro"),
    custoEmissor: qs("#id_custo_emissor"),
    valorCobrado: qs("#id_valor_cobrado_cliente"),
    lucroHighlight: qs("#lucro-highlight"),
    totalHighlight: qs("#total-highlight"),
    economiaHighlight: qs("#economia-highlight"),
    possuiVolta: qs("#possui-volta"),
    dataVolta: qs("#id_data_volta"),
    duracaoVolta: qs("#id_duracao_voo_volta_minutos"),
    fusoVolta: qs("#id_fuso_horario_volta"),
    vooVoltaCard: qs("#voo-volta-card"),
    escalaIdaToggle: qs("#ida-tem-escala"),
    escalaIdaWrapper: qs("#escala-ida-wrapper"),
    qtdEscalasIda: qs("#id_qtd_escalas_ida"),
    escalaVoltaToggle: qs("#volta-tem-escala"),
    escalaVoltaWrapper: qs("#escala-volta-wrapper"),
    qtdEscalasVolta: qs("#id_qtd_escalas_volta"),
    passageirosContainer: qs("#passageiros-container"),
    totalPassageiros: qs("#id_total_passageiros"),
    countAdultos: qs("#id_qtd_adultos"),
    countCriancas: qs("#id_qtd_criancas"),
    countBebes: qs("#id_qtd_bebes"),
    passengerButtons: qsa("[data-passenger-kind]"),
    countAdultosLabel: qs("#count-adulto"),
    countCriancasLabel: qs("#count-crianca"),
    countBebesLabel: qs("#count-bebe"),
  };

  const tipoMeta = {
    cliente: { title: "Conta propria da agencia", description: "Usar milhas/conta da agencia", icon: "CL" },
    administrada: { title: "Conta administrada", description: "Milhas de conta cedida", icon: "ADM" },
    parceiro: { title: "Emissor parceiro", description: "Emissao via parceiro", icon: "PAR" },
    concierge: { title: "Pontos do cliente concierge", description: "Conta e do cliente VIP", icon: "VIP" },
  };

  const passengerKinds = [
    { key: "adulto", title: "Adulto", field: refs.countAdultos, label: refs.countAdultosLabel },
    { key: "crianca", title: "Crianca", field: refs.countCriancas, label: refs.countCriancasLabel },
    { key: "bebe", title: "Bebe", field: refs.countBebes, label: refs.countBebesLabel },
  ];
  const clientContextCache = {};
  const passengerDetailCache = {};

  function loadDraft() {
    return null;
  }

  function saveDraft() {
    if (refs.autosaveLabel) refs.autosaveLabel.textContent = "Rascunho atualizado nesta pagina";
  }

  function applyFieldValues(values) {
    if (!values) return;
    Object.entries(values).forEach(([name, value]) => {
      if (name === "__step") return;
      const field = form.querySelector(`[name="${name}"]`);
      if (!field) return;
      field.type === "checkbox" ? (field.checked = Boolean(value)) : (field.value = value ?? "");
    });
  }

  function formatCurrency(value) {
    const numeric = Number.isFinite(Number(value)) ? Number(value) : 0;
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(numeric);
  }

  function formatDateTime(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(parsed);
  }

  function parseDurationMinutes(value) {
    if (!value) return 0;
    const [hours, minutes] = String(value).split(":").map((item) => Number(item || 0));
    if (Number.isNaN(hours) || Number.isNaN(minutes)) return 0;
    return (hours * 60) + minutes;
  }

  function calculateArrival(departureValue, durationMinutes, timezoneOffsetHours) {
    if (!departureValue || !durationMinutes) return null;
    const departure = new Date(departureValue);
    if (Number.isNaN(departure.getTime())) return null;
    return new Date(departure.getTime() + ((durationMinutes + (timezoneOffsetHours * 60)) * 60000));
  }

  function toNumberSafe(value) {
    const num = Number(value);
    return Number.isFinite(num) ? num : 0;
  }

  function buildContextUrl(template, id) {
    return (template || "").replace("__ID__", String(id));
  }

  async function fetchJson(url) {
    if (!url) return null;
    const response = await fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error(`Falha ao carregar contexto (${response.status})`);
    return response.json();
  }

  async function ensureClientContext(clienteId) {
    const normalizedId = Number(clienteId || 0);
    if (!normalizedId) return null;
    if (clientContextCache[normalizedId]) return clientContextCache[normalizedId];
    const payload = await fetchJson(buildContextUrl(context.clienteContextUrlTemplate, normalizedId));
    clientContextCache[normalizedId] = payload;
    return payload;
  }

  async function ensurePassengerDetail(passageiroId) {
    const normalizedId = Number(passageiroId || 0);
    if (!normalizedId) return null;
    if (passengerDetailCache[normalizedId]) return passengerDetailCache[normalizedId];
    const payload = await fetchJson(buildContextUrl(context.passageiroFrequenteUrlTemplate, normalizedId));
    passengerDetailCache[normalizedId] = payload;
    return payload;
  }

  function getTipoEmissao() {
    return refs.tipoEmissao?.value || "cliente";
  }

  function getClienteTipo() {
    const clienteId = Number(refs.cliente?.value || 0);
    if (!clienteId) return "";
    const fromContext = clientContextCache[clienteId]?.cliente?.tipo_cliente;
    if (fromContext) return fromContext;
    const map = context.clientesTipo || {};
    return map[clienteId] || "";
  }

  function getModeloOperacional() {
    return (refs.modeloOperacional?.value || "").trim();
  }

  function deriveTipoOperacao() {
    const tipo = getTipoEmissao();
    if (tipo === "concierge") return "concierge";
    if (tipo === "parceiro") return "emissor_parceiro";
    const clienteTipo = getClienteTipo();
    const modelo = getModeloOperacional();
    if (clienteTipo === "intermediario" || modelo === "2") return "intermediario";
    return "venda_direta";
  }

  function syncTipoOperacaoField() {
    const tipoOp = deriveTipoOperacao();
    if (refs.tipoOperacao) refs.tipoOperacao.value = tipoOp;
    return tipoOp;
  }

  function getSelectedText(select) {
    return select?.selectedOptions?.[0]?.textContent?.trim() || "-";
  }

  function hasVolta() {
    return Boolean(refs.possuiVolta?.checked || refs.dataVolta?.value);
  }

  function getEnabledSteps() {
    return hasVolta() ? [1, 2, 3, 4, 5, 6] : [1, 2, 4, 5, 6];
  }

  function getNextStep(step) {
    const enabledSteps = getEnabledSteps();
    const index = enabledSteps.indexOf(step);
    return enabledSteps[Math.min(index + 1, enabledSteps.length - 1)] || enabledSteps[enabledSteps.length - 1];
  }

  function getPrevStep(step) {
    const enabledSteps = getEnabledSteps();
    const index = enabledSteps.indexOf(step);
    return enabledSteps[Math.max(index - 1, 0)] || enabledSteps[0];
  }

  function getProgramasDisponiveis() {
    if (getTipoEmissao() === "administrada") {
      const contaId = refs.contaAdm?.value;
      return contaId ? context.contasAdmProgramas?.[contaId] || [] : [];
    }
    if (getTipoEmissao() === "parceiro") return context.empresaProgramas || [];
    const clienteId = refs.cliente?.value;
    return clienteId ? context.clienteProgramas?.[clienteId] || [] : [];
  }

  function getCurrentProgram() {
    return getProgramasDisponiveis().find((item) => String(item.id) === String(refs.programa?.value || ""));
  }

  function emptyState(title, copy) {
    return `<div class="passenger-empty"><div class="passenger-empty__icon">+</div><p class="passenger-empty__title">${title}</p><p class="passenger-empty__copy">${copy}</p></div>`;
  }

  function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "wizard-toast";
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 4000);
  }

  function renderTipoCards() {
    if (!refs.tipoCards || !refs.tipoEmissao) return;
    refs.tipoCards.innerHTML = Object.entries(tipoMeta).map(([value, meta]) => {
      const active = refs.tipoEmissao.value === value ? " is-active" : "";
      return `<button type="button" class="choice-card${active}" data-tipo-card="${value}"><span class="choice-card__icon">${meta.icon}</span><span class="choice-card__title">${meta.title}</span><span class="choice-card__description">${meta.description}</span></button>`;
    }).join("");
    qsa("[data-tipo-card]").forEach((button) => button.addEventListener("click", () => {
      refs.tipoEmissao.value = button.dataset.tipoCard;
      toggleTitularFields();
      saveDraft();
    }));
  }

  function renderProgramCards() {
    if (!refs.programaCards || !refs.programa) return;
    const options = Array.from(refs.programa.options).filter((option) => option.value);
    if (!options.length) {
      refs.programaCards.innerHTML = emptyState("Nenhum programa disponivel", "Selecione um titular compativel para carregar os programas.");
      return;
    }
    refs.programaCards.innerHTML = options.map((option) => {
      const active = refs.programa.value === option.value ? " is-active" : "";
      return `<button type="button" class="choice-card${active}" data-program-card="${option.value}"><span class="choice-card__icon">${option.textContent.slice(0, 1)}</span><span class="choice-card__title">${option.textContent}</span></button>`;
    }).join("");
    qsa("[data-program-card]").forEach((button) => button.addEventListener("click", () => {
      refs.programa.value = button.dataset.programCard;
      updateProgramaInfo();
      saveDraft();
    }));
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
    if (Array.from(refs.programa.options).some((option) => option.value === previous)) refs.programa.value = previous;
    updateProgramaInfo();
  }

  function updateCpfStatus(status) {
    if (!refs.cpfStatusBadge) return;
    refs.cpfStatusBadge.textContent = { disponivel: "Disponivel", proximo: "Proximo do limite", bloqueado: "Bloqueado" }[status] || "Disponivel";
  }

  function updateCpfLimite() {
    if (getTipoEmissao() === "parceiro") {
      if (refs.cpfConsumoInfo) refs.cpfConsumoInfo.textContent = "";
      if (refs.cpfLimiteError) refs.cpfLimiteError.textContent = "";
      if (refs.finishButton) refs.finishButton.disabled = false;
      return;
    }
    const selected = getCurrentProgram();
    if (!selected) {
      if (refs.cpfConsumoInfo) refs.cpfConsumoInfo.textContent = "";
      if (refs.cpfLimiteError) refs.cpfLimiteError.textContent = "";
      if (refs.finishButton) refs.finishButton.disabled = false;
      return;
    }
    const cpfs = qsa('input[name^="passageiro-"][name$="-cpf"]').map((field) => (field.value || "").replace(/\D/g, "")).filter(Boolean);
    const consumo = [...new Set(cpfs)].length;
    const ilimitado = selected.cpfs_total === null || selected.cpfs_total === undefined;
    const bloqueado = selected.status === "bloqueado";
    const excedeuEstimativa = !ilimitado && consumo > Number(selected.cpfs_disponiveis || 0);
    if (refs.cpfConsumoInfo) refs.cpfConsumoInfo.textContent = ilimitado ? `CPFs nesta emissao: ${consumo} • Disponiveis: ilimitado` : `CPFs nesta emissao: ${consumo} • Disponiveis: ${selected.cpfs_disponiveis} de ${selected.cpfs_total}`;
    if (refs.cpfLimiteError) refs.cpfLimiteError.textContent = bloqueado ? "Conta bloqueada para nova emissao." : excedeuEstimativa ? "A validacao final dos CPFs ocorre ao salvar a emissao." : "";
    if (refs.finishButton) refs.finishButton.disabled = bloqueado;
  }

  function updateProgramaInfo() {
    const selected = getCurrentProgram();
    if (!selected) {
      if (refs.programaInfo) refs.programaInfo.textContent = "";
      if (refs.cpfUsadosInfo) refs.cpfUsadosInfo.textContent = "";
      if (refs.cpfConsumoInfo) refs.cpfConsumoInfo.textContent = "";
      if (refs.cpfLimiteError) refs.cpfLimiteError.textContent = "";
      updateCpfStatus("disponivel");
      renderProgramCards();
      recalcValores();
      return;
    }
    const cpfsText = selected.cpfs_total === null || selected.cpfs_total === undefined ? "CPFs disponiveis: ilimitado" : `CPFs disponiveis: ${selected.cpfs_disponiveis} de ${selected.cpfs_total}`;
    if (refs.programaInfo) refs.programaInfo.textContent = selected.saldo !== undefined && selected.saldo !== null ? `Saldo: ${selected.saldo} pontos • Custo medio: ${formatCurrency(selected.valor_medio || 0)} • ${cpfsText}` : `Referencia do milheiro: ${formatCurrency(selected.valor_medio || 0)} • ${cpfsText}`;
    if (refs.cpfUsadosInfo) refs.cpfUsadosInfo.textContent = `CPFs usados: ${selected.cpfs_usados || 0}`;
    updateCpfStatus(selected.status || context.cpfControleInicial?.status || "disponivel");
    updateCpfLimite();
    renderProgramCards();
    recalcValores();
  }

  function toggleTitularFields() {
    const tipo = getTipoEmissao();
    if (refs.clienteWrapper) refs.clienteWrapper.style.display = "block";
    if (refs.contaAdmWrapper) refs.contaAdmWrapper.style.display = tipo === "administrada" ? "block" : "none";
    if (refs.emissorParceiroWrapper) refs.emissorParceiroWrapper.style.display = tipo === "parceiro" ? "block" : "none";
    if (refs.contaAdmRequired) refs.contaAdmRequired.style.display = tipo === "administrada" ? "inline" : "none";
    if (tipo !== "administrada" && refs.contaAdm) refs.contaAdm.value = "";
    if (tipo !== "parceiro" && refs.emissorParceiro) refs.emissorParceiro.value = "";
    if (refs.custoParceiro) refs.custoParceiro.readOnly = tipo !== "parceiro";
    const clienteTipo = getClienteTipo();
    const showModelo = tipo === "administrada" && clienteTipo !== "intermediario" && clienteTipo !== "concierge";
    if (refs.modeloOperacionalWrapper) refs.modeloOperacionalWrapper.style.display = showModelo ? "block" : "none";
    if (!showModelo && refs.modeloOperacional) refs.modeloOperacional.value = "";
    syncTipoOperacaoField();
    applyTipoOperacaoVisibility();
    renderTipoCards();
    updateProgramaOptions();
  }

  function applyTipoOperacaoVisibility() {
    const tipoOp = deriveTipoOperacao();
    const hideReferencia = tipoOp === "intermediario";
    if (refs.valorReferenciaWrapper) refs.valorReferenciaWrapper.style.display = hideReferencia ? "none" : "";
    if (refs.economiaWrapper) refs.economiaWrapper.style.display = hideReferencia ? "none" : "";
    if (hideReferencia && refs.valorReferencia) refs.valorReferencia.value = "";
    if (hideReferencia && refs.economia) refs.economia.value = "";
  }

  function updateResumo() {
    const origem = getSelectedText(refs.origemField);
    const destino = getSelectedText(refs.destinoField);
    const dataIda = refs.dataIda?.value || "";
    const dataVolta = refs.dataVolta?.value || "";
    const idaTemEscala = Number(refs.qtdEscalasIda?.value || 0) > 0;
    const voltaTemEscala = Number(refs.qtdEscalasVolta?.value || 0) > 0;
    const total = passengerKinds.reduce((sum, item) => sum + Number(item.field?.value || 0), 0);
    const duracaoIdaMinutos = parseDurationMinutes(refs.duracaoIda?.value);
    const duracaoVoltaMinutos = parseDurationMinutes(refs.duracaoVolta?.value);
    const fusoIdaHoras = toNumberSafe(refs.fusoIda?.value);
    const fusoVoltaHoras = toNumberSafe(refs.fusoVolta?.value);
    const chegadaIda = calculateArrival(dataIda, duracaoIdaMinutos, fusoIdaHoras);
    const chegadaVolta = hasVolta() ? calculateArrival(dataVolta, duracaoVoltaMinutos, fusoVoltaHoras) : null;
    if (refs.routeOrigin) refs.routeOrigin.textContent = origem;
    if (refs.routeDestination) refs.routeDestination.textContent = destino;
    if (refs.routeArrivalIda) refs.routeArrivalIda.textContent = chegadaIda ? formatDateTime(chegadaIda) : "--";
    if (refs.routeArrivalVolta) refs.routeArrivalVolta.textContent = chegadaVolta ? formatDateTime(chegadaVolta) : "--";
    if (refs.resumoTrechos) refs.resumoTrechos.textContent = origem !== "-" && destino !== "-" ? `${origem} -> ${destino}${idaTemEscala ? " | Ida com escala" : ""}${voltaTemEscala ? " | Volta com escala" : ""}` : "Preencha partida e destino.";
    if (refs.resumoDatas) refs.resumoDatas.textContent = `${dataIda ? `Ida: ${dataIda}` : "Ida pendente"} | ${hasVolta() ? (dataVolta ? `Volta: ${dataVolta}` : "Volta pendente") : "Somente ida"}`;
    if (refs.resumoPassageiros) refs.resumoPassageiros.textContent = `${total} passageiro(s)`;
    if (refs.resumoValores) refs.resumoValores.textContent = `${refs.valorReferencia?.value ? `Referencia ${formatCurrency(refs.valorReferencia.value)}` : "Valor de referencia nao informado"} | ${refs.valorTaxas?.value ? `Taxas ${formatCurrency(refs.valorTaxas.value)}` : "Taxas nao informadas"} | ${refs.pontos?.value ? `${refs.pontos.value} milhas` : "Milhas nao informadas"}`;
  }

  function recalcValores() {
    const selected = getCurrentProgram();
    const tipo = getTipoEmissao();
    const tipoOp = syncTipoOperacaoField();
    applyTipoOperacaoVisibility();
    const pontos = parseFloat(refs.pontos?.value || 0);
    const valorTaxas = parseFloat(refs.valorTaxas?.value || 0);
    const valorReferencia = parseFloat(refs.valorReferencia?.value || 0);
    const valorMilheiro = tipo === "parceiro" ? parseFloat(refs.custoParceiro?.value || 0) : Number(selected?.valor_medio || 0);
    if (refs.custoParceiro && tipo !== "parceiro") refs.custoParceiro.value = valorMilheiro ? String(Number(valorMilheiro).toFixed(2)) : "";
    const custoMilhas = (pontos / 1000) * valorMilheiro;
    if (refs.valorRefPontos) refs.valorRefPontos.value = custoMilhas ? String(custoMilhas.toFixed(2)) : "";
    const valorVenda = parseFloat(refs.vendaFinal?.value || 0);
    const valorTotalAuto = (valorVenda || 0) + (valorTaxas || 0);
    if (refs.valorTotalFinal) {
      refs.valorTotalFinal.value = valorTotalAuto ? String(valorTotalAuto.toFixed(2)) : "";
      refs.valorTotalFinal.setAttribute("readonly", "readonly");
    }
    const valorTotal = valorTotalAuto;
    const custoEmissor = parseFloat(refs.custoEmissor?.value || 0);
    const valorCobrado = parseFloat(refs.valorCobrado?.value || 0);
    const receita = valorTotal || valorVenda || 0;

    let lucroValor = 0;
    let economiaValor = null;

    if (tipoOp === "emissor_parceiro") {
      const base = valorCobrado || receita;
      lucroValor = base ? base - custoEmissor : 0;
      economiaValor = valorReferencia && base ? valorReferencia - base : null;
    } else if (tipoOp === "concierge") {
      lucroValor = 0;
      const equivalente = valorCobrado || custoMilhas;
      economiaValor = valorReferencia && equivalente ? valorReferencia - equivalente : null;
    } else if (tipoOp === "intermediario") {
      lucroValor = receita ? receita - (custoMilhas + valorTaxas) : 0;
      economiaValor = null;
    } else {
      lucroValor = receita ? receita - (custoMilhas + valorTaxas) : 0;
      economiaValor = valorReferencia && receita ? valorReferencia - receita : null;
    }

    if (refs.lucro) refs.lucro.value = lucroValor ? String(lucroValor.toFixed(2)) : "";
    if (refs.economia) {
      refs.economia.value = economiaValor !== null && !Number.isNaN(economiaValor) ? String(economiaValor.toFixed(2)) : "";
    }
    if (refs.lucroHighlight) refs.lucroHighlight.textContent = formatCurrency(refs.lucro?.value || 0);
    if (refs.totalHighlight) refs.totalHighlight.textContent = formatCurrency(valorTotal || valorVenda || 0);
    if (refs.economiaHighlight) refs.economiaHighlight.textContent = formatCurrency(refs.economia?.value || 0);
    updateValueRules(tipo, tipoOp);
    updateResumo();
  }

  function updateValueRules(tipo, tipoOp) {
    const regras = {
      venda_direta: {
        taxas: "Taxas da companhia e aeroporto. Somam no valor total final.",
        venda: "Valor das milhas vendidas ao cliente (sem taxas).",
      },
      intermediario: {
        taxas: "Taxas repassadas no valor final cobrado. Referência não se aplica.",
        venda: "Valor total negociado com a agência revendedora.",
      },
      concierge: {
        taxas: "Concierge: apenas taxas aéreas repassadas. Lucro zero (conta do cliente).",
        venda: "Concierge: normalmente não há venda de milhas (pontos do próprio cliente).",
      },
      emissor_parceiro: {
        taxas: "Emissor parceiro: taxas incluídas no valor final cobrado ao cliente.",
        venda: "Valor final cobrado ao cliente na emissão via parceiro.",
      },
    };
    const atual = regras[tipoOp] || regras.venda_direta;
    const rules = {
      valor_taxas: atual.taxas,
      valor_venda_final: atual.venda,
      valor_total_final: "Soma automática: valor venda milhas + taxas.",
    };
    Object.entries(rules).forEach(([name, text]) => {
      const helper = document.querySelector(`[data-rule-for="${name}"]`);
      if (helper) helper.textContent = text;
    });
  }

  function setVoltaVisibility() {
    const shouldShow = hasVolta();
    if (refs.vooVoltaCard) refs.vooVoltaCard.classList.toggle("is-visible", shouldShow);
    if (refs.possuiVolta) refs.possuiVolta.checked = shouldShow;
    if (!shouldShow) {
      if (refs.escalaVoltaToggle) refs.escalaVoltaToggle.checked = false;
      if (refs.escalaVoltaWrapper) refs.escalaVoltaWrapper.classList.remove("is-visible");
      if (refs.qtdEscalasVolta) refs.qtdEscalasVolta.value = "0";
      const totalEscalasVolta = qs("#id_total_escalas_volta");
      const voltaContainer = qs("#escalas-volta-container");
      if (totalEscalasVolta) totalEscalasVolta.value = "0";
      if (voltaContainer) voltaContainer.innerHTML = "";
    }
  }

  function syncReturnStep() {
    const shouldShow = hasVolta();
    if (refs.returnStepButton) refs.returnStepButton.hidden = !shouldShow;
    setVoltaVisibility();
    if (!shouldShow && currentStep === 3) currentStep = 4;
  }

  function collectCurrentPassengerValues() {
    const grouped = {};
    const inputs = form.querySelectorAll('[name^="passageiro-"]');
    inputs.forEach((input) => {
      const match = input.name.match(/^passageiro-(\d+)-(.+)$/);
      if (!match) return;
      const [, idx, rawField] = match;
      const field = rawField.replace(/-/g, "_");
      grouped[idx] = grouped[idx] || {};
      grouped[idx][field] = input.type === "checkbox" ? input.checked : input.value;
    });
    return Object.keys(grouped).sort((a, b) => Number(a) - Number(b)).map((key) => grouped[key]);
  }

  // Agrupa passageiros por categoria para que incrementar uma categoria
  // nao reposicione dados de outra categoria em slots errados.
  function groupSeedByCategoria(seed) {
    const byCategoria = {};
    (seed || []).forEach((item) => {
      const cat = item?.categoria || "adulto";
      byCategoria[cat] = byCategoria[cat] || [];
      byCategoria[cat].push(item);
    });
    return byCategoria;
  }

  function passengerSeed() {
    const fromDom = collectCurrentPassengerValues();
    if (fromDom.some((item) => Object.values(item).some((value) => value !== "" && value !== null && value !== undefined))) {
      return fromDom;
    }
    const grouped = {};
    Object.entries(loadedDraft || {}).forEach(([name, value]) => {
      const match = name.match(/^passageiro-(\d+)-(.+)$/);
      if (!match) return;
      const field = match[2].replace(/-/g, "_");
      grouped[match[1]] = grouped[match[1]] || {};
      grouped[match[1]][field] = value;
    });
    const fromDraft = Object.keys(grouped).sort((a, b) => Number(a) - Number(b)).map((key) => grouped[key]);
    return fromDraft.length ? fromDraft : context.passageirosData || [];
  }

  function updatePassengerCountLabels() {
    passengerKinds.forEach(({ field, label }) => {
      if (label) label.textContent = String(Number(field?.value || 0));
    });
  }

  function getCurrentClientContext() {
    const clienteId = Number(refs.cliente?.value || 0);
    return clienteId ? clientContextCache[clienteId] || null : null;
  }

  function renderPassengers() {
    if (!refs.passageirosContainer || !refs.totalPassageiros) return;
    updatePassengerCountLabels();
    const seed = passengerSeed();
    const seedByCat = groupSeedByCategoria(seed);
    const clientContext = getCurrentClientContext();
    const frequentes = clientContext?.passageiros_frequentes || [];
    refs.passageirosContainer.innerHTML = "";
    let index = 0;
    passengerKinds.forEach((kind) => {
      const quantity = Number(kind.field?.value || 0);
      const pool = seedByCat[kind.key] || [];
      for (let position = 0; position < quantity; position += 1) {
        const previous = pool[position] || {};
        const titular = frequentes.find((item) => item.is_titular);
        const naoTitulares = frequentes.filter((item) => !item.is_titular);
        const titularOpt = titular
          ? `<option value="__titular__">&#11088; ${titular.nome}${titular.cpf ? ` • ${titular.cpf}` : ""} (titular)</option>`
          : '<option value="__cliente__">Usar dados do cliente</option>';
        const options = [
          '<option value="">Preencher manualmente</option>',
          titularOpt,
          ...naoTitulares.map((item) => `<option value="${item.id}">${item.nome} • ${item.cpf}</option>`),
        ].join("");
        const card = document.createElement("div");
        card.className = "passenger-card passageiro-fields";
        card.innerHTML = `<div class="passenger-card__head"><span class="passenger-card__badge passenger-card__badge--${kind.key}">${kind.title} ${position + 1}</span><button type="button" class="passenger-card__remove" data-remove-kind="${kind.key}">Remover</button></div><div class="passenger-card__fields"><div><label class="wizard-label">${kind.title} ${position + 1} - Passageiro frequente</label><select name="passageiro-${index}-frequente" data-passageiro-frequente="${index}">${options}</select></div><div><label class="wizard-label">Nome completo <span class="required-asterisk">*</span></label><input type="text" name="passageiro-${index}-nome" value="${previous.nome || ""}" required></div><div><label class="wizard-label">CPF <span class="required-asterisk">*</span></label><input type="text" name="passageiro-${index}-cpf" value="${previous.cpf || ""}" required></div><div><label class="wizard-label">RG <span class="label-optional">(opcional)</span></label><input type="text" name="passageiro-${index}-rg" value="${previous.rg || ""}"></div><div><label class="wizard-label">Passaporte <span class="label-optional">(opcional)</span></label><input type="text" name="passageiro-${index}-passaporte" value="${previous.passaporte || ""}"></div><div><label class="wizard-label">Validade do passaporte <span class="label-optional">(opcional)</span></label><input type="date" name="passageiro-${index}-passaporte-validade" value="${previous.passaporte_validade || ""}"></div><div><label class="wizard-label">Data de nascimento <span class="required-asterisk">*</span></label><input type="date" name="passageiro-${index}-data-nascimento" value="${previous.data_nascimento || ""}" required></div><div><label class="wizard-label">Email <span class="label-optional">(opcional)</span></label><input type="email" name="passageiro-${index}-email" value="${previous.email || ""}" placeholder="passageiro@exemplo.com"></div><div><label class="wizard-label">Telefone <span class="label-optional">(opcional)</span></label><input type="tel" name="passageiro-${index}-telefone" value="${previous.telefone || ""}" placeholder="(11) 99999-9999"></div><div><label class="wizard-label">Observacoes <span class="label-optional">(opcional)</span></label><textarea name="passageiro-${index}-observacoes" rows="3">${previous.observacoes || ""}</textarea></div></div><input type="hidden" name="passageiro-${index}-categoria" value="${previous.categoria || kind.key}">`;
        refs.passageirosContainer.appendChild(card);
        index += 1;
      }
    });
    refs.totalPassageiros.value = String(index);
    if (!index) refs.passageirosContainer.innerHTML = emptyState("Nenhum passageiro adicionado", "Use os atalhos acima para incluir adultos, criancas ou bebes.");
    qsa("[data-remove-kind]").forEach((button) => button.addEventListener("click", () => {
      const kind = passengerKinds.find((item) => item.key === button.dataset.removeKind);
      if (!kind?.field) return;
      kind.field.value = String(Math.max(0, Number(kind.field.value || 0) - 1));
      renderPassengers();
      saveDraft();
    }));
    qsa("[data-passageiro-frequente]").forEach((select) => select.addEventListener("change", (event) => {
      const indexValue = event.currentTarget.dataset.passageiroFrequente;
      const selectedValue = event.currentTarget.value;
      const clientContext = getCurrentClientContext();
      if (selectedValue === "__titular__" || selectedValue === "__cliente__") {
        const titularData = clientContext?.passageiros_frequentes?.find((item) => item.is_titular);
        fillPassengerFields(indexValue, {
          nome: titularData?.nome || clientContext?.cliente?.nome || "",
          cpf: titularData?.cpf || clientContext?.cliente?.cpf || "",
          rg: titularData?.rg || "",
          passaporte: titularData?.passaporte || "",
          passaporte_validade: titularData?.passaporte_validade || "",
          data_nascimento: titularData?.data_nascimento || "",
          email: titularData?.email || clientContext?.cliente?.email || "",
          telefone: titularData?.telefone || clientContext?.cliente?.telefone || "",
        });
      } else if (selectedValue) {
        const lista = context.passageirosFrequentes?.[parseInt(refs.cliente?.value || 0, 10)] || [];
        const selected = lista.find((item) => String(item.id) === selectedValue);
        if (selected) {
          fillPassengerFields(indexValue, {
            nome: selected.nome || "",
            cpf: selected.cpf || "",
            rg: selected.rg || "",
            passaporte: selected.passaporte || "",
            passaporte_validade: selected.passaporte_validade || "",
            data_nascimento: selected.data_nascimento || "",
            email: selected.email || "",
            telefone: selected.telefone || "",
          });
        }
      }
      updateCpfLimite();
      saveDraft();
    }));
    updateCpfLimite();
    updateResumo();
  }

  function fillPassengerFields(indexValue, values) {
    const nome = form.querySelector(`[name="passageiro-${indexValue}-nome"]`);
    const cpf = form.querySelector(`[name="passageiro-${indexValue}-cpf"]`);
    const rg = form.querySelector(`[name="passageiro-${indexValue}-rg"]`);
    const passaporte = form.querySelector(`[name="passageiro-${indexValue}-passaporte"]`);
    const passaporteValidade = form.querySelector(`[name="passageiro-${indexValue}-passaporte-validade"]`);
    const dataNascimento = form.querySelector(`[name="passageiro-${indexValue}-data-nascimento"]`);
    const email = form.querySelector(`[name="passageiro-${indexValue}-email"]`);
    const telefone = form.querySelector(`[name="passageiro-${indexValue}-telefone"]`);
    if (nome) nome.value = values?.nome || "";
    if (cpf) cpf.value = values?.cpf || "";
    if (rg) rg.value = values?.rg || "";
    if (passaporte) passaporte.value = values?.passaporte || "";
    if (passaporteValidade) passaporteValidade.value = values?.passaporte_validade || "";
    if (dataNascimento) dataNascimento.value = values?.data_nascimento || "";
    if (email) email.value = values?.email || "";
    if (telefone) telefone.value = values?.telefone || "";
  }

  renderPassengers = function renderPassengersSecure() {
    if (!refs.passageirosContainer || !refs.totalPassageiros) return;
    updatePassengerCountLabels();
    const seed = passengerSeed();
    const seedByCat = groupSeedByCategoria(seed);
    const clientContext = getCurrentClientContext();
    const frequentes = clientContext?.passageiros_frequentes || [];
    refs.passageirosContainer.innerHTML = "";
    let index = 0;
    passengerKinds.forEach((kind) => {
      const quantity = Number(kind.field?.value || 0);
      const pool = seedByCat[kind.key] || [];
      for (let position = 0; position < quantity; position += 1) {
        const previous = pool[position] || {};
        const titular = frequentes.find((item) => item.is_titular);
        const naoTitulares = frequentes.filter((item) => !item.is_titular);
        const titularOpt = titular
          ? `<option value="__titular__">&#11088; ${titular.nome}${titular.cpf_masked ? ` • ${titular.cpf_masked}` : ""} (titular)</option>`
          : '<option value="__cliente__">Usar dados do cliente</option>';
        const options = [
          '<option value="">Preencher manualmente</option>',
          titularOpt,
          ...naoTitulares.map((item) => `<option value="${item.id}">${item.nome}${item.cpf_masked ? ` • ${item.cpf_masked}` : ""}</option>`),
        ].join("");
        const card = document.createElement("div");
        card.className = "passenger-card passageiro-fields";
        card.innerHTML = `<div class="passenger-card__head"><span class="passenger-card__badge passenger-card__badge--${kind.key}">${kind.title} ${position + 1}</span><button type="button" class="passenger-card__remove" data-remove-kind="${kind.key}">Remover</button></div><div class="passenger-card__fields"><div><label class="wizard-label">${kind.title} ${position + 1} - Passageiro frequente</label><select name="passageiro-${index}-frequente" data-passageiro-frequente="${index}">${options}</select></div><div><label class="wizard-label">Nome completo <span class="required-asterisk">*</span></label><input type="text" name="passageiro-${index}-nome" value="${previous.nome || ""}" required></div><div><label class="wizard-label">CPF <span class="required-asterisk">*</span></label><input type="text" name="passageiro-${index}-cpf" value="${previous.cpf || ""}" required></div><div><label class="wizard-label">RG <span class="label-optional">(opcional)</span></label><input type="text" name="passageiro-${index}-rg" value="${previous.rg || ""}"></div><div><label class="wizard-label">Passaporte <span class="label-optional">(opcional)</span></label><input type="text" name="passageiro-${index}-passaporte" value="${previous.passaporte || ""}"></div><div><label class="wizard-label">Validade do passaporte <span class="label-optional">(opcional)</span></label><input type="date" name="passageiro-${index}-passaporte-validade" value="${previous.passaporte_validade || ""}"></div><div><label class="wizard-label">Data de nascimento <span class="required-asterisk">*</span></label><input type="date" name="passageiro-${index}-data-nascimento" value="${previous.data_nascimento || ""}" required></div><div><label class="wizard-label">Email <span class="label-optional">(opcional)</span></label><input type="email" name="passageiro-${index}-email" value="${previous.email || ""}" placeholder="passageiro@exemplo.com"></div><div><label class="wizard-label">Telefone <span class="label-optional">(opcional)</span></label><input type="tel" name="passageiro-${index}-telefone" value="${previous.telefone || ""}" placeholder="(11) 99999-9999"></div><div><label class="wizard-label">Observacoes <span class="label-optional">(opcional)</span></label><textarea name="passageiro-${index}-observacoes" rows="3">${previous.observacoes || ""}</textarea></div></div><input type="hidden" name="passageiro-${index}-categoria" value="${previous.categoria || kind.key}">`;
        refs.passageirosContainer.appendChild(card);
        index += 1;
      }
    });
    refs.totalPassageiros.value = String(index);
    if (!index) refs.passageirosContainer.innerHTML = emptyState("Nenhum passageiro adicionado", "Use os atalhos acima para incluir adultos, criancas ou bebes.");
    qsa("[data-remove-kind]").forEach((button) => button.addEventListener("click", () => {
      const kind = passengerKinds.find((item) => item.key === button.dataset.removeKind);
      if (!kind?.field) return;
      kind.field.value = String(Math.max(0, Number(kind.field.value || 0) - 1));
      renderPassengers();
      saveDraft();
    }));
    qsa("[data-passageiro-frequente]").forEach((select) => select.addEventListener("change", async (event) => {
      const indexValue = event.currentTarget.dataset.passageiroFrequente;
      const selectedValue = event.currentTarget.value;
      if (selectedValue === "__titular__" || selectedValue === "__cliente__") {
        const clienteContextPayload = await ensureClientContext(refs.cliente?.value);
        const titularData = clienteContextPayload?.passageiros_frequentes?.find((item) => item.is_titular);
        fillPassengerFields(indexValue, {
          nome: titularData?.nome || clienteContextPayload?.cliente?.nome || "",
          cpf: titularData?.cpf || clienteContextPayload?.cliente?.cpf || "",
          rg: titularData?.rg || "",
          passaporte: titularData?.passaporte || "",
          passaporte_validade: titularData?.passaporte_validade || "",
          data_nascimento: titularData?.data_nascimento || "",
          email: titularData?.email || clienteContextPayload?.cliente?.email || "",
          telefone: titularData?.telefone || clienteContextPayload?.cliente?.telefone || "",
        });
      } else if (selectedValue) {
        fillPassengerFields(indexValue, await ensurePassengerDetail(selectedValue));
      }
      updateCpfLimite();
      saveDraft();
    }));
    updateCpfLimite();
    updateResumo();
  }

  function scaleSeed(tipo, initialData) {
    const grouped = {};
    Object.entries(loadedDraft || {}).forEach(([name, value]) => {
      const match = name.match(new RegExp(`^escala-${tipo}-(\\d+)-(.+)$`));
      if (!match) return;
      grouped[match[1]] = grouped[match[1]] || {};
      grouped[match[1]][match[2]] = value;
    });
    const fromDraft = Object.keys(grouped).sort((a, b) => Number(a) - Number(b)).map((key) => grouped[key]);
    return fromDraft.length ? fromDraft : initialData || [];
  }

  function initScaleSection(tipo, initialData) {
    const checkbox = qs(`#${tipo}-tem-escala`);
    const qtdInput = qs(`#id_qtd_escalas_${tipo}`);
    const totalInput = qs(`#id_total_escalas_${tipo}`);
    const wrapper = qs(`#escala-${tipo}-wrapper`);
    const container = qs(`#escalas-${tipo}-container`);
    const addButton = qs(`[data-add-escala="${tipo}"]`);
    if (!checkbox || !qtdInput || !totalInput || !wrapper || !container) return;
    const collect = () => qsa(`#escalas-${tipo}-container .escala-fields`).map((row, index) => ({
      aeroporto: row.querySelector(`[name="escala-${tipo}-${index}-aeroporto"]`)?.value || "",
      cidade: row.querySelector(`[name="escala-${tipo}-${index}-cidade"]`)?.value || "",
      duracao: row.querySelector(`[name="escala-${tipo}-${index}-duracao"]`)?.value || "",
    }));
    const buildScaleRow = (row, index) => {
      const options = ['<option value=""></option>', ...(context.aeroportos || []).map((airport) => `<option value="${airport.id}">${airport.sigla} - ${airport.nome}</option>`)].join("");
      const item = document.createElement("div");
      item.className = "scale-row escala-fields";
      item.innerHTML = `<div class="scale-grid"><div><label class="wizard-label">IATA da escala</label><select name="escala-${tipo}-${index}-aeroporto">${options}</select></div><div><label class="wizard-label">Cidade / observacao</label><input type="text" name="escala-${tipo}-${index}-cidade" value="${row.cidade || ""}"></div><div><label class="wizard-label">Duracao da escala</label><input type="time" name="escala-${tipo}-${index}-duracao" value="${row.duracao || ""}"></div><div class="scale-actions"><button type="button" class="scale-remove" data-remove-escala="${tipo}" data-remove-index="${index}">Remover</button></div></div>`;
      const select = item.querySelector(`[name="escala-${tipo}-${index}-aeroporto"]`);
      if (select) select.value = row.aeroporto_id || row.aeroporto || "";
      return item;
    };
    const renderRows = (rows) => {
      const visible = tipo === "volta" ? hasVolta() && checkbox.checked : checkbox.checked;
      wrapper.classList.toggle("is-visible", visible);
      if (!visible) {
        if (!checkbox.checked) {
          container.innerHTML = "";
        }
        qtdInput.value = "0";
        totalInput.value = "0";
        updateResumo();
        return;
      }
      const seededRows = scaleSeed(tipo, initialData);
      const finalRows = rows?.length ? rows : (seededRows.length ? seededRows : [{}]);
      container.innerHTML = "";
      finalRows.forEach((row, index) => {
        container.appendChild(buildScaleRow(row, index));
      });
      qtdInput.value = String(finalRows.length);
      totalInput.value = String(finalRows.length);
      qsa(`[data-remove-escala="${tipo}"]`).forEach((button) => button.addEventListener("click", () => {
        const remaining = collect();
        remaining.splice(Number(button.dataset.removeIndex), 1);
        if (!remaining.length) checkbox.checked = false;
        renderRows(remaining);
        saveDraft();
      }));
      container.querySelectorAll("select, input").forEach((field) => {
        field.addEventListener("input", () => {
          updateResumo();
          saveDraft();
        });
        field.addEventListener("change", () => {
          updateResumo();
          saveDraft();
        });
      });
      updateResumo();
    };
    checkbox.addEventListener("change", () => { renderRows(); saveDraft(); });
    addButton?.addEventListener("click", () => {
      checkbox.checked = true;
      const rows = collect();
      rows.push({});
      renderRows(rows);
      saveDraft();
    });
    const initialRows = scaleSeed(tipo, initialData);
    if (initialRows.length) checkbox.checked = true;
    renderRows(initialRows);
  }

  function updateReview() {
    if (!refs.reviewGrid) return;
    const total = passengerKinds.reduce((sum, item) => sum + Number(item.field?.value || 0), 0);
    refs.reviewGrid.innerHTML = [
      { title: "Cliente & Programa", step: 1, stats: [{ label: "Tipo de Emissao", value: tipoMeta[getTipoEmissao()]?.title || "-" }, { label: "Cliente", value: getSelectedText(refs.cliente) }, { label: "Programa", value: getSelectedText(refs.programa) }] },
      { title: "Voos", step: 2, stats: [{ label: "Origem", value: getSelectedText(qs("#id_aeroporto_partida")) }, { label: "Destino", value: getSelectedText(qs("#id_aeroporto_destino")) }, { label: "Ida", value: qs("#id_data_ida")?.value || "-" }, { label: "Volta", value: refs.dataVolta?.value || "Sem volta" }, { label: "Bagagem de mao", value: getSelectedText(refs.bagagemMao) || "Sob consulta" }, { label: "Bagagem despachada", value: getSelectedText(refs.bagagemDespachada) || "Sob consulta" }] },
      { title: "Passageiros", step: 4, stats: [{ label: "Adultos", value: String(Number(refs.countAdultos?.value || 0)) }, { label: "Criancas", value: String(Number(refs.countCriancas?.value || 0)) }, { label: "Bebes", value: String(Number(refs.countBebes?.value || 0)) }, { label: "Total", value: `${total} viajante(s)` }] },
      { title: "Valores", step: 5, stats: [{ label: "Milhas", value: refs.pontos?.value || "0" }, { label: "Taxas", value: formatCurrency(refs.valorTaxas?.value || 0) }, { label: "Total", value: formatCurrency(refs.valorTotalFinal?.value || refs.vendaFinal?.value || 0) }, { label: "Lucro", value: formatCurrency(refs.lucro?.value || 0) }] },
    ].map((panel) => `<div class="review-panel"><div class="review-panel__head"><div class="review-panel__title">${panel.title}</div><button type="button" class="review-edit" data-edit-step="${panel.step}">Editar</button></div><div class="review-grid__stats">${panel.stats.map((stat) => `<div class="review-stat"><span>${stat.label}</span><strong>${stat.value}</strong></div>`).join("")}</div></div>`).join("");
    qsa("[data-edit-step]").forEach((button) => button.addEventListener("click", () => setStep(Number(button.dataset.editStep))));
  }

  function validateStep(step) {
    if (step === 1) {
      if (!refs.tipoEmissao?.value) return showToast("Selecione o tipo de emissao"), false;
      if (!refs.cliente?.value) return showToast("Selecione o cliente"), false;
      if (getTipoEmissao() === "administrada" && !refs.contaAdm?.value) return showToast("Selecione a conta administrada"), false;
      if (getTipoEmissao() === "parceiro" && !refs.emissorParceiro?.value) return showToast("Selecione o emissor parceiro"), false;
      if (!refs.programa?.value) return showToast("Selecione o programa"), false;
    }
    if (step === 2) {
      if (!refs.origemField?.value) return showToast("Informe o aeroporto de partida"), false;
      if (!refs.destinoField?.value) return showToast("Informe o aeroporto de destino"), false;
      if (!refs.companhiaField?.value) return showToast("Selecione a companhia aerea"), false;
      if (!refs.dataIda?.value) return showToast("Informe a data da ida"), false;
    }
    if (step === 3 && hasVolta()) {
      if (!refs.dataVolta?.value) return showToast("Informe a data da volta"), false;
    }
    if (step === 4) {
      const total = passengerKinds.reduce((sum, item) => sum + Number(item.field?.value || 0), 0);
      if (!total) return showToast("Adicione pelo menos um passageiro"), false;
      for (const field of qsa('input[name$="-nome"], input[name$="-cpf"], input[name$="-data-nascimento"]')) {
        if (!field.value.trim()) return showToast("Preencha os dados obrigatorios dos passageiros"), false;
      }
    }
    if (step === 5) {
      if (!qs("#id_localizador")?.value.trim()) return showToast("Informe o localizador"), false;
      if (!refs.valorReferencia?.value) return showToast("Informe o valor de referencia"), false;
    }
    return true;
  }

  function setStep(step) {
    const enabledSteps = getEnabledSteps();
    currentStep = enabledSteps.includes(step) ? step : enabledSteps.find((item) => item >= step) || enabledSteps[enabledSteps.length - 1];
    refs.stepBlocks.forEach((block) => block.classList.toggle("is-active", Number(block.dataset.step) === currentStep));
    refs.stepButtons.forEach((button) => {
      const value = Number(button.dataset.goStep);
      button.classList.toggle("is-active", value === currentStep);
      button.classList.toggle("is-complete", enabledSteps.includes(value) && value < currentStep);
    });
    if (refs.prevButton) refs.prevButton.style.display = currentStep !== enabledSteps[0] ? "inline-flex" : "none";
    if (refs.nextButton) refs.nextButton.style.display = currentStep !== enabledSteps[enabledSteps.length - 1] ? "inline-flex" : "none";
    if (refs.finishButton) refs.finishButton.style.display = currentStep === enabledSteps[enabledSteps.length - 1] ? "inline-flex" : "none";
    updateReview();
    updateResumo();
    saveDraft();
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function attachEventListeners() {
    refs.stepButtons.forEach((button) => button.addEventListener("click", () => {
      const targetStep = Number(button.dataset.goStep);
      if (targetStep <= currentStep) setStep(targetStep);
    }));
    refs.prevButton?.addEventListener("click", () => setStep(getPrevStep(currentStep)));
    refs.nextButton?.addEventListener("click", () => { if (validateStep(currentStep)) setStep(getNextStep(currentStep)); });
    refs.tipoEmissao?.addEventListener("change", () => { toggleTitularFields(); recalcValores(); updateResumo(); saveDraft(); });
    refs.cliente?.addEventListener("change", async () => { await ensureClientContext(refs.cliente?.value); toggleTitularFields(); updateProgramaOptions(); renderPassengers(); recalcValores(); updateResumo(); saveDraft(); });
    refs.modeloOperacional?.addEventListener("change", () => { recalcValores(); updateResumo(); saveDraft(); });
    refs.contaAdm?.addEventListener("change", () => { updateProgramaOptions(); updateResumo(); saveDraft(); });
    refs.emissorParceiro?.addEventListener("change", () => { updateResumo(); saveDraft(); });
    refs.programa?.addEventListener("change", () => { updateProgramaInfo(); updateResumo(); saveDraft(); });
    [refs.pontos, refs.valorTaxas, refs.valorReferencia, refs.custoParceiro, refs.vendaFinal, refs.valorTotalFinal, refs.custoEmissor, refs.valorCobrado].filter(Boolean).forEach((field) => field.addEventListener("input", () => { recalcValores(); saveDraft(); }));
    refs.passengerButtons.forEach((button) => button.addEventListener("click", () => {
      const kind = passengerKinds.find((item) => item.key === button.dataset.passengerKind);
      if (!kind?.field) return;
      kind.field.value = String(Number(kind.field.value || 0) + 1);
      renderPassengers();
      saveDraft();
    }));
    [refs.origemField, refs.destinoField, refs.companhiaField, refs.dataIda, refs.escalaIdaToggle, refs.escalaVoltaToggle, refs.bagagemMao, refs.bagagemDespachada].filter(Boolean).forEach((field) => field.addEventListener("change", updateResumo));
    refs.possuiVolta?.addEventListener("change", () => {
      if (!refs.possuiVolta.checked && refs.dataVolta) refs.dataVolta.value = "";
      const voltaContainer = qs("#escalas-volta-container");
      const totalEscalasVolta = qs("#id_total_escalas_volta");
      if (!refs.possuiVolta.checked) {
        if (voltaContainer) voltaContainer.innerHTML = "";
        if (refs.qtdEscalasVolta) refs.qtdEscalasVolta.value = "0";
        if (totalEscalasVolta) totalEscalasVolta.value = "0";
      }
      syncReturnStep();
      updateResumo();
      saveDraft();
      setStep(currentStep);
    });
    refs.dataVolta?.addEventListener("change", () => { syncReturnStep(); updateResumo(); saveDraft(); });
    form.addEventListener("input", (event) => {
      if (event.target.name?.includes("passageiro-") || event.target.name?.includes("escala-")) {
        updateCpfLimite();
        updateResumo();
      }
      saveDraft();
    });
    form.addEventListener("change", () => {
      updateResumo();
      saveDraft();
    });
    form.addEventListener("submit", () => {
      if (refs.finishButton) refs.finishButton.disabled = true;
    });
  }

  function restoreDraft() {
    if (!loadedDraft) return;
    applyFieldValues(loadedDraft);
    if (Number.isFinite(Number(loadedDraft.__step))) currentStep = Number(loadedDraft.__step);
  }

  restoreDraft();
  toggleTitularFields();
  initScaleSection("ida", context.escalasIdaData || []);
  initScaleSection("volta", context.escalasVoltaData || []);
  await ensureClientContext(refs.cliente?.value);
  renderPassengers();
  applyFieldValues(loadedDraft);
  await ensureClientContext(refs.cliente?.value);
  renderPassengers();
  updateProgramaOptions();
  recalcValores();
  updatePassengerCountLabels();
  syncReturnStep();
  attachEventListeners();
  setStep(currentStep);
})();
