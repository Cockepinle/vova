(() => {
  const fields = document.querySelector("[data-product-attributes]");
  const dialog = document.querySelector("[data-attribute-dialog]");
  if (!fields || !dialog) return;
  const form = dialog.querySelector("form");
  const content = form.querySelector("[data-attribute-content]");
  const error = form.querySelector("[data-attribute-error]");
  const submit = form.querySelector("[type=submit]");
  let row, url, trigger, busy = false;

  function setBusy(value) {
    busy = value;
    submit.disabled = value;
    content.inert = value;
  }

  function updateEmpty() {
    fields.querySelector("[data-attributes-empty]").hidden = Boolean(fields.querySelector("[data-product-attribute]"));
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
    marker.dispatchEvent(new Event("change", {bubbles: true}));
  }

  fields.closest("form").addEventListener("management-draft-restored", event => {
    const removed = new Set(event.detail.remove_attribute || []);
    for (const fieldRow of fields.querySelectorAll("[data-product-attribute]")) {
      if (removed.has(fieldRow.dataset.productAttribute)) removeFromProduct(fieldRow);
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
    if (!button || dialog.open) return;
    trigger = button;
    row = button.closest("[data-product-attribute]");
    error.textContent = "";
    content.replaceChildren();
    const removing = button.hasAttribute("data-attribute-remove");
    dialog.querySelector("h2").textContent = removing ? "Убрать поле из товара" : row ? "Редактировать поле" : "Добавить поле";
    submit.textContent = removing ? "Убрать из товара" : row ? "Сохранить изменения" : "Создать и добавить";
    if (removing) {
      url = null;
      content.textContent = "Поле и его значение будут убраны из этой карточки при сохранении товара. Остальные карточки сохранят свои значения.";
      dialog.showModal();
      return;
    }
    url = new URL(button.dataset.url, location.href);
    url.searchParams.set("editor", "product");
    if (fields.dataset.productId) url.searchParams.set("product", fields.dataset.productId);
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
    if (!url) {
      removeFromProduct(row);
      dialog.close();
      return;
    }
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
        const template = document.createElement("template");
        template.innerHTML = result.html.trim();
        const replacement = template.content.firstElementChild;
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
        const order = Number(replacement.dataset.attributeOrder);
        const name = replacement.querySelector(".product-attribute-title > span").textContent;
        const next = [...fields.querySelectorAll("[data-product-attribute]")].find(other => {
          if (other === row) return false;
          const otherOrder = Number(other.dataset.attributeOrder);
          const otherName = other.querySelector(".product-attribute-title > span").textContent;
          return order < otherOrder || (order === otherOrder && name.localeCompare(otherName) < 0);
        });
        row?.remove();
        fields.insertBefore(replacement, next || fields.querySelector("[data-attributes-empty]"));
        window.enhanceStoreSelects?.(replacement);
        window.initManagementUploads?.(replacement);
        for (const input of valueControls(replacement)) {
          if (input.type === "file" && input.files.length) input.dispatchEvent(new Event("change", {bubbles: true}));
        }
        trigger = replacement.querySelector("[data-attribute-edit]");
      } else if (row) {
        row.remove();
      }
      for (const input of controls) input.dispatchEvent(new Event("upload-reset"));
      updateEmpty();
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
    (trigger?.isConnected ? trigger : document.querySelector("[data-attribute-new]"))?.focus();
    submit.disabled = false;
  });
})();
