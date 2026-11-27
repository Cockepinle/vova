(() => {
  const form = document.querySelector("[data-product-editor]");
  const name = form.elements.namedItem("name");
  const slug = form.elements.namedItem("slug");
  const isPublished = form.dataset.published === "1";
  const autoSlug = document.createElement("input");
  Object.assign(autoSlug, {type: "hidden", name: "auto_slug"});
  form.append(autoSlug);
  const transliteration = JSON.parse(document.getElementById("product-slug-transliteration").textContent);
  const seoModes = JSON.parse(document.getElementById("product-seo-modes").textContent);
  function updateSeo(field) {
    const title = name.value.trim();
    field.value = field === slug
      ? (title ? [...title.toLowerCase()].map(letter => transliteration[letter.codePointAt(0)] ?? letter).join("")
          .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, field.maxLength).replace(/-$/g, "") || "product" : "")
      : title.slice(0, field.maxLength);
  }
  for (const button of form.querySelectorAll("[data-seo-reset]")) {
    const field = form.elements.namedItem(button.dataset.seoReset);
    const mode = document.createElement("input");
    Object.assign(mode, {type: "hidden", name: "draft_seo_" + field.name});
    form.append(mode);
    let automatic = seoModes[field.name] === "auto" ||
      (seoModes[field.name] !== "manual" && !field.value && !(field === slug && isPublished));
    const refresh = () => {
      if (automatic) updateSeo(field);
      mode.value = automatic ? "auto" : "manual";
      if (field === slug) autoSlug.value = automatic ? "1" : "";
    };
    form.addEventListener("management-draft-restored", () => {
      if (mode.value) automatic = mode.value === "auto";
      if (field === slug) autoSlug.value = automatic ? "1" : "";
    });
    name.addEventListener("input", refresh);
    field.addEventListener("input", () => {
      automatic = false;
      refresh();
    });
    button.addEventListener("click", () => {
      automatic = true;
      refresh();
      field.dispatchEvent(new Event("change", {bubbles: true}));
      field.focus();
    });
    if (form.dataset.bound !== "1") refresh();
    else {
      mode.value = automatic ? "auto" : "manual";
      if (field === slug) autoSlug.value = automatic ? "1" : "";
    }
  }

  form.addEventListener("submit", (event) => {
    if (isPublished && slug.value && slug.value !== form.dataset.originalSlug &&
        !window.confirm("Изменить адрес товара? Ссылки со старым адресом перестанут работать.")) {
      event.preventDefault();
    }
  });

  const dialog = document.querySelector("[data-variant-dialog]");
  const open = form.querySelector("[data-open-variant]");
  const group = form.elements.namedItem("variant_group");
  const productOrder = form.elements.namedItem("variant_sort_order");
  let savedOrder = productOrder.value;
  const dialogGroup = dialog.querySelector("[data-dialog-group]");
  const create = dialog.querySelector("[data-new-variant]");
  const reload = dialog.querySelector("[data-load-variant]");
  const search = dialog.querySelector("[data-variant-search]");
  const use = dialog.querySelector("[data-use-variant]");
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
    const query = search.value.trim().toLocaleLowerCase();
    dialogGroup.replaceChildren(new Option("Новая группа", ""), ...[...group.options]
      .filter(option => option.value && option.text.toLocaleLowerCase().includes(query))
      .map(option => new Option(option.text, option.value)));
    if ([...dialogGroup.options].some(option => option.value === value)) dialogGroup.value = value;
    use.disabled = busy || !dialogGroup.value;
  }
  function showForm(html) {
    content.innerHTML = html;
    window.initVariantGroup(content);
    window.enhanceStoreSelects?.(content);
  }
  async function request(url, body) {
    if (busy) return;
    busy = true;
    dialogGroup.disabled = create.disabled = reload.disabled = close.disabled = use.disabled = search.disabled = true;
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
        if (Object.hasOwn(saved.orders || {}, productId)) {
          const nextOrder = String(saved.orders[productId]);
          if (productOrder.value === savedOrder) productOrder.value = nextOrder;
          savedOrder = nextOrder;
        }
        if (saved.removed.includes(productId) && group.value === key) group.value = "";
        if (saved.members.includes(productId) && !group.value) group.value = key;
        if (saved.created) {
          group.value = key;
          form.elements.namedItem("new_variant_group").value = "";
        }
        group.dispatchEvent(new Event("change", {bubbles: true}));
        search.value = "";
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
      dialogGroup.disabled = create.disabled = reload.disabled = close.disabled = search.disabled = false;
      use.disabled = !dialogGroup.value;
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
    search.value = "";
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
  search.addEventListener("keydown", event => { if (event.key === "Enter") event.preventDefault(); });
  search.addEventListener("input", () => {
    const previous = dialogGroup.value;
    syncGroups(previous);
    if (dialogGroup.value !== previous) content.replaceChildren();
  });
  use.addEventListener("click", () => {
    group.value = dialogGroup.value;
    form.elements.namedItem("new_variant_group").value = "";
    group.dispatchEvent(new Event("change", {bubbles: true}));
    dialog.close();
  });
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

(() => {
  const picker = document.querySelector("[data-product-promotions]");
  if (!picker) return;
  const search = picker.querySelector("[data-product-promotion-search]");
  const rows = [...picker.querySelectorAll("[data-product-promotion]")];
  const empty = picker.querySelector("[data-product-promotion-empty]");
  search.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase("ru");
    for (const row of rows) {
      row.hidden = !row.querySelector("[data-promotion-title]").textContent.toLocaleLowerCase("ru").includes(query);
    }
    empty.hidden = !rows.length || rows.some(row => !row.hidden);
  });
  search.addEventListener("keydown", event => {
    if (event.key === "Enter") event.preventDefault();
  });
})();
