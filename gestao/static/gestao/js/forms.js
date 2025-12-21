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
