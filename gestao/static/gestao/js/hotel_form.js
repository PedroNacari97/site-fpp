(() => {
  const referencia = document.getElementById("id_valor_referencia");
  const pago = document.getElementById("id_valor_pago");
  const economia = document.getElementById("id_economia_obtida");
  if (!referencia || !pago || !economia) {
    return;
  }

  const parseValue = (value) => {
    if (!value) {
      return 0;
    }
    return Number(String(value).replace(",", ".")) || 0;
  };

  const updateEconomia = () => {
    const total = parseValue(referencia.value) - parseValue(pago.value);
    economia.value = Number.isFinite(total) ? total.toFixed(2) : "";
  };

  referencia.addEventListener("input", updateEconomia);
  pago.addEventListener("input", updateEconomia);
  updateEconomia();
})();
