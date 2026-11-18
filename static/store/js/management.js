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
  const status = pageTree.querySelector("[data-page-tree-status]");
  let draggedNode = null;
  const directNodes = (list) => [...list.children].filter((child) => child.matches(".page-tree-node"));
  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("is-error", isError);
  };
  const saveTree = async () => {
    const items = [...pageTree.querySelectorAll(".page-tree-node")].map((node) => {
      const list = node.parentElement;
      const siblings = directNodes(list);
      return {
        id: Number(node.dataset.pageId),
        parent_id: list.dataset.parentId ? Number(list.dataset.parentId) : null,
        order: siblings.indexOf(node),
      };
    });
    try {
      const response = await fetch(pageTree.dataset.reorderUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.cookie.split("; ").find((cookie) => cookie.startsWith("csrftoken="))?.split("=")[1] || "",
        },
        body: JSON.stringify({ items }),
      });
      if (!response.ok) throw new Error(await response.text() || "Не удалось сохранить порядок страниц.");
      setStatus("Порядок и вложенность сохранены.");
    } catch (error) {
      setStatus(error.message || "Не удалось сохранить порядок страниц.", true);
    }
  };
  const applyFilter = () => {
    const query = (search?.value || "").trim().toLocaleLowerCase();
    const nodes = [...pageTree.querySelectorAll(".page-tree-node")];
    if (!query) {
      nodes.forEach((node) => { node.hidden = false; });
      return;
    }
    const matches = new Set(nodes.filter((node) => node.textContent.toLocaleLowerCase().includes(query)));
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

  pageTree.querySelectorAll(".page-tree-grip").forEach((grip) => {
    grip.addEventListener("dragstart", (event) => {
      if (search?.value.trim()) {
        event.preventDefault();
        setStatus("Очистите поиск перед изменением порядка.", true);
        return;
      }
      draggedNode = grip.closest(".page-tree-node");
      draggedNode?.classList.add("dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", draggedNode?.dataset.pageId || "");
    });
    grip.addEventListener("dragend", () => {
      draggedNode?.classList.remove("dragging");
      pageTree.querySelectorAll(".drop-before,.drop-after,.drop-inside").forEach((node) => {
        node.classList.remove("drop-before", "drop-after", "drop-inside");
      });
    });
  });
  pageTree.addEventListener("dragover", (event) => {
    if (!draggedNode) return;
    const row = event.target.closest(".page-tree-row");
    const list = event.target.closest(".page-tree-list");
    if (!row && !list) return;
    event.preventDefault();
    if (row) {
      const target = row.closest(".page-tree-node");
      if (!target || target === draggedNode || draggedNode.contains(target)) return;
      target.classList.remove("drop-before", "drop-after", "drop-inside");
      const fraction = (event.clientY - row.getBoundingClientRect().top) / row.offsetHeight;
      target.classList.add(fraction < .25 ? "drop-before" : fraction > .75 ? "drop-after" : "drop-inside");
    }
  });
  pageTree.addEventListener("drop", async (event) => {
    if (!draggedNode) return;
    const row = event.target.closest(".page-tree-row");
    const targetList = event.target.closest(".page-tree-list");
    event.preventDefault();
    if (row) {
      const target = row.closest(".page-tree-node");
      if (!target || target === draggedNode || draggedNode.contains(target)) return;
      const fraction = (event.clientY - row.getBoundingClientRect().top) / row.offsetHeight;
      if (fraction < .25 || fraction > .75) {
        const siblings = target.parentElement;
        siblings.insertBefore(draggedNode, fraction < .25 ? target : target.nextSibling);
      } else {
        let children = target.querySelector(":scope > .page-tree-list");
        if (!children) {
          children = document.createElement("ul");
          children.className = "page-tree-list";
          children.dataset.parentId = target.dataset.pageId;
          target.append(children);
          const toggle = target.querySelector(":scope > .page-tree-row [data-tree-toggle]");
          if (toggle) {
            toggle.hidden = false;
            toggle.disabled = false;
          }
        }
        children.hidden = false;
        children.append(draggedNode);
      }
    } else if (targetList && !draggedNode.contains(targetList)) {
      targetList.append(draggedNode);
    }
    draggedNode.classList.remove("dragging");
    pageTree.querySelectorAll(".drop-before,.drop-after,.drop-inside").forEach((node) => {
      node.classList.remove("drop-before", "drop-after", "drop-inside");
    });
    draggedNode = null;
    await saveTree();
  });
}
