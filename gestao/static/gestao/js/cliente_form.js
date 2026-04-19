(() => {
  const onlyDigits = (value) => String(value || "").replace(/\D/g, "");

  const maskCEP = (value) => {
    const digits = onlyDigits(value).slice(0, 8);
    if (digits.length <= 5) {
      return digits;
    }
    return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  };

  const setupFullName = () => {
    const fullName = document.getElementById("id_full_name");
    const firstName = document.getElementById("id_first_name");
    const lastName = document.getElementById("id_last_name");
    if (!fullName || !firstName || !lastName) {
      return;
    }

    const joinName = () => {
      const current = [firstName.value, lastName.value].filter(Boolean).join(" ").trim();
      fullName.value = fullName.value || current;
    };

    const splitName = () => {
      const raw = (fullName.value || "").trim().replace(/\s+/g, " ");
      if (!raw) {
        firstName.value = "";
        lastName.value = "";
        return;
      }
      const parts = raw.split(" ");
      firstName.value = parts.shift() || "";
      lastName.value = parts.join(" ");
    };

    joinName();
    fullName.addEventListener("input", splitName);
    fullName.closest("form")?.addEventListener("submit", splitName);
  };

  const setupCepLookup = () => {
    const cepInput = document.getElementById("id_cep");
    if (!cepInput) {
      return;
    }

    const status = document.getElementById("cep-status");
    const setStatus = (message, tone) => {
      if (!status) {
        return;
      }
      status.textContent = message || "";
      status.style.color = tone === "error" ? "#dc2626" : "";
    };

    const fillIfEmptyOrKnown = (id, value) => {
      const input = document.getElementById(id);
      if (input && value) {
        input.value = value;
      }
    };

    const searchCep = () => {
      const digits = onlyDigits(cepInput.value);
      if (digits.length !== 8) {
        setStatus("");
        return;
      }

      setStatus("Buscando endereco...");
      fetch(`https://viacep.com.br/ws/${digits}/json/`)
        .then((response) => response.json())
        .then((data) => {
          if (data.erro) {
            setStatus("CEP nao encontrado.", "error");
            return;
          }

          setStatus("");
          fillIfEmptyOrKnown("id_endereco", data.logradouro || "");
          fillIfEmptyOrKnown("id_bairro", data.bairro || "");
          fillIfEmptyOrKnown("id_cidade", data.localidade || "");
          fillIfEmptyOrKnown("id_estado", data.uf || "");

          const numero = document.getElementById("id_numero");
          if (numero && !numero.value) {
            numero.focus();
          }
        })
        .catch(() => {
          setStatus("Erro ao buscar CEP.", "error");
        });
    };

    cepInput.value = maskCEP(cepInput.value);
    cepInput.addEventListener("input", () => {
      cepInput.value = maskCEP(cepInput.value);
      clearTimeout(cepInput._cepTimer);
      cepInput._cepTimer = setTimeout(searchCep, 450);
    });
    cepInput.addEventListener("blur", searchCep);
  };

  const setupTipoClienteToggle = () => {
    const tipoField = document.querySelector("#id_tipo_cliente, [name='tipo_cliente']");
    if (!tipoField) return;
    const conditionalBlocks = document.querySelectorAll("[data-show-for]");
    if (!conditionalBlocks.length) return;
    const applyVisibility = () => {
      const current = (tipoField.value || "").trim();
      conditionalBlocks.forEach((node) => {
        const target = node.getAttribute("data-show-for");
        const matches = target
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean);
        node.style.display = matches.includes(current) ? "" : "none";
      });
    };
    tipoField.addEventListener("change", applyVisibility);
    applyVisibility();
  };

  setupFullName();
  setupCepLookup();
  setupTipoClienteToggle();
})();
