import { initLoginFocus } from "./modules/login.js";
import { initTableEnhancements } from "./modules/tables.js";

const initSidebarToggle = () => {
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const openButton = document.querySelector("[data-sidebar-open]");
  const closeButton = document.querySelector("[data-sidebar-close]");
  const body = document.body;

  if (!sidebar || !overlay || !openButton) {
    return;
  }

  const closeSidebar = () => {
    body.classList.remove("sidebar-open");
    openButton.setAttribute("aria-expanded", "false");
    sidebar.setAttribute("aria-hidden", "true");
  };

  const openSidebar = () => {
    body.classList.add("sidebar-open");
    openButton.setAttribute("aria-expanded", "true");
    sidebar.setAttribute("aria-hidden", "false");
  };

  openButton.addEventListener("click", openSidebar);
  if (closeButton) {
    closeButton.addEventListener("click", closeSidebar);
  }
  overlay.addEventListener("click", closeSidebar);

  const navLinks = sidebar.querySelectorAll("a.nav-item");
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      if (window.innerWidth < 768) {
        closeSidebar();
      }
    });
  });
};

document.addEventListener("DOMContentLoaded", () => {
  initLoginFocus();
  initTableEnhancements();
  initSidebarToggle();
});
