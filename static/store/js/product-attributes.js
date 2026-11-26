(() => {
  const fields = document.querySelector("[data-product-attributes]");
  const dialog = document.querySelector("[data-attribute-dialog]");
  if (!fields || !dialog) return;
  const form = dialog.querySelector("form");
  const content = form.querySelector("[data-attribute-content]");
  const error = form.querySelector("[data-attribute-error]");
  const submit = form.querySelector("[type=submit]");
  const editor = fields.closest("form");
  const toggle = editor.querySelector("[data-attribute-picker]");
  const catalog = new Map(JSON.parse(document.getElementById("product-attribute-catalog").textContent)
    .map(item => [String(item.id), item.name]));
  const rows = () => [...fields.querySelectorAll("[data-product-attribute]")];
  const empty = fields.querySelector("[data-attributes-empty]");
  let row, url, trigger, busy = false;
  let pending, applying = false;

  function action(text, className) {
    const button = document.createElement("button");
    Object.assign(button, {type: "button", textContent: text, className});
    return button;
  }
  const footer = document.createElement("div");
  footer.className = "product-picker-footer";
  const count = document.createElement("span");
  count.setAttribute("role", "status");
  const pickerError = document.createElement("p");
  pickerError.setAttribute("role", "alert");
  pickerError.hidden = true;
  const create = action("+ Создать новое поле", "ghost-button");
  create.dataset.attributeNew = "";
  create.dataset.url = fields.dataset.url;
  const cancel = action("Отмена", "ghost-button");
  const apply = action("Применить", "primary-button");
  footer.append(count, create, pickerError, cancel, apply);
  function updateCount() {
    count.textContent = "Выбрано: " + pending.size;
  }
  const picker = window.createProductPicker(toggle, {
    label: "Пользовательские поля",
    placeholder: "Поиск по названию поля",
    footer,
    onOpen() {
      pending = new Set(rows().map(element => element.dataset.productAttribute));
      pickerError.hidden = true;
      updateCount();
    },
    items: query => [...catalog].filter(([, name]) => name.toLocaleLowerCase().includes(query))
      .map(([id, name]) => {
        const label = document.createElement("label");
        const check = document.createElement("input");
        Object.assign(check, {type: "checkbox", checked: pending.has(id), disabled: applying});
        label.append(check, name);
        check.addEventListener("change", () => {
          if (check.checked) pending.add(id);
          else pending.delete(id);
          updateCount();
        });
        return label;
      }),
  });
  cancel.addEventListener("click", () => picker.close(true));

  function fitText(input) {
    input.style.height = "auto";
    input.style.height = input.scrollHeight + (input.offsetHeight - input.clientHeight) + "px";
  }
  fields.addEventListener("input", event => {
    if (event.target.matches("[data-attribute-text]")) fitText(event.target);
  });
  function fitRows() {
    fields.querySelectorAll("[data-attribute-text]").forEach(fitText);
  }
  fitRows();
  window.addEventListener("resize", fitRows);
  document.fonts?.ready.then(fitRows);

  function setBusy(value) {
    busy = value;
    submit.disabled = value;
    content.inert = value;
  }

  function updateEmpty() {
    empty.hidden = rows().length > 0;
  }

  function valueControls(element) {
    return [...element.querySelectorAll("[data-attribute-value] :is(input, select, textarea)")];
  }

  function removeFromProduct(fieldRow) {
    const marker = document.createElement("input");
    Object.assign(marker, {type: "hidden", name: "remove_attribute", value: fieldRow.dataset.productAttribute});
    fields.append(marker);
    for (const input of valueControls(fieldRow)) input.dispatchEvent(new Event("upload-reset"));
    fieldRow.remove();
    updateEmpty();
  }

  function insertRow(html, previousRow) {
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const replacement = template.content.firstElementChild;
    const id = replacement.dataset.productAttribute;
    fields.querySelector(`[name="remove_attribute"][value="${id}"]`)?.remove();
    previousRow?.remove();
    const order = Number(replacement.dataset.attributeOrder);
    const name = catalog.get(id);
    const next = rows().find(other => {
      const otherOrder = Number(other.dataset.attributeOrder);
      return order < otherOrder || (order === otherOrder && name.localeCompare(catalog.get(other.dataset.productAttribute)) < 0);
    });
    fields.insertBefore(replacement, next || empty);
    window.enhanceStoreSelects?.(replacement);
    window.initManagementUploads?.(replacement);
    updateEmpty();
    return replacement;
  }

  function endpoint(mode, base = fields.dataset.url) {
    const path = new URL(base, location.href);
    path.searchParams.set("editor", mode);
    if (fields.dataset.productId) path.searchParams.set("product", fields.dataset.productId);
    return path;
  }

  async function loadRows(ids) {
    const result = {};
    for (let start = 0; start < ids.length; start += 100) {
      const path = endpoint("rows");
      ids.slice(start, start + 100).forEach(id => path.searchParams.append("field", id));
      const response = await fetch(path);
      if (!response.ok || response.redirected) throw new Error("Не удалось загрузить поля. Попробуйте ещё раз.");
      Object.assign(result, (await response.json()).rows);
    }
    if (ids.some(id => !result[id])) throw new Error("Некоторые поля больше недоступны. Обновите список после сохранения черновика.");
    return result;
  }

  function filled(element) {
    return element.hasAttribute("data-attribute-saved-value") || draftValues(valueControls(element)).length > 0;
  }

  apply.addEventListener("click", async () => {
    if (applying) return;
    const selected = new Set(pending);
    const current = rows();
    const removed = current.filter(element => !selected.has(element.dataset.productAttribute));
    if (removed.some(filled) && !window.confirm("Убрать выбранные поля? Их значения будут удалены из товара при сохранении.")) return;
    const added = [...selected].filter(id => !current.some(element => element.dataset.productAttribute === id));
    applying = true;
    apply.disabled = create.disabled = true;
    picker.render();
    pickerError.hidden = true;
    try {
      const html = await loadRows(added);
      removed.forEach(removeFromProduct);
      added.forEach(id => insertRow(html[id]));
      updateEmpty();
      fitRows();
      fields.dispatchEvent(new Event("change", {bubbles: true}));
      picker.close(true);
    } catch (failure) {
      pickerError.textContent = failure.message;
      pickerError.hidden = false;
    } finally {
      applying = false;
      apply.disabled = create.disabled = false;
      picker.render();
    }
  });

  editor.addEventListener("submit", event => { if (applying) event.preventDefault(); });
  editor.addEventListener("management-draft-restored", async event => {
    const data = event.detail;
    const removed = new Set(data.remove_attribute || []);
    const added = (data.select_attribute || []).filter(id =>
      catalog.has(id) && !removed.has(id) && !rows().some(element => element.dataset.productAttribute === id));
    applying = true;
    toggle.disabled = true;
    try {
      const html = await loadRows(added);
      for (const element of rows()) {
        if (removed.has(element.dataset.productAttribute)) removeFromProduct(element);
      }
      for (const id of added) {
        const replacement = insertRow(html[id]);
        const values = data["field_" + id];
        if (!values) continue;
        for (const input of valueControls(replacement)) {
          if (input.type === "checkbox" || input.type === "radio") {
            input.checked = values.some(entry => entry[0] === input.value && entry[1] === true);
          } else if (input.type !== "file" && values.length) {
            input.value = values[0];
          }
          input.dispatchEvent(new Event("change", {bubbles: true}));
        }
      }
      fitRows();
    } catch (failure) {
      const draftError = editor.querySelector("[data-attribute-draft-error]");
      draftError.textContent = "Не удалось восстановить выбранные поля из черновика. " + failure.message;
      draftError.hidden = false;
    } finally {
      applying = false;
      toggle.disabled = false;
    }
  });

  function draftValues(controls) {
    return controls.flatMap(input => {
      if (input.type === "checkbox" || input.type === "radio") return input.checked ? [input.value] : [];
      if (input.type === "file") return [...input.files].map(file => file.name);
      return input.value ? [input.value] : [];
    });
  }

  function showForm(html) {
    content.innerHTML = html;
    window.enhanceStoreSelects?.(content);
  }

  async function request(options) {
    const response = await fetch(url, options);
    const result = await response.json().catch(() => ({}));
    if (!response.ok && !result.html) {
      throw new Error(result.error || "Не удалось выполнить операцию. Проверьте соединение и сессию.");
    }
    return result;
  }

  document.addEventListener("click", async event => {
    const button = event.target.closest("[data-attribute-new], [data-attribute-edit], [data-attribute-remove]");
    if (!button || dialog.open || applying) return;
    row = button.closest("[data-product-attribute]");
    if (button.hasAttribute("data-attribute-remove")) {
      if (filled(row) && !window.confirm("Убрать поле и его значение из этого товара при сохранении?")) return;
      removeFromProduct(row);
      fields.dispatchEvent(new Event("change", {bubbles: true}));
      toggle.focus();
      return;
    }
    trigger = button;
    error.textContent = "";
    content.replaceChildren();
    dialog.querySelector("h2").textContent = row ? "Редактировать поле" : "Создать поле";
    submit.textContent = row ? "Сохранить изменения" : "Создать и добавить";
    picker.close();
    url = endpoint("product", button.dataset.url);
    setBusy(true);
    dialog.showModal();
    try {
      showForm((await request()).html);
    } catch (failure) {
      error.textContent = failure.message;
      return;
    } finally {
      setBusy(false);
      if (!content.firstElementChild) submit.disabled = true;
    }
    content.querySelector("input:not([type=hidden])")?.focus();
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || submit.disabled) return;
    const data = new FormData(form);
    const controls = row ? valueControls(row) : [];
    const values = draftValues(controls);
    for (const value of values) data.append("draft_value", value);
    setBusy(true);
    error.textContent = "";
    let invalid = false;
    try {
      const result = await request({method: "POST", body: data});
      if (!result.id) {
        showForm(result.html);
        invalid = true;
        return;
      }
      if (result.html) {
        catalog.set(String(result.id), result.name);
        const replacement = insertRow(result.html, row);
        for (const input of valueControls(replacement)) {
          const previous = controls.find(old => old.name === input.name);
          if (!previous) continue;
          if (input.type === "checkbox" || input.type === "radio") {
            input.checked = input.value === "on" ? previous.checked : values.includes(input.value);
          } else if (input.type === "file") {
            if (previous.type === "file") input.files = previous.files;
          } else if (previous.type !== "file") {
            input.value = values[0] ?? "";
          }
        }
        for (const input of valueControls(replacement)) {
          if (input.type === "select-one" || (input.type === "file" && input.files.length)) input.dispatchEvent(new Event("change", {bubbles: true}));
        }
        trigger = replacement.querySelector("[data-attribute-edit]");
      }
      for (const input of controls) input.dispatchEvent(new Event("upload-reset"));
      updateEmpty();
      fitRows();
      fields.dispatchEvent(new Event("change", {bubbles: true}));
      dialog.close();
    } catch (failure) {
      error.textContent = failure.message;
    } finally {
      setBusy(false);
      if (invalid) (content.querySelector('[aria-invalid="true"]:not(.search-select-source)') || submit).focus();
    }
  });

  dialog.addEventListener("cancel", event => { if (busy) event.preventDefault(); });
  form.querySelectorAll("[data-attribute-close]").forEach(button => {
    button.addEventListener("click", () => { if (!busy) dialog.close(); });
  });
  dialog.addEventListener("close", () => {
    (trigger?.isConnected && trigger !== create ? trigger : toggle)?.focus();
    submit.disabled = false;
  });
})();
