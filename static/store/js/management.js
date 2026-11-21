function formatRussianPhone(value) {
  let digits = value.replace(/\D/g, "");

  if (digits.startsWith("8")) {
    digits = `7${digits.slice(1)}`;
  }

  if (!digits.startsWith("7")) {
    digits = `7${digits}`;
  }

  digits = digits.slice(0, 11);
  const phone = digits.slice(1);
  let result = "+7";

  if (phone.length > 0) {
    result += ` (${phone.slice(0, 3)}`;
  }

  if (phone.length >= 3) {
    result += ")";
  }

  if (phone.length > 3) {
    result += ` ${phone.slice(3, 6)}`;
  }

  if (phone.length > 6) {
    result += `-${phone.slice(6, 8)}`;
  }

  if (phone.length > 8) {
    result += `-${phone.slice(8, 10)}`;
  }

  return result;
}

document.addEventListener("input", (event) => {
  const phoneInput = event.target.closest(".js-phone-mask");
  const fileInput = event.target.closest(".fancy-file input[type='file']");
  const gallerySelectAll = event.target.closest(".js-select-gallery");

  if (phoneInput) {
    phoneInput.value = formatRussianPhone(phoneInput.value);
  }

  if (fileInput) {
    const fileName = fileInput.closest(".fancy-file").querySelector(".file-name");
    const count = fileInput.files.length;

    if (fileName) {
      fileName.textContent = count ? `Выбрано файлов: ${count}` : "Файлы не выбраны";
    }
  }

  if (gallerySelectAll) {
    document.querySelectorAll('[name="delete_images"]').forEach((checkbox) => {
      checkbox.checked = gallerySelectAll.checked;
    });
  }
});

// Preserve column context when tables stack into mobile records.
document.querySelectorAll('.mgmt-table').forEach(table => {
  const labels = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim());
  table.querySelectorAll('tbody tr').forEach(row => {
    [...row.cells].forEach((cell, index) => {
      if (cell.colSpan === 1 && labels[index]) cell.dataset.label = labels[index];
    });
  });
  table.querySelectorAll('input[type="checkbox"]').forEach(input => {
    if (!input.hasAttribute('aria-label')) input.setAttribute('aria-label', input.closest('thead') ? 'Выбрать все записи' : 'Выбрать запись');
  });
});
document.querySelectorAll('.toolbar input, .toolbar select, .bulk-bar select').forEach(input => {
  if (!input.hasAttribute('aria-label')) input.setAttribute('aria-label', input.placeholder || input.options?.[0]?.text || 'Фильтр');
});
document.querySelectorAll("[data-filter-library]").forEach((library) => {
  const search = library.querySelector("[data-filter-search]");
  const empty = library.querySelector("[data-filter-no-results]");
  const items = [...library.querySelectorAll("[data-filter-name]")];
  search?.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    items.forEach(item => { item.hidden = !item.dataset.filterName.includes(query); });
    empty.hidden = items.some(item => !item.hidden);
  });
});

const categorySettings = document.querySelector("[data-category-settings]");
if (categorySettings) {
  const snapshot = () => JSON.stringify([...new FormData(categorySettings)].map(([name, value]) => [
    name, value instanceof File ? [value.name, value.size, value.lastModified] : value,
  ]));
  const savedSettings = snapshot();
  document.querySelector("[data-category-filters]")?.addEventListener("submit", event => {
    if (snapshot() !== savedSettings && !window.confirm("Изменения категории ещё не сохранены. Продолжить работу с фильтрами?")) {
      event.preventDefault();
      return;
    }
    const message = event.target.dataset.filterConfirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });
}

document.querySelector('[data-add-link]')?.addEventListener('click', () => {
  const total = document.querySelector('#id_links-TOTAL_FORMS');
  const template = document.querySelector('#link-empty-form');
  document.querySelector('[data-link-forms]').insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__prefix__', total.value));
  total.value = String(Number(total.value) + 1);
});
document.querySelectorAll('[data-copy-url]').forEach(button => button.addEventListener('click', async () => {
  const url = new URL(button.dataset.copyUrl, location.origin).href;
  try { await navigator.clipboard.writeText(url); button.textContent = 'Ссылка скопирована'; }
  catch { window.prompt('Скопируйте ссылку', url); }
}));

document.querySelectorAll('.js-customer-price-toggle').forEach(checkbox => {
  const priceInput = checkbox.closest('.customer-price-row')?.querySelector('input[type="number"]');
  const syncPriceInput = () => {
    if (!priceInput) return;
    priceInput.disabled = !checkbox.checked;
    if (checkbox.checked && !priceInput.value) priceInput.focus();
  };
  checkbox.addEventListener('change', syncPriceInput);
});
document.querySelector("[data-select-all]")?.addEventListener("change", (event) => {
  document.querySelectorAll('#order-export-form input[name="ids"]').forEach((input) => {
    input.checked = event.target.checked;
  });
});

const managementShell = document.querySelector(".mgmt-shell");
const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
if (managementShell && sidebarToggle) {
  const savedState = localStorage.getItem("management-sidebar-collapsed") === "1";
  managementShell.classList.toggle("sidebar-collapsed", savedState);
  sidebarToggle.setAttribute("aria-expanded", String(!savedState));
  sidebarToggle.setAttribute("aria-label", savedState ? "Развернуть боковую панель" : "Свернуть боковую панель");
  sidebarToggle.addEventListener("click", () => {
    const collapsed = managementShell.classList.toggle("sidebar-collapsed");
    localStorage.setItem("management-sidebar-collapsed", collapsed ? "1" : "0");
    sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
    sidebarToggle.setAttribute("aria-label", collapsed ? "Развернуть боковую панель" : "Свернуть боковую панель");
  });
}

document.querySelectorAll(".page-editor-tabs").forEach((tabList) => {
  const form = tabList.closest("form");
  const tabs = [...tabList.querySelectorAll("[data-page-tab]")];
  const panels = [...(form || document).querySelectorAll("[data-page-panel]")];
  const activate = (tab) => {
    const target = tab.dataset.pageTab;
    tabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", String(active));
      item.tabIndex = active ? 0 : -1;
    });
    panels.forEach((panel) => {
      const active = panel.dataset.pagePanel === target;
      panel.hidden = !active;
      panel.classList.toggle("active", active);
    });
  };
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].focus();
      activate(tabs[next]);
    });
  });
  const activeTab = tabs.find((tab) => tab.getAttribute("aria-selected") === "true");
  if (activeTab) activate(activeTab);
  const firstError = panels.find((panel) => panel.querySelector(".errorlist"));
  if (firstError) {
    const errorTab = tabs.find((tab) => tab.dataset.pageTab === firstError.dataset.pagePanel);
    if (errorTab) activate(errorTab);
  }
});

document.querySelectorAll("[data-page-editor]").forEach((form) => {
  let dirty = false;
  const markDirty = () => { dirty = true; };
  form.addEventListener("input", markDirty);
  form.addEventListener("change", markDirty);
  form.addEventListener("submit", () => { dirty = false; });
  window.addEventListener("beforeunload", (event) => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  const typeField = form.querySelector('[name="page_type"]');
  const syncPageType = () => {
    if (!typeField || typeField.disabled) return;
    const isCustom = typeField.value === "custom";
    const fixedPage = form.querySelector('[data-page-field="page"]');
    const slugField = form.querySelector('[data-page-field="slug"]');
    if (fixedPage) fixedPage.hidden = isCustom;
    if (slugField) slugField.hidden = !isCustom;
  };
  typeField?.addEventListener("change", syncPageType);
  syncPageType();
});

const pageTree = document.querySelector("[data-page-tree]");
if (pageTree) {
  const search = document.querySelector("[data-page-search]");
  const applyFilter = () => {
    const query = (search?.value || "").trim().toLocaleLowerCase();
    const nodes = [...pageTree.querySelectorAll(".page-tree-node")];
    if (!query) {
      nodes.forEach((node) => { node.hidden = false; });
      return;
    }
    const matches = new Set(nodes.filter((node) => node.querySelector(":scope > .page-tree-row .page-tree-main")?.textContent.toLocaleLowerCase().includes(query)));
    nodes.forEach((node) => {
      let child = node;
      while (child) {
        const parent = child.parentElement.closest(".page-tree-node");
        if (parent) matches.add(parent);
        child = parent;
      }
    });
    nodes.forEach((node) => {
      node.hidden = !matches.has(node);
      if (matches.has(node)) {
        const list = node.querySelector(":scope > .page-tree-list");
        if (list) list.hidden = false;
      }
    });
  };
  search?.addEventListener("input", applyFilter);
  pageTree.querySelectorAll("[data-tree-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const list = button.closest(".page-tree-node")?.querySelector(":scope > .page-tree-list");
      if (!list) return;
      list.hidden = !list.hidden;
      button.setAttribute("aria-expanded", String(!list.hidden));
      button.setAttribute("aria-label", list.hidden ? "Развернуть вложенные страницы" : "Свернуть вложенные страницы");
    });
  });
  document.querySelector("[data-page-tree-toggle]")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const expand = button.getAttribute("aria-expanded") !== "true";
    pageTree.querySelectorAll(":scope > .page-tree-list .page-tree-list").forEach((list) => {
      list.hidden = !expand;
    });
    pageTree.querySelectorAll(".page-tree-toggle").forEach((toggle) => {
      toggle.setAttribute("aria-expanded", String(expand));
      toggle.setAttribute("aria-label", expand ? "Свернуть вложенные страницы" : "Развернуть вложенные страницы");
    });
    button.setAttribute("aria-expanded", String(expand));
    button.textContent = expand ? "Свернуть дерево" : "Развернуть дерево";
  });

  applyFilter();
}

(() => {
  document.querySelectorAll("[data-category-image]").forEach(component => {
    const mediaField = component.querySelector('[name="image_media"]');
    const fileInput = component.querySelector('input[type="file"]');
    const imageUrl = component.querySelector('[name="image_url"]');
    const preview = component.querySelector("[data-category-image-preview]");
    const status = component.querySelector("[data-category-image-status]");
    const removeButton = component.querySelector("[data-category-image-remove]");
    const removeInput = component.querySelector('[name="remove_image"]');
    const sources = component.querySelector(".category-image-sources");
    const summary = component.querySelector("[data-category-image-change]");
    const library = component.querySelector("[data-category-image-library]");
    const original = preview.querySelector("img")?.cloneNode();
    let objectUrl = null;

    const showPreview = (url, alt = "Изображение категории") => {
      const image = document.createElement(url ? "img" : "span");
      if (url) {
        image.className = "current-image-preview";
        image.src = url;
        image.alt = alt;
        image.addEventListener("error", () => {
          if (image.parentNode !== preview) return;
          showPreview("");
          removeButton.hidden = false;
          status.textContent = "Не удалось показать миниатюру. Проверьте изображение или выберите другое.";
        }, {once: true});
      } else {
        image.textContent = "Изображение не выбрано";
      }
      preview.replaceChildren(image);
      removeButton.hidden = !url;
      summary.textContent = url ? "Изменить" : "Выбрать изображение";
    };

    const discardFilePreview = () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    };

    function selectImage(item) {
      mediaField.value = String(item.id);
      discardFilePreview();
      fileInput.value = "";
      imageUrl.value = "";
      removeInput.value = "";
      showPreview(item.url, item.alt || item.title);
      status.textContent = "Изображение из медиатеки выбрано. Сохраните категорию.";
      sources.open = false;
      summary.focus();
    }
    library.addEventListener("click", () => window.openManagementMediaPicker(library, {
      kind: "image", multiple: false, onSelect: ([item]) => selectImage(item),
    }));
    fileInput.addEventListener("change", () => {
      if (!fileInput.files[0]) return;
      discardFilePreview();
      mediaField.value = "";
      imageUrl.value = "";
      removeInput.value = "";
      objectUrl = URL.createObjectURL(fileInput.files[0]);
      showPreview(objectUrl, "Предпросмотр загруженного изображения");
      status.textContent = "Файл выбран. Сохраните категорию.";
      sources.open = false;
      summary.focus();
    });
    imageUrl.addEventListener("change", () => {
      const url = imageUrl.value.trim();
      if (!/^https?:\/\//i.test(url)) {
        if (url) status.textContent = "Введите полный адрес изображения, начиная с http:// или https://.";
        else if (!fileInput.files.length && !mediaField.value) {
          if (removeInput.value !== "1" && original) showPreview(original.src, original.alt);
          else showPreview("");
        }
        return;
      }
      discardFilePreview();
      fileInput.value = "";
      mediaField.value = "";
      removeInput.value = "";
      showPreview(url);
      status.textContent = "Ссылка указана. Сохраните категорию.";
    });
    removeButton.addEventListener("click", () => {
      if (!window.confirm("Убрать изображение у этой категории?")) return;
      discardFilePreview();
      fileInput.value = "";
      mediaField.value = "";
      imageUrl.value = "";
      removeInput.value = "1";
      showPreview("");
      status.textContent = "Изображение будет убрано после сохранения категории.";
      summary.focus();
    });
  });

  document.querySelectorAll(".fancy-file input[type='file']").forEach((input) => {
    input.addEventListener("change", () => {
      if (!input.files[0]) return;
      const preview = input.closest(".image-field")?.querySelector("[data-current-preview]");
      if (!preview) return;
      preview.innerHTML = `<img class="current-image-preview" src="${URL.createObjectURL(input.files[0])}" alt="Предпросмотр">`;
    });
  });
})();
