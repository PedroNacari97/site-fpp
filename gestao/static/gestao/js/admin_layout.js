document.addEventListener("DOMContentLoaded", () => {
  const toggles = document.querySelectorAll("[data-sidebar-toggle], [data-sidebar-open]");
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const body = document.body;

  const isDesktop = () => window.innerWidth >= 1024;

  const setAriaState = (isOpen) => {
    if (!sidebar) return;
    sidebar.setAttribute("aria-hidden", isDesktop() ? "false" : isOpen ? "false" : "true");
  };

  const showOverlay = (isOpen) => {
    if (!overlay) return;
    overlay.classList.toggle("hidden", !isOpen);
  };

  const openSidebar = () => {
    body.classList.add("sidebar-open");
    setAriaState(true);
    showOverlay(true);
    toggles.forEach((btn) => btn.setAttribute("aria-expanded", "true"));
  };

  const closeSidebar = () => {
    body.classList.remove("sidebar-open");
    setAriaState(false);
    showOverlay(false);
    toggles.forEach((btn) => btn.setAttribute("aria-expanded", "false"));
  };

  const toggleSidebar = () => {
    if (body.classList.contains("sidebar-open")) {
      closeSidebar();
    } else {
      openSidebar();
    }
  };

  toggles.forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      toggleSidebar();
    });
  });

  overlay?.addEventListener("click", closeSidebar);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSidebar();
    }
  });

  const handleResize = () => {
    if (isDesktop()) {
      body.classList.remove("sidebar-open");
      showOverlay(false);
      setAriaState(true);
    } else {
      setAriaState(body.classList.contains("sidebar-open"));
    }
  };

  window.addEventListener("resize", handleResize);
  handleResize();
});
