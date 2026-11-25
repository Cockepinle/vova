(() => {
  const form = document.querySelector("[data-product-editor]");
  const name = form.elements.namedItem("name");
  const slug = form.elements.namedItem("slug");
  const isPublished = form.dataset.published === "1";
  const autoSlug = document.createElement("input");
  Object.assign(autoSlug, {type: "hidden", name: "auto_slug"});
  form.append(autoSlug);
  const cyrillic = [..."абвгдеёжзийклмнопрстуфхцчшщъыьэюя"];
  const latin = "a b v g d e yo zh z i y k l m n o p r s t u f kh ts ch sh shch _ y _ e yu ya".split(" ");
  const transliteration = new Map(cyrillic.map((letter, index) => [letter, latin[index]]));
  function updateSeo(field) {
    const title = name.value.trim();
    field.value = field === slug
      ? (title ? [...title.toLowerCase()].map(letter => transliteration.get(letter) ?? letter).join("")
          .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, field.maxLength).replace(/-$/g, "") || "product" : "")
      : title.slice(0, field.maxLength);
  }
  for (const button of form.querySelectorAll("[data-seo-reset]")) {
    const field = form.elements.namedItem(button.dataset.seoReset);
    const mode = document.createElement("input");
    Object.assign(mode, {type: "hidden", name: "draft_seo_" + field.name});
    form.append(mode);
    let automatic = !field.value && !(field === slug && isPublished);
    const refresh = () => {
      if (automatic) updateSeo(field);
      mode.value = automatic ? "auto" : "manual";
      if (field === slug) autoSlug.value = automatic ? "1" : "";
    };
    form.addEventListener("management-draft-restored", () => {
      if (mode.value) automatic = mode.value === "auto";
    });
    name.addEventListener("input", refresh);
    field.addEventListener("input", () => {
      automatic = false;
      refresh();
    });
    button.addEventListener("click", () => {
      automatic = true;
      refresh();
      field.focus();
    });
  }

  function snapshot(includeCustomerPrices = true) {
    return JSON.stringify([...new FormData(form)].map(([key, value]) => [
      key, value instanceof File ? [value.name, value.size, value.lastModified] : value,
    ]).filter(([key]) => key !== "auto_slug" && (
      includeCustomerPrices || (key !== "price_customers" && !key.startsWith("customer_price_"))
    )));
  }
  const initial = snapshot();
  const initialProduct = snapshot(false);
  let submitting = false;
  function warn(event) {
    if (!submitting && form.dataset.draftReloading !== "1" && (form.dataset.bound === "1" || snapshot() !== initial)) {
      event.preventDefault();
      event.returnValue = "";
    }
  }
  function trackChanges() {
    window.removeEventListener("beforeunload", warn);
    if (form.dataset.bound === "1" || snapshot() !== initial) {
      window.addEventListener("beforeunload", warn);
    }
  }
  form.addEventListener("input", trackChanges);
  form.addEventListener("change", trackChanges);
  window.addEventListener("pageshow", () => { submitting = false; trackChanges(); });
  trackChanges();
  form.addEventListener("submit", (event) => {
    if (event.submitter?.name === "save_customer_prices") {
      submitting = !event.defaultPrevented && form.dataset.bound !== "1" && snapshot(false) === initialProduct;
      return;
    }
    if (isPublished && slug.value && slug.value !== form.dataset.originalSlug &&
        !window.confirm("Изменить адрес товара? Ссылки со старым адресом перестанут работать.")) {
      event.preventDefault();
      return;
    }
    submitting = !event.defaultPrevented;
  });

  const dialog = document.querySelector("[data-variant-dialog]");
  const open = form.querySelector("[data-open-variant]");
  const group = form.elements.namedItem("variant_group");
  const dialogGroup = dialog.querySelector("[data-dialog-group]");
  const create = dialog.querySelector("[data-new-variant]");
  const reload = dialog.querySelector("[data-load-variant]");
  const close = dialog.querySelector("[data-close-variant]");
  const content = dialog.querySelector("[data-variant-content]");
  const status = dialog.querySelector("[data-variant-status]");
  let busy = false;

  function announce(message, error = false) {
    status.textContent = message;
    status.hidden = !message;
    status.classList.toggle("error", error);
  }
  function syncGroups(value) {
    dialogGroup.replaceChildren(new Option("Новая группа", ""), ...[...group.options]
      .filter(option => option.value).map(option => new Option(option.text, option.value)));
    dialogGroup.value = value;
  }
  function showForm(html) {
    content.innerHTML = html;
    window.initVariantGroup(content);
    window.enhanceStoreSelects?.(content);
  }
  async function request(url, body) {
    if (busy) return;
    busy = true;
    dialogGroup.disabled = create.disabled = reload.disabled = close.disabled = true;
    dialog.setAttribute("aria-busy", "true");
    const submit = content.querySelector('[type="submit"]');
    if (submit) submit.disabled = true;
    announce(body ? "Сохранение группы…" : "Загрузка группы…");
    try {
      const response = await fetch(url, {
        method: body ? "POST" : "GET",
        headers: {"X-Variant-Dialog": "1"},
        body,
      });
      if (response.redirected || response.status === 403) {
        throw new Error("Сессия истекла или доступ закрыт. Войдите в панель управления повторно.");
      }
      if (response.status === 422) {
        showForm(await response.text());
        announce("Проверьте отмеченные поля.", true);
      } else if (!response.ok) {
        throw new Error(response.status === 404 ? "Группа больше недоступна." : "Сервер не смог обработать запрос к группе.");
      } else if (body) {
        const saved = await response.json();
        const key = String(saved.id);
        const option = [...group.options].find(item => item.value === key);
        if (option) option.text = saved.name;
        else group.add(new Option(saved.name, key));
        const productId = Number(form.dataset.productId);
        if (saved.removed.includes(productId) && group.value === key) group.value = "";
        if (saved.members.includes(productId) && !group.value) group.value = key;
        if (saved.created) {
          group.value = key;
          form.elements.namedItem("new_variant_group").value = "";
        }
        group.dispatchEvent(new Event("change", {bubbles: true}));
        syncGroups(key);
        content.replaceChildren();
        announce("Группа сохранена. Можно закрыть окно или выбрать группу для редактирования.");
      } else {
        showForm(await response.text());
        const draftName = form.elements.namedItem("new_variant_group").value;
        if (!dialogGroup.value && draftName) content.querySelector('[name="name"]').value = draftName;
        announce("");
      }
    } catch (error) {
      announce(error instanceof TypeError ? "Не удалось подключиться к серверу. Попробуйте снова." : error.message, true);
    } finally {
      busy = false;
      dialogGroup.disabled = create.disabled = reload.disabled = close.disabled = false;
      if (submit) submit.disabled = false;
      dialog.removeAttribute("aria-busy");
    }
  }
  function loadGroup() {
    if (busy) return;
    content.replaceChildren();
    request(dialogGroup.value
      ? dialog.dataset.editUrl.replace("/0/edit/", "/" + dialogGroup.value + "/edit/")
      : dialog.dataset.newUrl);
  }
  open.addEventListener("click", () => {
    syncGroups(group.value);
    dialog.showModal();
    loadGroup();
  });
  close.addEventListener("click", () => {
    if (!busy) dialog.close();
  });
  dialog.addEventListener("cancel", event => { if (busy) event.preventDefault(); });
  dialog.addEventListener("close", () => open.focus());
  dialogGroup.addEventListener("change", loadGroup);
  reload.addEventListener("click", loadGroup);
  create.addEventListener("click", () => {
    dialogGroup.value = "";
    loadGroup();
  });
  content.addEventListener("submit", event => {
    event.preventDefault();
    request(event.target.action, new FormData(event.target));
  });
})();
