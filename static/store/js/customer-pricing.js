(() => {
  const pricing = document.querySelector("[data-customer-pricing]");
  if (pricing) {
    const level = pricing.querySelector('[name="price_level"]');
    const highlight = () => {
      pricing.querySelectorAll("[data-customer-coefficient]").forEach(label => {
        label.classList.toggle("is-current", label.dataset.customerCoefficient === level.value + "_coefficient");
      });
    };
    level.addEventListener("change", highlight);
    highlight();
  }

  const section = document.querySelector("[data-customer-products]");
  if (!section) return;
  const input = section.querySelector("[data-product-search]");
  const results = section.querySelector("[data-product-results]");
  const rows = section.querySelector("[data-product-price-rows]");
  const template = section.querySelector("[data-product-price-template]");
  const status = section.querySelector("[data-product-status]");
  const empty = section.querySelector("[data-product-empty]");
  let timer;
  let request;

  function selectProduct(product) {
    let row = rows.querySelector('[data-product-id="' + product.id + '"]');
    if (!row) {
      row = template.content.firstElementChild.cloneNode(true);
      row.dataset.productId = product.id;
      row.querySelector("[data-product-name]").textContent = product.name;
      row.querySelector("[data-product-sku]").textContent = product.sku || "";
      row.querySelector("[data-product-level]").textContent = product.level_price + " ₽";
      row.querySelector("input").name = "individual_price_" + product.id;
      rows.append(row);
    }
    empty.hidden = true;
    results.replaceChildren();
    input.value = "";
    status.textContent = "Укажите индивидуальную цену для товара «" + product.name + "» и сохраните карточку.";
    row.querySelector("input").focus();
  }

  function showResults(items) {
    results.replaceChildren(...items.map(product => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "customer-product-option";
      const name = document.createElement("strong");
      name.textContent = product.name;
      const details = document.createElement("small");
      details.textContent = (product.sku ? product.sku + " · " : "") + product.level_price + " ₽";
      option.append(name, details);
      option.addEventListener("click", () => selectProduct(product));
      return option;
    }));
    status.textContent = items.length ? "" : "Товары не найдены.";
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    request?.abort();
    const query = input.value.trim();
    results.replaceChildren();
    if (query.length < 2) {
      status.textContent = query ? "Введите ещё хотя бы один символ." : "";
      return;
    }
    timer = setTimeout(async () => {
      const current = request = new AbortController();
      status.textContent = "Ищем товары…";
      const url = new URL(section.dataset.productSearchUrl, document.baseURI);
      url.searchParams.set("q", query);
      try {
        const response = await fetch(url, {signal: current.signal});
        if (!response.ok) throw new Error();
        const {items} = await response.json();
        if (!current.signal.aborted) showResults(items);
      } catch {
        if (!current.signal.aborted) status.textContent = "Поиск недоступен. Повторите попытку.";
      }
    }, 220);
  });

  input.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === "ArrowDown") {
      event.preventDefault();
      results.querySelector("button")?.focus();
    } else if (event.key === "Escape") {
      clearTimeout(timer);
      request?.abort();
      results.replaceChildren();
      status.textContent = "";
    }
  });

  rows.addEventListener("click", event => {
    const button = event.target.closest("[data-product-remove]");
    if (!button) return;
    const row = button.closest("[data-product-id]");
    const amount = row.querySelector("input");
    amount.value = "";
    amount.focus();
    status.textContent = "Сохраните карточку, чтобы вернуть для товара цену по уровню.";
  });
})();
