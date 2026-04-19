(() => {
  const onlyDigits = (value) => String(value || "").replace(/\D/g, "");

  const masks = {
    cpf(value) {
      const digits = onlyDigits(value).slice(0, 11);
      if (digits.length <= 3) return digits;
      if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
      if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
      return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
    },

    telefone(value) {
      const digits = onlyDigits(value).slice(0, 11);
      if (digits.length <= 2) return digits.length ? `(${digits}` : "";
      if (digits.length <= 6) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
      if (digits.length <= 10) {
        return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
      }
      return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
    },

    cep(value) {
      const digits = onlyDigits(value).slice(0, 8);
      if (digits.length <= 5) return digits;
      return `${digits.slice(0, 5)}-${digits.slice(5)}`;
    },

    date(value) {
      const raw = String(value || "").trim();
      const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
      if (isoMatch) {
        return `${isoMatch[3]}/${isoMatch[2]}/${isoMatch[1]}`;
      }

      const digits = onlyDigits(value).slice(0, 8);
      if (digits.length <= 2) return digits;
      if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
      return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
    },
  };

  const aliases = {
    phone: "telefone",
    tel: "telefone",
    celular: "telefone",
    whatsapp: "telefone",
    data: "date",
  };

  const ignoredTypes = new Set([
    "button",
    "checkbox",
    "color",
    "date",
    "datetime-local",
    "email",
    "file",
    "hidden",
    "month",
    "number",
    "password",
    "radio",
    "range",
    "reset",
    "submit",
    "time",
    "url",
    "week",
  ]);

  const normalize = (value) =>
    String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();

  const fieldTokens = (field) => {
    const value = [
      field.getAttribute("name"),
      field.getAttribute("id"),
      field.getAttribute("autocomplete"),
      field.getAttribute("aria-label"),
    ].join(" ");
    return normalize(value).split(/[^a-z0-9]+/).filter(Boolean);
  };

  const resolveMask = (field) => {
    if (!field || field.tagName !== "INPUT" || field.readOnly || field.disabled) {
      return "";
    }

    const explicit = normalize(field.dataset.mask);
    if (explicit) {
      return masks[explicit] ? explicit : aliases[explicit] || "";
    }

    const type = normalize(field.getAttribute("type") || "text");
    if (ignoredTypes.has(type)) {
      return "";
    }

    const tokens = fieldTokens(field);
    if (tokens.includes("cpf")) return "cpf";
    if (tokens.includes("cep")) return "cep";
    if (tokens.some((token) => ["telefone", "celular", "whatsapp", "phone", "tel"].includes(token))) {
      return "telefone";
    }
    if (tokens.some((token) => ["data", "nascimento", "validade", "vigencia"].includes(token))) {
      return "date";
    }
    return "";
  };

  const applyMask = (field) => {
    const mask = resolveMask(field);
    if (!mask || !masks[mask]) {
      return;
    }

    const previous = field.value;
    const previousLength = previous.length;
    const previousStart = field.selectionStart || previousLength;
    const formatted = masks[mask](previous);
    field.value = formatted;
    field.dataset.appliedMask = mask;

    const maxLengthByMask = { cpf: 14, telefone: 15, cep: 9, date: 10 };
    if (field.maxLength !== maxLengthByMask[mask]) {
      field.maxLength = maxLengthByMask[mask];
    }
    if (!field.inputMode) {
      field.inputMode = "numeric";
    }

    if (document.activeElement === field && field.setSelectionRange) {
      const delta = formatted.length - previousLength;
      const nextPosition = Math.max(0, previousStart + delta);
      field.setSelectionRange(nextPosition, nextPosition);
    }
  };

  document.addEventListener("input", (event) => {
    applyMask(event.target);
  });

  document.addEventListener("focusin", (event) => {
    applyMask(event.target);
  });

  document.addEventListener("change", (event) => {
    applyMask(event.target);
  });

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("input").forEach(applyMask);

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType !== Node.ELEMENT_NODE) {
            return;
          }
          if (node.matches && node.matches("input")) {
            applyMask(node);
          }
          if (node.querySelectorAll) {
            node.querySelectorAll("input").forEach(applyMask);
          }
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();

document.addEventListener("DOMContentLoaded", () => {
  const toggleButtons = document.querySelectorAll("[data-filter-toggle]");

  toggleButtons.forEach((btn) => {
    const root = btn.closest("[data-filters-root]") || document;
    const panel =
      root.querySelector("[data-filter-panel]") ||
      document.querySelector(btn.dataset.target);

    const toggle = () => {
      if (!panel) return;
      const isOpen = panel.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    };

    btn.addEventListener("click", toggle);
  });
});
