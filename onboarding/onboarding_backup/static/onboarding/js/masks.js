/**
 * Mascaras de input para onboarding: CPF, telefone, CNPJ, CEP, data.
 * Usa data-mask="cpf|telefone|cnpj|cep|date" nos inputs.
 */
(function () {
  function maskDate(v) {
    var d = v.replace(/\D/g, "").slice(0, 8);
    if (d.length <= 2) return d;
    if (d.length <= 4) return d.slice(0, 2) + "/" + d.slice(2);
    return d.slice(0, 2) + "/" + d.slice(2, 4) + "/" + d.slice(4);
  }

  function maskCEP(v) {
    var d = v.replace(/\D/g, "").slice(0, 8);
    if (d.length <= 5) return d;
    return d.slice(0, 5) + "-" + d.slice(5);
  }

  function maskCPF(v) {
    var d = v.replace(/\D/g, "").slice(0, 11);
    if (d.length <= 3) return d;
    if (d.length <= 6) return d.slice(0, 3) + "." + d.slice(3);
    if (d.length <= 9) return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6);
    return d.slice(0, 3) + "." + d.slice(3, 6) + "." + d.slice(6, 9) + "-" + d.slice(9);
  }

  function maskTelefone(v) {
    var d = v.replace(/\D/g, "").slice(0, 11);
    if (d.length <= 2) return d.length ? "(" + d : "";
    if (d.length <= 7) return "(" + d.slice(0, 2) + ") " + d.slice(2);
    if (d.length <= 10) return "(" + d.slice(0, 2) + ") " + d.slice(2, 6) + "-" + d.slice(6);
    return "(" + d.slice(0, 2) + ") " + d.slice(2, 7) + "-" + d.slice(7);
  }

  function maskCNPJ(v) {
    var d = v.replace(/\D/g, "").slice(0, 14);
    if (d.length <= 2) return d;
    if (d.length <= 5) return d.slice(0, 2) + "." + d.slice(2);
    if (d.length <= 8) return d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5);
    if (d.length <= 12) return d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5, 8) + "/" + d.slice(8);
    return d.slice(0, 2) + "." + d.slice(2, 5) + "." + d.slice(5, 8) + "/" + d.slice(8, 12) + "-" + d.slice(12);
  }

  var masks = {
    cpf: maskCPF,
    telefone: maskTelefone,
    cnpj: maskCNPJ,
    cep: maskCEP,
    date: maskDate,
  };

  document.addEventListener("input", function (e) {
    var el = e.target;
    var type = el && el.dataset && el.dataset.mask;
    if (type && masks[type]) {
      var pos = el.selectionStart;
      var oldLen = el.value.length;
      el.value = masks[type](el.value);
      var newLen = el.value.length;
      var newPos = pos + (newLen - oldLen);
      if (newPos < 0) newPos = 0;
      el.setSelectionRange(newPos, newPos);

      // Auto-fill CEP via ViaCEP
      if (type === "cep") {
        var digits = el.value.replace(/\D/g, "");
        clearTimeout(el._cepTimer);
        var hint = document.getElementById("cep-status");
        if (digits.length === 8) {
          el._cepTimer = setTimeout(function () {
            if (hint) { hint.textContent = "Buscando..."; hint.style.color = "var(--login-muted)"; }
            fetch("https://viacep.com.br/ws/" + digits + "/json/")
              .then(function (r) { return r.json(); })
              .then(function (data) {
                if (data.erro) {
                  if (hint) { hint.textContent = "CEP nao encontrado"; hint.style.color = "#dc2626"; }
                  return;
                }
                if (hint) hint.textContent = "";
                var fields = {
                  id_endereco: data.logradouro || "",
                  id_bairro: data.bairro || "",
                  id_cidade: data.localidade || "",
                  id_estado: data.uf || "",
                };
                for (var id in fields) {
                  var input = document.getElementById(id);
                  if (input) input.value = fields[id];
                }
                var numInput = document.getElementById("id_numero");
                if (numInput && !numInput.value) numInput.focus();
              })
              .catch(function () {
                if (hint) { hint.textContent = "Erro ao buscar CEP"; hint.style.color = "#dc2626"; }
              });
          }, 400);
        } else {
          if (hint) hint.textContent = "";
        }
      }
    }
  });
})();
