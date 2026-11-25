(() => {
  const search = document.querySelector("[data-category-search]");
  if (!search) return;
  const template = document.querySelector("[data-category-products-template]");
  const rows = [...document.querySelectorAll("[data-category-id]")];
  const index = new Map(rows.map(row => [row.dataset.categoryId, row]));
  const reloadPanels = new Map();
  const key = "category-tree:" + document.body.dataset.managementUser;
  let expanded = new Set();
  try { expanded = new Set(JSON.parse(sessionStorage.getItem(key) || "[]")); } catch {}
  const query = new URLSearchParams(location.search).get("q");
  if (query) search.value = query;

  function refreshTree() {
    const term = search.value.trim().toLocaleLowerCase();
    const matches = new Set();
    const ancestors = new Set();
    if (term) for (const row of rows) {
      if (!row.dataset.name.toLocaleLowerCase().includes(term)) continue;
      matches.add(row.dataset.categoryId);
      for (let parent = row.dataset.parent; parent; parent = index.get(parent)?.dataset.parent) ancestors.add(parent);
    }
    for (const row of rows) {
      const {categoryId, parent} = row.dataset;
      const branch = row.querySelector("[data-category-branch]");
      const opened = term ? ancestors.has(categoryId) : expanded.has(categoryId);
      row.hidden = term ? !matches.has(categoryId) && !ancestors.has(categoryId)
        : Boolean(parent && (!expanded.has(parent) || index.get(parent)?.hidden));
      if (branch) {
        branch.setAttribute("aria-expanded", String(opened));
        branch.textContent = opened ? "−" : "+";
      }
      row.nextElementSibling.hidden = row.hidden ||
        row.querySelector("[data-category-products]").getAttribute("aria-expanded") !== "true";
    }
    document.querySelector("[data-category-no-results]").hidden = !term || matches.size > 0;
  }
  const bulk = document.querySelector("form[data-category-bulk]");
  const originalStatuses = new Map([...bulk.querySelectorAll(".status-select")].map(select => [select, select.value]));
  bulk.addEventListener("formdata", event => {
    const payload = event.formData;
    payload.delete("category_ids");
    for (const [select, initial] of originalStatuses) {
      if (select.value !== initial) payload.append("category_ids", select.name.slice("status_".length));
      else payload.delete(select.name);
    }
  });
  search.oninput = refreshTree;
  search.form.onsubmit = event => event.preventDefault();
  for (const row of rows) {
    const id = row.dataset.categoryId;
    const branch = row.querySelector("[data-category-branch]");
    if (branch) branch.onclick = () => {
      if (search.value.trim()) search.value = "";
      if (expanded.has(id)) expanded.delete(id);
      else expanded.add(id);
      try { sessionStorage.setItem(key, JSON.stringify([...expanded])); } catch {}
      refreshTree();
    };
    const count = row.querySelector("[data-category-products]");
    count.onclick = () => {
      const opening = count.getAttribute("aria-expanded") !== "true";
      count.setAttribute("aria-expanded", String(opening));
      refreshTree();
      const cell = row.nextElementSibling.cells[0];
      if (opening) {
        if (cell.firstElementChild) reloadPanels.get(id)?.();
        else initialize(cell, count.dataset.url, id);
      }
    };
  }
  refreshTree();

  function updateCounts(counts) {
    for (const [id, count] of Object.entries(counts)) {
      const row = index.get(id);
      if (!row) continue;
      row.dataset.direct = count;
      row.querySelector("[data-category-products]").textContent = count;
    }
    const descendants = new Map();
    for (const row of [...rows].reverse()) {
      const total = descendants.get(row.dataset.categoryId) || 0;
      const output = row.querySelector("[data-category-descendants]");
      if (output) output.textContent = total;
      const parent = row.dataset.parent;
      descendants.set(parent, (descendants.get(parent) || 0) + total + Number(row.dataset.direct));
    }
  }
  function initialize(cell, url, id) {
    cell.append(template.content.cloneNode(true));
    const panel = cell.firstElementChild;
    const search = panel.querySelector("[data-member-search]");
    const mode = panel.querySelector("[data-member-mode]");
    const destination = panel.querySelector("[data-member-destination]");
    destination.querySelector(`option[value="${id}"]`)?.remove();
    const status = panel.querySelector("[data-member-status]");
    const body = panel.querySelector("[data-member-rows]");
    const previous = panel.querySelector("[data-member-prev]");
    const next = panel.querySelector("[data-member-next]");
    const save = panel.querySelector("[data-member-save]");
    const changes = new Map();
    let current;
    let page = 1;
    let latest;
    let timer;
    function announce() {
      status.textContent = `Найдено: ${latest.total} · Страница ${latest.page} из ${latest.pages} · Изменений: ${changes.size}`;
      save.disabled = !changes.size;
    }
    function draw() {
      body.replaceChildren();
      previous.disabled = latest.page <= 1;
      next.disabled = latest.page >= latest.pages;
      for (const product of latest.rows) {
        const linked = String(product.category) === id;
        const line = body.insertRow();
        const select = document.createElement("input");
        select.type = "checkbox";
        select.checked = changes.has(product.id) ? !linked : linked;
        select.setAttribute("aria-label", "Привязка: " + product.name);
        select.onchange = () => {
          if (select.checked === linked) changes.delete(product.id);
          else changes.set(product.id, {id: product.id, source: product.category, destination: linked ? null : id});
          announce();
        };
        const name = document.createElement("span");
        name.className = "category-member-name";
        const image = document.createElement("img");
        image.alt = "";
        image.loading = "lazy";
        image.src = product.image || document.body.dataset.missingImage;
        window.setManagementImageFallback(image);
        name.append(image, product.name);
        if (!linked) {
          const source = document.createElement("small");
          source.textContent = product.category_name;
          name.append(source);
        }
        const edit = document.createElement("a");
        edit.href = product.url;
        edit.className = "ghost-button";
        edit.textContent = "Изменить";
        for (const [label, value] of [["Привязка", select], ["Товар", name], ["Артикул", product.sku || "—"],
          ["Статус", product.status], ["Цена", product.price + " ₽"], ["Действия", edit]]) {
          const td = line.insertCell();
          td.dataset.label = label;
          td.append(value);
        }
      }
      announce();
    }
    async function load() {
      current?.abort();
      const controller = current = new AbortController();
      const endpoint = new URL(url, location.href);
      endpoint.search = new URLSearchParams({mode: mode.value, q: search.value, page});
      status.textContent = "Загрузка товаров…";
      try {
        const response = await fetch(endpoint, {signal: controller.signal});
        if (!response.ok || response.redirected) throw new Error();
        const result = await response.json();
        if (controller !== current) return;
        latest = result;
        page = latest.page;
        draw();
      } catch (error) {
        if (error.name !== "AbortError") status.textContent = "Не удалось загрузить товары.";
      }
    }
    search.oninput = () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 200); };
    search.onkeydown = event => { if (event.key === "Enter") event.preventDefault(); };
    mode.onchange = () => { page = 1; load(); };
    previous.onclick = () => { page--; load(); };
    next.onclick = () => { page++; load(); };
    save.onclick = async () => {
      const moves = [...changes.values()].map(move => ({...move, destination: move.destination || destination.value}));
      if (moves.some(move => !move.destination)) {
        status.textContent = "Выберите категорию назначения для снятых товаров.";
        destination.focus();
        return;
      }
      panel.inert = true;
      try {
        const body = new URLSearchParams({csrfmiddlewaretoken: panel.closest("form").elements.csrfmiddlewaretoken.value,
          moves: JSON.stringify(moves)});
        const response = await fetch(url, {method: "POST", body});
        if (response.redirected) throw new Error("Войдите в панель управления повторно.");
        const result = await response.json();
        if (!response.ok) throw new Error(result.error);
        updateCounts(result.counts);
        changes.clear();
        await load();
      } catch (error) {
        status.textContent = error.message || "Не удалось сохранить изменения.";
      } finally {
        panel.inert = false;
      }
    };
    reloadPanels.set(id, load);
    load();
  }
})();
