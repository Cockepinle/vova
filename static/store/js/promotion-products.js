(() => {
  const picker = document.querySelector("[data-promotion-products]");
  const search = picker.querySelector("[data-promotion-search]");
  const category = picker.querySelector("[data-promotion-category]");
  const selection = picker.querySelector("[data-promotion-selection]");
  const options = [...picker.querySelectorAll("[data-promotion-option]")].map(row => ({
    row, input: row.querySelector("input"), label: row.textContent.trim(),
  }));
  picker.querySelector("[data-promotion-controls]").hidden = false;
  picker.querySelector("[data-promotion-selected]").hidden = false;

  function filter() {
    const term = search.value.trim().toLocaleLowerCase("ru");
    for (const {row, input, label} of options) {
      row.hidden = Boolean(category.value && input.dataset.category !== category.value)
        || !label.toLocaleLowerCase("ru").includes(term);
    }
    picker.querySelector("[data-promotion-empty]").hidden = options.some(({row}) => !row.hidden) || !options.length;
  }

  function showSelection() {
    const items = options.filter(({input}) => input.checked).map(({input, label}) => {
      const item = document.createElement("li");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "ghost-button";
      remove.textContent = "Убрать";
      remove.setAttribute("aria-label", `Убрать ${label}`);
      remove.addEventListener("click", () => {
        input.checked = false;
        showSelection();
        search.focus();
      });
      item.append(label, remove);
      return item;
    });
    if (!items.length) {
      const empty = document.createElement("li");
      empty.textContent = "Товары не выбраны.";
      items.push(empty);
    }
    selection.replaceChildren(...items);
  }

  for (const [selector, checked] of [["[data-promotion-select]", true], ["[data-promotion-unselect]", false]]) {
    picker.querySelector(selector).addEventListener("click", () => {
      for (const {row, input} of options) if (!row.hidden) input.checked = checked;
      showSelection();
    });
  }
  search.addEventListener("input", filter);
  category.addEventListener("change", filter);
  picker.addEventListener("change", showSelection);
  showSelection();
})();
