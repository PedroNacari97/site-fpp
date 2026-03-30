document.addEventListener("DOMContentLoaded", () => {
  const copyButton = document.querySelector("[data-copy-text]");
  if (!copyButton) {
    return;
  }
  copyButton.addEventListener("click", async () => {
    const text = copyButton.dataset.copyText || "";
    try {
      await navigator.clipboard.writeText(text);
      copyButton.textContent = "✅ Texto copiado";
      setTimeout(() => {
        copyButton.textContent = "📋 Copiar texto completo";
      }, 2000);
    } catch (error) {
      copyButton.textContent = "❌ Falha ao copiar";
    }
  });
});
