(() => {
  const search = document.querySelector("[data-category-search]");
  if (!search) return;
  const template = document.querySelector("[data-category-products-template]");
  const rows = [...document.querySelectorAll("[data-category-id]")];
  const index = new Map(rows.map(row => [row.dataset.categoryId, row]));
  const reloadPanels = new Map();
  const pendingPanels = new Set();
  const key = "category-tree:" + document.body.dataset.managementUser;
  let expanded = new Set();
  try { expanded = new Set(JSON.parse(sessionStorage.getItem(key) || "[]")); } catch {}
  const query = new URLSearchParams(location.search).get("q");
  try { search.value = query ?? sessionStorage.getItem(key + ":search") ?? ""; } catch { search.value = query || ""; }
  function saveTree() {
    const locationURL = new URL(location.href);
    if (locationURL.searchParams.has("q")) {
      if (search.value) locationURL.searchParams.set("q", search.value);
      else locationURL.searchParams.delete("q");
      history.replaceState(history.state, "", locationURL);
    }
    try {
      sessionStorage.setItem(key, JSON.stringify([...expanded]));
      sessionStorage.setItem(key + ":search", search.value);
    } catch {}
  }
  function setAll(open) {
    search.value = "";
    expanded = new Set(open ? rows.filter(row => row.querySelector("[data-category-branch]")).map(row => row.dataset.categoryId) : []);
    saveTree();
    refreshTree();
  }
  document.querySelector("[data-category-expand]").onclick = () => setAll(true);
  document.querySelector("[data-category-collapse]").onclick = () => setAll(false);
  function warnPending(event) {
    event.preventDefault();
    event.returnValue = "";
  }
  function setPending(id, pending) {
    if (pending) pendingPanels.add(id);
    else pendingPanels.delete(id);
    if (pendingPanels.size) window.addEventListener("beforeunload", warnPending);
    else window.removeEventListener("beforeunload", warnPending);
  }

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
        branch.textContent = opened ? "▾" : "▸";
        branch.disabled = Boolean(term);
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
  search.oninput = () => { saveTree(); refreshTree(); };
  search.form.onsubmit = event => event.preventDefault();
  for (const row of rows) {
    const id = row.dataset.categoryId;
    const branch = row.querySelector("[data-category-branch]");
    if (branch) branch.onclick = () => {
      if (expanded.has(id)) expanded.delete(id);
      else expanded.add(id);
      saveTree();
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
      const button = row.querySelector("[data-category-products]");
      button.textContent = count;
      button.setAttribute("aria-label", `Товары категории ${row.dataset.name}: ${count}`);
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
    const add = panel.querySelector("[data-member-add]");
    const help = panel.querySelector("[data-member-help]");
    let adding = false;
    let linkedView = {query: "", page: 1};
    const destination = panel.querySelector("[data-member-destination]");
    destination.querySelector(`option[value="${id}"]`)?.remove();
    const status = panel.querySelector("[data-member-status]");
    const body = panel.querySelector("[data-member-rows]");
    const previous = panel.querySelector("[data-member-prev]");
    const next = panel.querySelector("[data-member-next]");
    const save = panel.querySelector("[data-member-save]");
    const discard = panel.querySelector("[data-member-reset]");
    const changes = new Map();
    let current;
    let page = 1;
    let latest;
    let timer;
    function announce() {
      status.textContent = `Найдено: ${latest.total} · Страница ${latest.page} из ${latest.pages} · Изменений: ${changes.size}`;
      save.disabled = !changes.size;
      discard.hidden = !changes.size;
      setPending(id, Boolean(changes.size));
    }
    function draw() {
      body.replaceChildren();
      previous.disabled = latest.page <= 1;
      next.disabled = latest.page >= latest.pages;
      if (!latest.rows.length) {
        const empty = body.insertRow().insertCell();
        empty.colSpan = 6;
        empty.textContent = search.value.trim() ? "Товары по запросу не найдены." : "В этом списке пока нет товаров.";
      }
      for (const product of latest.rows) {
        const linked = String(product.category) === id;
        const line = body.insertRow();
        const select = document.createElement("input");
        select.type = "checkbox";
        select.checked = changes.has(product.id) ? changes.get(product.id).destination === id : linked;
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
        edit.target = "_blank";
        edit.rel = "noopener";
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
      endpoint.search = new URLSearchParams({mode: adding ? "available" : "linked", q: search.value, page});
      status.textContent = "Загрузка товаров…";
      try {
        const response = await fetch(endpoint, {signal: controller.signal});
        if (!response.ok || response.redirected) throw new Error();
        const result = await response.json();
        if (controller !== current) return;
        latest = result;
        page = latest.page;
        draw();
        return true;
      } catch (error) {
        if (error.name !== "AbortError") status.textContent = "Не удалось загрузить товары.";
      }
    }
    search.oninput = () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 200); };
    search.onkeydown = event => { if (event.key === "Enter") event.preventDefault(); };
    function setMode(value) {
      if (value === adding) return;
      clearTimeout(timer);
      if (value) linkedView = {query: search.value, page};
      adding = value;
      add.setAttribute("aria-pressed", String(adding));
      add.textContent = adding ? "К товарам категории" : "+ Добавить товары";
      help.textContent = adding ? "Отметьте товары для переноса из их текущих категорий." :
        "У товара одна основная категория. Чтобы снять привязку, выберите другую категорию.";
      search.value = adding ? "" : linkedView.query;
      page = adding ? 1 : linkedView.page;
    }
    add.onclick = () => { setMode(!adding); load(); search.focus(); };
    previous.onclick = () => { page--; load(); };
    next.onclick = () => { page++; load(); };
    discard.onclick = () => {
      changes.clear();
      draw();
      load();
    };
    save.onclick = async () => {
      const moves = [...changes.values()].map(move => ({...move, destination: move.destination || destination.value}));
      if (moves.some(move => !move.destination)) {
        status.textContent = "Выберите категорию назначения для снятых товаров.";
        destination.focus();
        return;
      }
      clearTimeout(timer);
      current?.abort();
      panel.inert = true;
      status.textContent = "Сохранение привязок…";
      try {
        const body = new URLSearchParams({csrfmiddlewaretoken: panel.closest("form").elements.csrfmiddlewaretoken.value,
          moves: JSON.stringify(moves)});
        const response = await fetch(url, {method: "POST", body});
        if (response.redirected) throw new Error("Войдите в панель управления повторно.");
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.counts) throw new Error(result.error ||
          (response.status === 403 ? "Обновите страницу и повторите вход в панель." : "Не удалось сохранить изменения."));
        updateCounts(result.counts);
        changes.clear();
        setPending(id, false);
        for (const otherId of Object.keys(result.counts)) {
          if (otherId !== id && !pendingPanels.has(otherId)) reloadPanels.get(otherId)?.();
        }
        setMode(false);
        if (await load()) status.textContent = "Привязки сохранены. " + status.textContent;
        else status.textContent = "Привязки сохранены. Не удалось обновить список.";
      } catch (error) {
        status.textContent = error instanceof TypeError ? "Нет ответа сервера. Проверьте соединение." : error.message;
      } finally {
        panel.inert = false;
      }
    };
    reloadPanels.set(id, load);
    load();
  }
})();
