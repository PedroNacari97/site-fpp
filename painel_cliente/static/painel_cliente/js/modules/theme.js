const STORAGE_KEY = "darkMode";

const applyTheme = (isDark) => {
  document.body.classList.toggle("dark-mode", isDark);
  const toggles = document.querySelectorAll("[data-theme-toggle]");
  toggles.forEach((toggle) => {
    toggle.textContent = isDark ? "☀️" : "🌙";
    toggle.setAttribute("aria-pressed", isDark ? "true" : "false");
    toggle.setAttribute(
      "aria-label",
      isDark ? "Desativar modo escuro" : "Ativar modo escuro"
    );
  });
};

export const initThemeToggle = () => {
  const isDark = localStorage.getItem(STORAGE_KEY) === "enabled";
  applyTheme(isDark);

  const toggles = document.querySelectorAll("[data-theme-toggle]");
  if (!toggles.length) {
    return;
  }

  toggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const nextState = !document.body.classList.contains("dark-mode");
      localStorage.setItem(STORAGE_KEY, nextState ? "enabled" : "disabled");
      applyTheme(nextState);
    });
  });
};
