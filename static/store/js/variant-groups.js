const parameterRows = document.querySelector("[data-parameter-rows]");
const parameterTemplate = document.querySelector("[data-parameter-empty-form]");
const addParameterButton = document.querySelector("[data-add-parameter]");
const totalForms = document.querySelector("#id_parameters-TOTAL_FORMS");

addParameterButton?.addEventListener("click", () => {
  if (!parameterRows || !parameterTemplate || !totalForms) {
    return;
  }

  const index = Number(totalForms.value);
  const maxForms = Number(document.querySelector("#id_parameters-MAX_NUM_FORMS").value);
  if (index >= maxForms) return;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = parameterTemplate.innerHTML.replaceAll("__prefix__", String(index));
  const row = wrapper.firstElementChild;
  parameterRows.append(row);
  totalForms.value = String(index + 1);
  addParameterButton.disabled = index + 1 >= maxForms;
  row.querySelector("input").focus();
});

const productSearch = document.querySelector("[data-product-search]");
const productOptions = [...document.querySelectorAll("[data-product-option]")];
const selection = document.querySelector("[data-variant-selection]");
const noResults = document.querySelector("[data-variant-no-results]");

if (productSearch) {
  function updateSelection() {
    selection.textContent = "Выбрано товаров: " + productOptions.filter(option => option.querySelector("input").checked).length;
  }
  productSearch.addEventListener("input", () => {
    const query = productSearch.value.trim().toLocaleLowerCase();
    productOptions.forEach(option => {
      option.hidden = !option.querySelector("label").textContent.toLocaleLowerCase().includes(query);
    });
    noResults.hidden = !query || productOptions.length === 0 || productOptions.some(option => !option.hidden);
  });
  productOptions.forEach(option => option.addEventListener("change", updateSelection));
  updateSelection();
}
