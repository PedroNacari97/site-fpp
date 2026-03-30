document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const openButton = document.querySelector("[data-sidebar-open]");
  const body = document.body;

  if (!sidebar || !overlay || !openButton) {
    return;
  }

  const openSidebar = () => {
    body.classList.add("sidebar-open");
    openButton.setAttribute("aria-expanded", "true");
    sidebar.setAttribute("aria-hidden", "false");
  };

  const closeSidebar = () => {
    body.classList.remove("sidebar-open");
    openButton.setAttribute("aria-expanded", "false");
    sidebar.setAttribute("aria-hidden", "true");
  };

  openButton.addEventListener("click", openSidebar);
  overlay.addEventListener("click", closeSidebar);

  const navLinks = sidebar.querySelectorAll("a.nav-item");
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      if (window.innerWidth < 768) {
        closeSidebar();
      }
    });
  });
});
