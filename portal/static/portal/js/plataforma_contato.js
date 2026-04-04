document.addEventListener("DOMContentLoaded", () => {
  const leadPage = document.querySelector("[data-lead-page]");
  if (!leadPage) {
    return;
  }

  const modal = document.querySelector("[data-lead-modal]");
  const scrollArea = document.querySelector("[data-lead-scroll-area]");
  const openTriggers = document.querySelectorAll("[data-lead-open-modal]");
  const closeTriggers = document.querySelectorAll("[data-lead-close]");
  const closeButton = modal?.querySelector("[data-lead-close-button]");
  const consentCheckbox = modal?.querySelector("[data-lead-confirm-checkbox]");
  const confirmButton = modal?.querySelector("[data-lead-confirm]");
  const consentInput = document.querySelector("[data-lead-consent-input]");
  const consentStatus = document.querySelector("[data-lead-consent-status]");
  const scrollStatus = modal?.querySelector("[data-lead-scroll-status]");
  const form = document.querySelector("[data-lead-form]");

  if (!modal || !scrollArea || !consentCheckbox || !confirmButton || !consentInput || !form) {
    return;
  }

  const setAcceptedState = (accepted) => {
    consentInput.value = accepted ? "1" : "";
    if (consentStatus) {
      consentStatus.textContent = accepted
        ? "Termo lido e aceito."
        : "Leitura e aceite pendentes.";
    }
  };

  let reachedBottom = consentInput.value === "1";
  if (reachedBottom) {
    setAcceptedState(true);
    consentCheckbox.checked = true;
  }

  const syncGate = () => {
    if (reachedBottom) {
      consentCheckbox.disabled = false;
      confirmButton.disabled = false;
      if (closeButton) {
        closeButton.disabled = false;
      }
      if (scrollStatus) {
        scrollStatus.textContent = "Leitura concluida. Marque o checkbox e confirme o aceite.";
      }
      return;
    }

    const isAtBottom =
      scrollArea.scrollTop + scrollArea.clientHeight >= scrollArea.scrollHeight - 12;
    if (isAtBottom) {
      reachedBottom = true;
      syncGate();
    }
  };

  const openModal = () => {
    modal.classList.remove("is-hidden");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("portal-modal-open");
    if (!reachedBottom) {
      scrollArea.scrollTop = 0;
      consentCheckbox.checked = false;
    }
    syncGate();
  };

  const closeModal = (force = false) => {
    if (!force && !reachedBottom) {
      return;
    }
    modal.classList.add("is-hidden");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("portal-modal-open");
  };

  openTriggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      openModal();
    });
  });

  closeTriggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      closeModal(false);
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("is-hidden")) {
      event.preventDefault();
      closeModal(false);
    }
  });

  scrollArea.addEventListener("scroll", syncGate);
  syncGate();

  confirmButton.addEventListener("click", () => {
    if (!reachedBottom) {
      return;
    }
    if (!consentCheckbox.checked) {
      if (scrollStatus) {
        scrollStatus.textContent = "Marque o checkbox para confirmar o aceite.";
      }
      return;
    }
    setAcceptedState(true);
    closeModal(true);
  });

  form.addEventListener("submit", (event) => {
    if (consentInput.value === "1") {
      return;
    }
    event.preventDefault();
    openModal();
    if (scrollStatus && reachedBottom) {
      scrollStatus.textContent = "Marque o checkbox e confirme o aceite para enviar o formulario.";
    }
  });
});
