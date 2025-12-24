export const initTableEnhancements = () => {
  document.querySelectorAll("table").forEach((table) => {
    table.dataset.enhanced = "true";
  });
};
