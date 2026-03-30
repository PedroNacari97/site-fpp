/**
 * @typedef {"default" | "superadmin"} LoginMode
 */

const formatCpf = (value) => {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 11);
  return digits
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1-$2");
};

export const initLoginExperience = () => {
  const form = document.querySelector("[data-login-form]");
  if (!form) {
    return;
  }

  /** @type {LoginMode} */
  const mode = form.dataset.loginMode === "superadmin" ? "superadmin" : "default";
  const identifier = form.querySelector("input[name='identifier']");
  const mfaCode = form.querySelector("input[name='mfa_code']");

  if (identifier instanceof HTMLInputElement) {
    identifier.focus();
    if (mode === "default" && identifier.dataset.identifierType === "cpf") {
      identifier.addEventListener("input", () => {
        const cursorAtEnd = identifier.selectionStart === identifier.value.length;
        identifier.value = formatCpf(identifier.value);
        if (cursorAtEnd) {
          identifier.setSelectionRange(identifier.value.length, identifier.value.length);
        }
      });
    }
  }

  if (mfaCode instanceof HTMLInputElement) {
    mfaCode.focus();
    mfaCode.addEventListener("input", () => {
      mfaCode.value = String(mfaCode.value || "").replace(/\D/g, "").slice(0, 6);
    });
  }
};
