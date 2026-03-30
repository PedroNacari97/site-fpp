const isLoginPage = () => {
  const path = window.location.pathname.toLowerCase();
  return document.body.classList.contains("login-page") || path.includes("login");
};

const applyTheme = () => {
  document.body.classList.toggle("dark-mode", !isLoginPage());
};

export const initThemeToggle = () => {
  applyTheme();
};
