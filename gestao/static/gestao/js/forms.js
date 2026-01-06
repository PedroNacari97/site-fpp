document.addEventListener("input", (event) => {
  const target = event.target;
  if (target && target.dataset.mask === "date") {
    const digits = target.value.replace(/\D/g, "").slice(0, 8);
    const parts = [];
    if (digits.length > 0) {
      parts.push(digits.slice(0, 2));
    }
    if (digits.length >= 3) {
      parts.push(digits.slice(2, 4));
    }
    if (digits.length >= 5) {
      parts.push(digits.slice(4, 8));
    }
    target.value = parts.join("/");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const toggleButtons = document.querySelectorAll("[data-filter-toggle]");

  toggleButtons.forEach((btn) => {
    const root = btn.closest("[data-filters-root]") || document;
    const panel =
      root.querySelector("[data-filter-panel]") ||
      document.querySelector(btn.dataset.target);

    const toggle = () => {
      if (!panel) return;
      const isOpen = panel.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", isOpen ? "true" : "false");
    };

    btn.addEventListener("click", toggle);
  });
});
