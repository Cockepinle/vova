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
  function enhanceSingle(select) {
    if (select.hidden || select.dataset.mediaField || select.classList.contains("search-select-source")) return;
    const dropdown = document.createElement("details");
    dropdown.className = "search-select single-store-select";
    const toggle = document.createElement("summary");
    const panel = document.createElement("div");
    panel.className = "search-select-menu search-select-options";
    dropdown.append(toggle, panel);
    const label = select.labels?.[0];
    const labelledBy = select.getAttribute("aria-labelledby");
    const name = select.getAttribute("aria-label") || document.getElementById(labelledBy)?.textContent
      || label?.querySelector("span")?.textContent || label?.textContent;
    select.after(dropdown);
    select.classList.add("search-select-source");

    function sync() {
      const text = select.selectedOptions[0]?.text || "Выбрать";
      toggle.textContent = text;
      toggle.setAttribute("aria-label", name ? name.trim() + ": " + text : text);
      toggle.setAttribute("aria-disabled", String(select.disabled));
      toggle.setAttribute("aria-invalid", String(select.getAttribute("aria-invalid") === "true"));
      toggle.tabIndex = select.disabled ? -1 : 0;
      if (select.disabled) dropdown.open = false;
    }

    function open() {
      const buttons = [...select.options].map(option => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = option.text;
        button.disabled = option.disabled || Boolean(option.closest("optgroup")?.disabled);
        button.setAttribute("aria-pressed", String(option.selected));
        button.addEventListener("click", event => {
          event.preventDefault();
          dropdown.open = false;
          toggle.focus();
          if (!option.selected) {
            select.selectedIndex = option.index;
            select.dispatchEvent(new Event("input", {bubbles: true}));
            select.dispatchEvent(new Event("change", {bubbles: true}));
          }
        });
        return button;
      });
      panel.replaceChildren(...buttons);
      dropdown.open = true;
    }

    toggle.addEventListener("click", event => {
      event.preventDefault();
      if (select.disabled) return;
      if (dropdown.open) dropdown.open = false;
      else open();
    });
    dropdown.addEventListener("keydown", event => {
      if (event.key === "Escape" && dropdown.open) {
        event.preventDefault();
        event.stopPropagation();
        dropdown.open = false;
        toggle.focus();
      } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key) && !select.disabled) {
        event.preventDefault();
        const opening = !dropdown.open;
        if (opening) open();
        const buttons = [...panel.querySelectorAll("button:enabled")];
        const index = buttons.indexOf(document.activeElement);
        const selected = buttons.findIndex(button => button.getAttribute("aria-pressed") === "true");
        const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
          : index < 0 ? Math.max(0, selected)
          : Math.max(0, Math.min(buttons.length - 1, index + (event.key === "ArrowUp" ? -1 : 1)));
        if (opening) requestAnimationFrame(() => { if (dropdown.open) buttons[next]?.focus(); });
        else buttons[next]?.focus();
      }
    });
    dropdown.addEventListener("focusout", event => {
      if (!dropdown.contains(event.relatedTarget)) dropdown.open = false;
    });
    select.addEventListener("change", sync);
    select.addEventListener("invalid", event => {
      event.preventDefault();
      toggle.setAttribute("aria-invalid", "true");
      toggle.focus();
    });
    select.form?.addEventListener("reset", () => queueMicrotask(sync));
    new MutationObserver(sync).observe(select, {attributes: true, childList: true, subtree: true});
    sync();
  }

  document.addEventListener("pointerdown", event => {
    for (const dropdown of document.querySelectorAll(".search-select details[open], .single-store-select[open]")) {
      if (!dropdown.parentElement.contains(event.target) || (dropdown.matches(".single-store-select") && !dropdown.contains(event.target))) {
        dropdown.open = false;
      }
    }
  });

  window.enhanceStoreSelects = root => {
    root.querySelectorAll("select[multiple]").forEach(enhance);
    if (document.body.hasAttribute("data-management-user") && !CSS.supports("selector(::picker(select))")) {
      root.querySelectorAll("select:not([multiple], [size], .media-picker-select)").forEach(enhanceSingle);
    }
  };
  window.enhanceStoreSelects(document);
})();
