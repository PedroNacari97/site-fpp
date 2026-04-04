import { initLoginExperience } from "./modules/login.js";
import { initTableEnhancements } from "./modules/tables.js";
import { initThemeToggle } from "./modules/theme.js";

const initSidebarToggle = () => {
  const sidebar = document.querySelector("[data-sidebar]");
  const overlay = document.querySelector("[data-sidebar-overlay]");
  const openButton = document.querySelector("[data-sidebar-open]");
  const closeButton = document.querySelector("[data-sidebar-close]");
  const collapseButton = document.querySelector("[data-sidebar-collapse]");
  const body = document.body;
  const storageKey = "ncfly.sidebar.collapsed";

  if (!sidebar || !overlay || !openButton) {
    return;
  }

  const isDesktop = () => window.innerWidth >= 1024;

  const applyCollapsedState = (collapsed) => {
    if (!collapseButton) {
      return;
    }

    const shouldCollapse = isDesktop() && collapsed;
    body.classList.toggle("sidebar-collapsed", shouldCollapse);
    collapseButton.setAttribute("aria-pressed", shouldCollapse ? "true" : "false");
  };

  const syncCollapsedState = () => {
    if (!collapseButton) {
      return;
    }

    applyCollapsedState(window.localStorage.getItem(storageKey) === "true");
  };

  const closeSidebar = () => {
    body.classList.remove("sidebar-open");
    openButton.setAttribute("aria-expanded", "false");
    sidebar.setAttribute("aria-hidden", isDesktop() ? "false" : "true");
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

  collapseButton?.addEventListener("click", () => {
    const nextState = !(window.localStorage.getItem(storageKey) === "true");
    window.localStorage.setItem(storageKey, nextState ? "true" : "false");
    applyCollapsedState(nextState);
  });

  const navLinks = sidebar.querySelectorAll("a.nav-item, [data-sidebar-link]");
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      if (!isDesktop()) {
        closeSidebar();
      }
    });
  });

  const handleResize = () => {
    if (isDesktop()) {
      body.classList.remove("sidebar-open");
      sidebar.setAttribute("aria-hidden", "false");
    } else {
      body.classList.remove("sidebar-collapsed");
      openButton.setAttribute("aria-expanded", body.classList.contains("sidebar-open") ? "true" : "false");
      sidebar.setAttribute("aria-hidden", body.classList.contains("sidebar-open") ? "false" : "true");
    }

    syncCollapsedState();
  };

  window.addEventListener("resize", handleResize);
  handleResize();
};

const initAdminNotifications = () => {
  const root = document.querySelector("[data-notification-root]");
  const toggle = document.querySelector("[data-notification-toggle]");
  const panel = document.querySelector("[data-notification-panel]");
  const closeButton = document.querySelector("[data-notification-close]");
  const list = document.querySelector("[data-notification-list]");
  const badge = document.querySelector("[data-notification-badge]");
  const subtitle = document.querySelector("[data-notification-subtitle]");
  const markUrl = root?.dataset.notificationMarkUrl;

  if (!root || !toggle || !panel) {
    return;
  }

  const getCsrfToken = () => {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  };

  const updateUnreadState = (count) => {
    if (subtitle) {
      subtitle.textContent = `${count} não lida(s)`;
    }

    if (!badge) {
      return;
    }

    if (count > 0) {
      badge.hidden = false;
      badge.textContent = String(count);
      return;
    }

    badge.hidden = true;
    badge.textContent = "";
  };

  const ensureEmptyState = () => {
    if (!list) {
      return;
    }

    const remainingItems = list.querySelectorAll("[data-notification-item]");
    const currentEmpty = list.querySelector("[data-notification-empty]");
    if (remainingItems.length) {
      currentEmpty?.remove();
      return;
    }

    if (!currentEmpty) {
      const empty = document.createElement("div");
      empty.className = "admin-notifications-panel__empty";
      empty.dataset.notificationEmpty = "true";
      empty.textContent = "Sem notificações operacionais no momento.";
      list.appendChild(empty);
    }
  };

  const closePanel = () => {
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  };

  const openPanel = () => {
    panel.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
  };

  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    if (panel.hidden) {
      openPanel();
      return;
    }
    closePanel();
  });

  closeButton?.addEventListener("click", () => {
    closePanel();
  });

  panel.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  panel.addEventListener("click", async (event) => {
    const markButton = event.target.closest("[data-notification-mark-read]");
    if (!markButton) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    const item = markButton.closest("[data-notification-item]");
    const key = item?.dataset.notificationKey;
    if (!item || !key || !markUrl || markButton.disabled) {
      return;
    }

    markButton.disabled = true;

    try {
      const response = await fetch(markUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ key }),
      });

      if (!response.ok) {
        throw new Error("Falha ao atualizar notificação.");
      }

      const payload = await response.json();
      item.remove();
      updateUnreadState(payload.unread_count ?? 0);
      ensureEmptyState();
    } catch (error) {
      markButton.disabled = false;
      console.error(error);
    }
  });

  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) {
      closePanel();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePanel();
    }
  });

  ensureEmptyState();
};

const initAutoSubmitFilters = () => {
  const forms = document.querySelectorAll("form[data-auto-submit-filters]");

  if (!forms.length) {
    return;
  }

  const isSupportedField = (field) => {
    if (!(field instanceof HTMLElement)) {
      return false;
    }

    if (!field.closest("form[data-auto-submit-filters]")) {
      return false;
    }

    if (field.hasAttribute("data-auto-submit-ignore") || field.closest("[data-auto-submit-ignore]")) {
      return false;
    }

    if (field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement) {
      return !field.disabled;
    }

    if (!(field instanceof HTMLInputElement) || field.disabled) {
      return false;
    }

    const ignoredTypes = new Set(["button", "submit", "reset", "hidden", "file"]);
    return !ignoredTypes.has((field.type || "").toLowerCase());
  };

  forms.forEach((form) => {
    form.addEventListener("change", (event) => {
      const field = event.target;

      if (!isSupportedField(field)) {
        return;
      }

      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
        return;
      }

      form.submit();
    });
  });
};

document.addEventListener("DOMContentLoaded", () => {
  initLoginExperience();
  initTableEnhancements();
  initSidebarToggle();
  initAdminNotifications();
  initAutoSubmitFilters();
  initThemeToggle();
});
