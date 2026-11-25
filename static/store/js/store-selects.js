(() => {
  function enhance(select) {
    if (select.hidden || select.dataset.mediaField || select.classList.contains("search-select-source")) return;
    const label = select.labels?.[0];
    const name = select.getAttribute("aria-label") || label?.querySelector("span")?.textContent || "Выбор значений";
    const container = document.createElement("div");
    container.className = "search-select";
    const chips = document.createElement("div");
    chips.className = "search-select-chips";
    const dropdown = document.createElement("details");
    const toggle = document.createElement("summary");
    toggle.textContent = "Выбрать";
    toggle.setAttribute("aria-label", name + " — выбрать");
    const panel = document.createElement("div");
    panel.className = "search-select-menu";
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "Поиск";
    search.setAttribute("aria-label", "Поиск: " + name);
    const options = document.createElement("div");
    options.className = "search-select-options";
    panel.append(search, options);
    dropdown.append(toggle, panel);
    container.append(chips, dropdown);
    if (label && select.parentElement === label) {
      const field = document.createElement("div");
      field.className = label.className + " search-select-field";
      label.replaceWith(field);
      field.append(...label.childNodes);
    }
    select.after(container);
    select.classList.add("search-select-source");

    function change(option, value) {
      if (select.disabled) return;
      option.selected = value;
      select.dispatchEvent(new Event("change", {bubbles: true}));
    }
    function renderOptions() {
      const query = search.value.trim().toLocaleLowerCase();
      const buttons = [...select.options].filter(option =>
        option.value && option.text.toLocaleLowerCase().includes(query)).map(option => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = option.text;
        button.dataset.value = option.value;
        button.disabled = select.disabled || option.disabled || Boolean(option.closest("optgroup")?.disabled);
        button.setAttribute("aria-pressed", String(option.selected));
        button.addEventListener("click", () => change(option, !option.selected));
        return button;
      });
      options.replaceChildren(...buttons);
      if (!buttons.length) options.textContent = "Ничего не найдено";
    }
    function render() {
      toggle.tabIndex = select.disabled ? -1 : 0;
      toggle.setAttribute("aria-disabled", String(select.disabled));
      toggle.setAttribute("aria-invalid", String(select.getAttribute("aria-invalid") === "true" || !select.validity.valid));
      if (select.disabled) dropdown.open = false;
      chips.replaceChildren(...[...select.selectedOptions].map(option => {
        const chip = document.createElement("span");
        const remove = document.createElement("button");
        chip.className = "search-select-chip";
        chip.append(option.text, remove);
        remove.type = "button";
        remove.textContent = "×";
        remove.disabled = select.disabled || option.disabled;
        remove.setAttribute("aria-label", "Убрать " + option.text);
        remove.addEventListener("click", () => {
          toggle.focus();
          change(option, false);
        });
        return chip;
      }));
      const byValue = new Map([...select.options].map(option => [option.value, option]));
      for (const button of options.querySelectorAll("button")) {
        const option = byValue.get(button.dataset.value);
        button.setAttribute("aria-pressed", String(option.selected));
        button.disabled = select.disabled || option.disabled || Boolean(option.closest("optgroup")?.disabled);
      }
    }
    toggle.addEventListener("click", event => {
      event.preventDefault();
      if (select.disabled) return;
      dropdown.open = !dropdown.open;
      if (dropdown.open) {
        search.value = "";
        renderOptions();
        search.focus();
      }
    });
    container.addEventListener("keydown", event => {
      if (!dropdown.open) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        dropdown.open = false;
        toggle.focus();
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        const buttons = [search, ...options.querySelectorAll("button:enabled")];
        const next = buttons.indexOf(document.activeElement) + (event.key === "ArrowDown" ? 1 : -1);
        if (buttons[next]) {
          event.preventDefault();
          buttons[next].focus();
        }
      }
      if (event.target === search && event.key === "Enter") event.preventDefault();
    });
    container.addEventListener("focusout", event => {
      if (!container.contains(event.relatedTarget)) dropdown.open = false;
    });
    search.addEventListener("input", renderOptions);
    select.addEventListener("change", render);
    select.addEventListener("invalid", event => {
      event.preventDefault();
      toggle.setAttribute("aria-invalid", "true");
      toggle.focus();
    });
    select.form?.addEventListener("reset", () => queueMicrotask(render));
    new MutationObserver(render).observe(select, {attributes: true, attributeFilter: ["disabled", "aria-invalid"]});
    render();
  }
  window.enhanceStoreSelects = (root) => root.querySelectorAll("select[multiple]").forEach(enhance);
  window.enhanceStoreSelects(document);
})();
