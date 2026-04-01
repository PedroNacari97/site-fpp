document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll("[data-load-more-button]");

  buttons.forEach((button) => {
    const targetId = button.getAttribute("data-load-more-target");
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      button.remove();
      return;
    }

    const batchSize = Number.parseInt(button.getAttribute("data-batch-size") || "6", 10);
    const defaultLabel = button.getAttribute("data-label-default") || button.textContent.trim();

    const updateState = () => {
      const hiddenItems = target.querySelectorAll("[data-load-more-item].is-hidden");
      if (!hiddenItems.length) {
        const wrapper = button.closest(".portal-category-loadmore");
        if (wrapper) {
          wrapper.remove();
        } else {
          button.remove();
        }
        return;
      }

      button.textContent = `${defaultLabel} (${hiddenItems.length})`;
    };

    button.addEventListener("click", () => {
      const hiddenItems = Array.from(target.querySelectorAll("[data-load-more-item].is-hidden"));
      hiddenItems.slice(0, batchSize).forEach((item) => item.classList.remove("is-hidden"));
      updateState();
    });

    updateState();
  });
});
