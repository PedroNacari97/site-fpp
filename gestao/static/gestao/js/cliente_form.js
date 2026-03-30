(() => {
  const fullName = document.getElementById("id_full_name");
  const firstName = document.getElementById("id_first_name");
  const lastName = document.getElementById("id_last_name");
  if (!fullName || !firstName || !lastName) {
    return;
  }

  const joinName = () => {
    const current = [firstName.value, lastName.value].filter(Boolean).join(" ").trim();
    fullName.value = current;
  };

  const splitName = () => {
    const raw = (fullName.value || "").trim().replace(/\s+/g, " ");
    if (!raw) {
      firstName.value = "";
      lastName.value = "";
      return;
    }
    const parts = raw.split(" ");
    firstName.value = parts.shift() || "";
    lastName.value = parts.join(" ");
  };

  joinName();
  fullName.addEventListener("input", splitName);
})();
