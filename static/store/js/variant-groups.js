const parameterRows = document.querySelector("[data-parameter-rows]");
const parameterTemplate = document.querySelector("[data-parameter-empty-form]");
const addParameterButton = document.querySelector("[data-add-parameter]");
const totalForms = document.querySelector("#id_parameters-TOTAL_FORMS");

addParameterButton?.addEventListener("click", () => {
  if (!parameterRows || !parameterTemplate || !totalForms) {
    return;
  }

  const index = Number(totalForms.value);
  const wrapper = document.createElement("div");
  wrapper.innerHTML = parameterTemplate.innerHTML.replaceAll("__prefix__", String(index));
  parameterRows.append(wrapper.firstElementChild);
  totalForms.value = String(index + 1);
});

document.querySelector("[data-product-search]")?.addEventListener("input", (event) => {
  const query = event.target.value.trim().toLocaleLowerCase();
  document.querySelectorAll("[data-product-option]").forEach((option) => {
    option.hidden = !option.textContent.toLocaleLowerCase().includes(query);
  });
});
