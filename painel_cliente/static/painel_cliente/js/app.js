import { initLoginFocus } from "./modules/login.js";
import { initTableEnhancements } from "./modules/tables.js";

const initSidebarToggle = () => {
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const openButton = document.querySelector("[data-sidebar-open]");
  const closeButton = document.querySelector("[data-sidebar-close]");

  if (!sidebar || !overlay || !openButton || !closeButton) {
    return;
  }

  const closeSidebar = () => {
    sidebar.classList.remove("is-open");
    overlay.classList.remove("is-visible");
  };

  const openSidebar = () => {
    sidebar.classList.add("is-open");
    overlay.classList.add("is-visible");
  };

  openButton.addEventListener("click", openSidebar);
  closeButton.addEventListener("click", closeSidebar);
  overlay.addEventListener("click", closeSidebar);
};

document.addEventListener("DOMContentLoaded", () => {
  initLoginFocus();
  initTableEnhancements();
  initSidebarToggle();
});
