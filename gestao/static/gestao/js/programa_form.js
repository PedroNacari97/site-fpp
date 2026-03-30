(() => {
  const setupProgramRules = () => {
    const tipo = document.getElementById("id_tipo");
    const programaBase = document.getElementById("id_programa_base");
    const regraReset = document.getElementById("id_tipo_regra_reset");
    const diasReset = document.getElementById("id_dias_reset");
    if (!tipo || !programaBase || !regraReset || !diasReset) {
      return;
    }

    const syncProgramaBase = () => {
      const isPrincipal = tipo.value === "principal";
      programaBase.disabled = isPrincipal;
      if (isPrincipal) {
        programaBase.value = "";
      }
    };

    const syncDiasReset = () => {
      const usesDays = regraReset.value === "dias";
      diasReset.disabled = !usesDays;
      if (!usesDays) {
        diasReset.value = "";
      }
    };

    tipo.addEventListener("change", syncProgramaBase);
    regraReset.addEventListener("change", syncDiasReset);
    syncProgramaBase();
    syncDiasReset();
  };

  const setupLogoFallbacks = () => {
    document.querySelectorAll("[data-program-logo-img]").forEach((image) => {
      image.addEventListener("error", () => {
        image.remove();
      });
    });
  };

  const setupLogoPreview = () => {
    const input = document.getElementById("id_logo");
    const nameField = document.getElementById("id_nome");
    const preview = document.querySelector("[data-program-logo-preview]");
    const fallback = preview instanceof HTMLElement
      ? preview.querySelector(".points-program-form__logo-fallback, .points-program__logo-fallback")
      : null;

    const syncFallbackText = () => {
      if (!(nameField instanceof HTMLInputElement) || !(fallback instanceof HTMLElement)) {
        return;
      }
      const initials = String(nameField.value || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((chunk) => chunk[0])
        .join("")
        .toUpperCase();
      fallback.textContent = initials || "PF";
    };

    if (nameField instanceof HTMLInputElement) {
      nameField.addEventListener("input", syncFallbackText);
      syncFallbackText();
    }

    if (!(input instanceof HTMLInputElement) || !(preview instanceof HTMLElement)) {
      return;
    }

    input.addEventListener("change", () => {
      const [file] = Array.from(input.files || []);
      const existing = preview.querySelector("[data-program-logo-img]");
      if (existing) {
        existing.remove();
      }
      if (!file) {
        return;
      }

      const objectUrl = URL.createObjectURL(file);
      const image = document.createElement("img");
      image.src = objectUrl;
      image.alt = "Preview da logo";
      image.className = "points-program-form__logo-image";
      image.setAttribute("data-program-logo-img", "true");
      image.addEventListener("load", () => {
        URL.revokeObjectURL(objectUrl);
      });
      image.addEventListener("error", () => {
        URL.revokeObjectURL(objectUrl);
        image.remove();
      });
      preview.prepend(image);
    });
  };

  setupProgramRules();
  setupLogoFallbacks();
  setupLogoPreview();
})();
