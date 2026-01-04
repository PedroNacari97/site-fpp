const dateFormat = "Y-m-d";

const parseValue = (input) => {
  if (!input || !input.value) {
    return [];
  }
  try {
    const parsed = JSON.parse(input.value);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
};

const formatDate = (dateObj) => dateObj.toISOString().slice(0, 10);

const expandRange = (rangeDates) => {
  if (!rangeDates || rangeDates.length < 2) {
    return [];
  }
  const [start, end] = rangeDates;
  const dates = [];
  const current = new Date(start);
  while (current <= end) {
    dates.push(formatDate(current));
    current.setDate(current.getDate() + 1);
  }
  return dates;
};

const renderChips = (container, dates) => {
  container.innerHTML = "";
  if (!dates.length) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "Nenhuma data selecionada.";
    container.appendChild(empty);
    return;
  }
  dates.forEach((date) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "date-chip is-removable";
    chip.dataset.dateValue = date;
    chip.innerHTML = `<span>${date}</span><span class="remove">×</span>`;
    container.appendChild(chip);
  });
};

const setupDateGroup = (groupEl) => {
  const hiddenInput = groupEl.querySelector("input[type='hidden']");
  const chipsContainer = groupEl.querySelector("[data-chips]");
  const calendarInput = groupEl.querySelector("[data-calendar]");
  const rangeInput = groupEl.querySelector("[data-range]");
  const confirmButton = groupEl.querySelector("[data-confirm]");

  let selectedDates = parseValue(hiddenInput);

  const syncHidden = () => {
    hiddenInput.value = JSON.stringify(selectedDates);
    renderChips(chipsContainer, selectedDates);
  };

  syncHidden();

  const calendar = flatpickr(calendarInput, {
    mode: "multiple",
    dateFormat,
    allowInput: false,
  });

  const rangePicker = flatpickr(rangeInput, {
    mode: "range",
    dateFormat,
    allowInput: false,
  });

  confirmButton.addEventListener("click", () => {
    const multipleDates = calendar.selectedDates.map(formatDate);
    const rangeDates = expandRange(rangePicker.selectedDates);
    const merged = Array.from(new Set([...selectedDates, ...multipleDates, ...rangeDates]));
    selectedDates = merged.sort();
    calendar.clear();
    rangePicker.clear();
    syncHidden();
  });

  chipsContainer.addEventListener("click", (event) => {
    const target = event.target.closest(".date-chip.is-removable");
    if (!target) {
      return;
    }
    const value = target.dataset.dateValue;
    selectedDates = selectedDates.filter((item) => item !== value);
    syncHidden();
  });
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-date-group]").forEach(setupDateGroup);
});
