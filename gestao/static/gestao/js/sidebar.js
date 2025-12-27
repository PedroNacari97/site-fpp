document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const openButton = document.querySelector("[data-sidebar-open]");
  const closeButton = document.querySelector("[data-sidebar-close]");

  if (!sidebar || !overlay || !openButton || !closeButton) {
    return;
  }

  const openSidebar = () => {
    sidebar.classList.add("is-open");
    overlay.classList.add("is-visible");
  };

  const closeSidebar = () => {
    sidebar.classList.remove("is-open");
    overlay.classList.remove("is-visible");
  };

  openButton.addEventListener("click", openSidebar);
  closeButton.addEventListener("click", closeSidebar);
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
