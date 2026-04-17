(() => {
  const referencia = document.getElementById("id_valor_referencia");
  const pago = document.getElementById("id_valor_pago");
  const economia = document.getElementById("id_economia_obtida");

  const parseValue = (value) => {
    if (!value) return 0;
    return Number(String(value).replace(",", ".")) || 0;
  };

  const updateEconomia = () => {
    if (!referencia || !pago || !economia) return;
    const total = parseValue(referencia.value) - parseValue(pago.value);
    economia.value = Number.isFinite(total) ? total.toFixed(2) : "";
  };

  if (referencia) referencia.addEventListener("input", updateEconomia);
  if (pago) pago.addEventListener("input", updateEconomia);
  updateEconomia();

  // ── Voo vinculado dinâmico ──
  const clienteSelect = document.getElementById("id_cliente");
  const vooSelect = document.getElementById("id_voo_vinculado");
  if (!clienteSelect || !vooSelect) return;

  const vooAtual = vooSelect.value;

  const carregarVoos = (clienteId) => {
    // Limpa options
    vooSelect.innerHTML = '<option value="">Carregando...</option>';
    vooSelect.disabled = true;

    if (!clienteId) {
      vooSelect.innerHTML = '<option value="">Selecione o cliente primeiro</option>';
      vooSelect.disabled = false;
      return;
    }

    fetch("/adm/api/voos-cliente/" + clienteId + "/")
      .then((r) => r.json())
      .then((voos) => {
        vooSelect.innerHTML = '<option value="">Nenhum (sem voo vinculado)</option>';
        voos.forEach((v) => {
          const opt = document.createElement("option");
          opt.value = v.id;
          opt.textContent = v.label;
          if (String(v.id) === String(vooAtual)) opt.selected = true;
          vooSelect.appendChild(opt);
        });
        vooSelect.disabled = false;
      })
      .catch(() => {
        vooSelect.innerHTML = '<option value="">Erro ao carregar voos</option>';
        vooSelect.disabled = false;
      });
  };

  clienteSelect.addEventListener("change", () => {
    carregarVoos(clienteSelect.value);
  });

  // Se já tem cliente selecionado (edição), carrega os voos
  if (clienteSelect.value) {
    carregarVoos(clienteSelect.value);
  }
})();
