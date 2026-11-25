(() => {
  const panel = document.querySelector("[data-product-pricing]");
  if (!panel) return;

  const form = panel.closest("form");
  const baseInput = form.elements.namedItem("cost_price");
  const manualInput = form.elements.namedItem("price");
  const retailLabel = panel.querySelector("[data-retail-price-label]");
  const buyer = panel.querySelector("[data-price-buyer]");
  const levels = [...panel.querySelectorAll("[data-price-level]")].map(row => ({
    key: row.dataset.priceLevel,
    input: form.elements.namedItem(row.dataset.priceLevel + "_coefficient"),
    amount: row.querySelector("[data-level-amount]"),
    formula: row.querySelector("[data-level-formula]"),
  }));
  const maxPrice = 999999999999n;
  const coefficientScale = 10000n;
  let manualValue = manualInput.value;
  let calculatedRetail = false;

  // null is an empty field; undefined means that the current input is invalid.
  function parse(value, places, integerDigits) {
    const text = value.trim();
    if (!text) return null;
    const parts = text.match(/^([+-]?)([0-9]*)(?:[.,]([0-9]*))?$/);
    if (!parts || (!parts[2] && !parts[3])) return undefined;
    const integer = parts[2].replace(/^0+/, "");
    const fraction = parts[3] || "";
    if (integer.length > integerDigits || fraction.length > places) return undefined;
    const amount = BigInt((integer || "0") + fraction.padEnd(places, "0"));
    return parts[1] === "-" && amount ? undefined : amount;
  }

  function format(amount, places, decimal = ",") {
    const text = amount.toString().padStart(places + 1, "0");
    return text.slice(0, -places) + decimal + text.slice(-places);
  }

  function multiply(base, coefficient) {
    const amount = (base * coefficient + coefficientScale / 2n) / coefficientScale;
    return amount <= maxPrice ? amount : undefined;
  }

  function calculate(base, coefficient, fallback, source) {
    if (coefficient === undefined) return {amount: undefined, formula: "Проверьте коэффициент"};
    if (coefficient === null) return fallback;
    if (base == null) return {amount: undefined, formula: "Укажите базовую цену"};
    const amount = multiply(base, coefficient);
    return amount === undefined
      ? {amount, formula: "Превышен предел цены"}
      : {amount, formula: format(base, 2) + " ₽ × " + format(coefficient, 4).replace(/0+$/, "").replace(/,$/, "") + " · " + source};
  }

  function draw(amount, formula, result) {
    amount.textContent = result.amount == null ? "—" : format(result.amount, 2) + " ₽";
    formula.textContent = result.formula;
  }

  function refresh() {
    const base = parse(baseInput.value, 2, 10);
    const coefficients = Object.fromEntries(levels.map(row => [row.key, parse(row.input.value, 4, 6)]));
    if (!calculatedRetail) manualValue = manualInput.value;
    const manual = {amount: parse(manualValue, 2, 10), formula: "Ручная розничная цена"};
    const nominal = {};
    nominal.retail = calculate(base, coefficients.retail, manual, "коэффициент товара");
    calculatedRetail = coefficients.retail != null && base != null && nominal.retail.amount != null;
    manualInput.readOnly = calculatedRetail;
    if (retailLabel) retailLabel.textContent = calculatedRetail ? "Розничная цена (рассчитана)" : "Ручная розничная цена";
    manualInput.value = calculatedRetail ? format(nominal.retail.amount, 2, ".") : manualValue;

    const retailFallback = {amount: nominal.retail.amount, formula: "По розничной цене товара"};
    for (const row of levels) {
      if (row.key !== "retail") {
        nominal[row.key] = calculate(base, coefficients[row.key], retailFallback, "коэффициент товара");
      }
      draw(row.amount, row.formula, nominal[row.key]);
    }

    const selected = buyer.selectedOptions[0];
    const individual = parse(selected.dataset.individual || "", 2, 10);
    const personalCoefficient = parse(selected.dataset.coefficient || "", 4, 6);
    const fallback = nominal[selected.dataset.level] || nominal.retail;
    const result = individual != null
      ? {amount: individual, formula: "Сохранённая индивидуальная цена"}
      : base === null ? fallback : calculate(base, personalCoefficient, fallback, "коэффициент клиента");
    draw(panel.querySelector("[data-buyer-amount]"), panel.querySelector("[data-buyer-formula]"), result);
  }

  panel.addEventListener("input", refresh);
  buyer.addEventListener("change", refresh);
  form.addEventListener("management-draft-restored", () => {
    manualValue = manualInput.value;
    refresh();
  });
  refresh();
})();
