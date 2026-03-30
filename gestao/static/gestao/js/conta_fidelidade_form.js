(() => {
  const checkbox = document.getElementById("id_clube_ativo");
  const clubBody = document.querySelector("[data-club-body]");
  const validade = document.getElementById("id_validade");
  const validadeProxy = document.getElementById("id_validade_proxy");
  if (!checkbox || !clubBody) {
    return;
  }

  const syncClubState = () => {
    clubBody.classList.toggle("is-disabled", !checkbox.checked);
  };

  const syncProxyFromReal = () => {
    if (validade && validadeProxy) {
      validadeProxy.value = validade.value || "";
    }
  };

  const syncRealFromProxy = () => {
    if (validade && validadeProxy) {
      validade.value = validadeProxy.value || "";
    }
  };

  checkbox.addEventListener("change", syncClubState);
  if (validade && validadeProxy) {
    validade.addEventListener("input", syncProxyFromReal);
    validadeProxy.addEventListener("input", syncRealFromProxy);
    syncProxyFromReal();
  }
  syncClubState();
})();
