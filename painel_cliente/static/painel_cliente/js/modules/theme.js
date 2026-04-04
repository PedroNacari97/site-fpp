const applyTheme = () => {
  const explicitTheme = (document.body.dataset.defaultTheme || "").toLowerCase().trim();

  if (explicitTheme === "dark") {
    document.body.classList.add("dark-mode");
    return;
  }

  if (explicitTheme === "light") {
    document.body.classList.remove("dark-mode");
    return;
  }

  document.body.classList.remove("dark-mode");
};

export const initThemeToggle = () => {
  applyTheme();
};
