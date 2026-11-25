(() => {
  const panel = document.querySelector("[data-customer-prices]");
  if (!panel) return;
  const form = panel.closest("form");
  const search = panel.querySelector("[data-buyer-search]");
  const level = panel.querySelector("[data-buyer-level]");
  const priced = panel.querySelector("[data-buyer-priced]");
  const selected = panel.querySelector("[data-buyer-selected]");
  const status = panel.querySelector("[data-buyer-status]");
  const body = panel.querySelector("[data-buyer-rows]");
  const save = panel.querySelector("[data-buyer-save]");
  const draft = panel.querySelector("[data-buyer-edits]");
  const previous = panel.querySelector('[data-buyer-step="-1"]');
  const next = panel.querySelector('[data-buyer-step="1"]');
  const preview = form.querySelector("[data-price-buyer]");
  const levels = new Map([...level.options].map(option => [option.value, option.text]));
  let edits = {};
  let data;
  let page = 1;
  let controller;
  let timer;

  function restore() {
    try { edits = JSON.parse(draft.value || "{}"); }
    catch { edits = {}; }
    load();
  }
  function announce() {
    if (!data) return;
    const total = data.selected + Object.values(edits).reduce((count, entry) =>
      count + Number(entry.value !== null) - Number(entry.original !== null), 0);
    status.textContent = `Найдено: ${data.total} · Выбрано: ${total} · Страница ${data.page} из ${data.pages}`;
  }
  function change(row, value) {
    if (value === row.price) delete edits[row.id];
    else edits[row.id] = {value, original: row.price};
    draft.value = JSON.stringify(edits);
    draft.dispatchEvent(new Event("change", {bubbles: true}));
    save.disabled = !Object.keys(edits).length;
    announce();
  }
  function render() {
    body.replaceChildren();
    previous.disabled = data.page <= 1;
    next.disabled = data.page >= data.pages;
    save.disabled = !Object.keys(edits).length;
    preview.replaceChildren(preview.options[0], ...data.rows.map(row => {
      const option = new Option(row.name, row.id);
      Object.assign(option.dataset, {level: row.level, individual: row.price ?? "", coefficient: row.coefficient ?? ""});
      return option;
    }));
    preview.dispatchEvent(new Event("change"));
    for (const row of data.rows) {
      const current = edits[row.id] ? edits[row.id].value : row.price;
      const line = body.insertRow();
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = current !== null;
      check.setAttribute("aria-label", "Выбрать " + row.name);
      const price = document.createElement("input");
      price.inputMode = "decimal";
      price.value = current ?? "";
      price.disabled = !check.checked;
      price.setAttribute("aria-label", "Цена для " + row.name);
      check.onchange = () => {
        price.disabled = !check.checked;
        change(row, check.checked ? price.value : null);
        if (check.checked) price.focus();
      };
      price.oninput = () => change(row, price.value);
      const cells = [["Выбор", check], ["Покупатель", row.company ? row.name + " · " + row.company : row.name],
        ["Электронная почта", row.email], ["Уровень цен", levels.get(row.level)], ["Индивидуальная цена", price]];
      for (const [label, value] of cells) {
        const cell = line.insertCell();
        cell.dataset.label = label;
        cell.append(value ?? "—");
      }
    }
    announce();
  }
  async function load() {
    controller?.abort();
    const current = controller = new AbortController();
    const url = new URL(panel.dataset.url, location.href);
    url.search = new URLSearchParams({q: search.value, level: level.value, priced: +priced.checked,
      selected: +selected.checked, page, selection: Object.entries(edits).map(([id, entry]) =>
        (entry.value === null ? "-" : "+") + id).join(",")});
    status.textContent = "Загрузка покупателей…";
    try {
      const response = await fetch(url, {signal: current.signal});
      if (!response.ok || response.redirected) throw new Error();
      const result = await response.json();
      if (controller !== current) return;
      data = result;
      page = data.page;
      render();
    } catch (error) {
      if (error.name !== "AbortError") status.textContent = "Не удалось загрузить покупателей. Повторите поиск.";
    }
  }
  search.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { page = 1; load(); }, 200);
  });
  search.addEventListener("keydown", event => { if (event.key === "Enter") event.preventDefault(); });
  for (const filter of [level, priced, selected]) filter.onchange = () => { page = 1; load(); };
  previous.onclick = () => { page--; load(); };
  next.onclick = () => { page++; load(); };
  save.onclick = async () => {
    panel.inert = true;
    try {
      const body = new URLSearchParams({csrfmiddlewaretoken: form.elements.csrfmiddlewaretoken.value,
        edits: JSON.stringify(Object.fromEntries(Object.entries(edits).map(([key, item]) => [key, item.value])))});
      const response = await fetch(panel.dataset.url, {method: "POST", body});
      const result = await response.json();
      if (!response.ok || !result.saved) throw new Error(result.error || "Не удалось сохранить цены.");
      edits = {};
      draft.value = "";
      draft.dispatchEvent(new Event("change", {bubbles: true}));
      await load();
    } catch (error) {
      status.textContent = error instanceof SyntaxError ? "Не удалось сохранить цены. Проверьте вход в панель." : error.message;
    } finally {
      panel.inert = false;
    }
  };
  form.addEventListener("management-draft-restored", restore);
  restore();
})();
