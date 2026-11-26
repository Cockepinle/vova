window.createProductPicker = (toggle, {label, placeholder, items, footer, onOpen}) => {
  const panel = document.createElement("div");
  panel.className = "product-picker";
  panel.id = toggle.dataset.attributePicker === undefined ? "variant-picker" : "attribute-picker";
  panel.setAttribute("popover", "manual");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", label);
  toggle.setAttribute("aria-haspopup", "dialog");
  toggle.setAttribute("aria-controls", panel.id);
  toggle.setAttribute("aria-expanded", "false");
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = placeholder;
  search.setAttribute("aria-label", placeholder);
  const options = document.createElement("div");
  options.className = "product-picker-options";
  panel.append(search, options);
  if (footer) panel.append(footer);
  toggle.after(panel);
  let opened = false;

  function render() {
    const entries = items(search.value.trim().toLocaleLowerCase());
    options.replaceChildren(...entries);
    if (!entries.length) options.textContent = "Ничего не найдено";
  }
  function position() {
    if (!opened) return;
    const anchor = toggle.getBoundingClientRect();
    const viewport = window.visualViewport;
    const left = viewport?.offsetLeft ?? 0;
    const top = viewport?.offsetTop ?? 0;
    const width = viewport?.width ?? document.documentElement.clientWidth;
    const height = viewport?.height ?? document.documentElement.clientHeight;
    const bottom = top + height;
    const below = bottom - anchor.bottom - 16;
    const above = anchor.top - top - 16;
    const upwards = below < 300 && above > below;
    const panelWidth = Math.min(Math.max(anchor.width, 325), 440, width - 24);
    Object.assign(panel.style, {
      width: panelWidth + "px",
      left: Math.max(left + 12, Math.min(anchor.left, left + width - panelWidth - 12)) + "px",
      top: upwards ? "auto" : Math.max(top + 8, anchor.bottom + 6) + "px",
      bottom: upwards ? Math.max(document.documentElement.clientHeight - bottom + 8,
        document.documentElement.clientHeight - anchor.top + 6) + "px" : "auto",
      maxHeight: Math.max(0, upwards ? above : below) + "px",
    });
  }
  function close(focus = false) {
    if (!opened) return;
    opened = false;
    panel.hidePopover();
    toggle.setAttribute("aria-expanded", "false");
    if (focus) toggle.focus();
  }
  function open() {
    if (opened || toggle.disabled) return;
    opened = true;
    onOpen?.();
    search.value = "";
    render();
    position();
    panel.showPopover();
    toggle.setAttribute("aria-expanded", "true");
    search.focus({preventScroll: true});
  }
  toggle.addEventListener("click", () => opened ? close(true) : open());
  toggle.addEventListener("keydown", event => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      open();
    }
  });
  search.addEventListener("input", render);
  panel.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (event.target === search && event.key === "Enter") {
      event.preventDefault();
      options.querySelector("button:enabled")?.click();
    } else if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      const controls = [search, ...options.querySelectorAll("button:enabled, input:enabled")];
      const current = controls.indexOf(document.activeElement);
      if (current < 0) return;
      event.preventDefault();
      controls[Math.max(0, Math.min(controls.length - 1, current + (event.key === "ArrowDown" ? 1 : -1)))].focus();
    }
  });
  document.addEventListener("pointerdown", event => {
    if (!panel.contains(event.target) && !toggle.contains(event.target)) close();
  });
  document.addEventListener("focusin", event => {
    if (!panel.contains(event.target) && !toggle.contains(event.target)) close();
  });
  window.addEventListener("resize", position);
  window.addEventListener("scroll", position, true);
  window.visualViewport?.addEventListener("resize", position);
  window.visualViewport?.addEventListener("scroll", position);
  return {close, render};
};

(() => {
  const select = document.querySelector("[data-product-editor] #id_variant_group");
  if (!select) return;
  const field = select.closest("label");
  const label = field.querySelector("span");
  const wrapper = document.createElement("div");
  wrapper.className = "product-group-field";
  field.replaceWith(wrapper);
  wrapper.append(...field.childNodes);
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "product-picker-toggle product-group-toggle";
  const value = document.createElement("span");
  label.id = "variant-picker-label";
  value.id = "variant-picker-value";
  toggle.setAttribute("aria-labelledby", label.id + " " + value.id);
  toggle.append(value);
  select.after(toggle);
  select.hidden = true;
  const empty = "Без группы модификаций";
  const picker = window.createProductPicker(toggle, {
    label: label.textContent,
    placeholder: "Поиск по названию группы",
    items: query => [...select.options].filter(option =>
      (option.value ? option.text : empty).toLocaleLowerCase().includes(query)
    ).map(option => {
      const button = document.createElement("button");
      button.type = "button";
      const caption = document.createElement("span");
      caption.textContent = option.value ? option.text : empty;
      button.title = caption.textContent;
      button.append(caption);
      button.disabled = option.disabled;
      button.setAttribute("aria-pressed", String(option.selected));
      button.addEventListener("click", () => {
        select.value = option.value;
        select.dispatchEvent(new Event("input", {bubbles: true}));
        select.dispatchEvent(new Event("change", {bubbles: true}));
        picker.close(true);
      });
      return button;
    }),
  });
  function sync() {
    value.textContent = select.value ? select.selectedOptions[0].text : empty;
    toggle.disabled = select.disabled;
    toggle.setAttribute("aria-invalid", String(select.getAttribute("aria-invalid") === "true"));
  }
  select.addEventListener("change", sync);
  select.form.addEventListener("reset", () => queueMicrotask(sync));
  sync();
})();
