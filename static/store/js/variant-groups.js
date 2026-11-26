window.initVariantGroup = (root) => {
  const parameterRows = root.querySelector("[data-parameter-rows]");
  const parameterTemplate = root.querySelector("[data-parameter-empty-form]");
  const addParameterButton = root.querySelector("[data-add-parameter]");
  const totalForms = root.querySelector("#id_parameters-TOTAL_FORMS");

  addParameterButton?.addEventListener("click", () => {
    if (!parameterRows || !parameterTemplate || !totalForms) {
      return;
    }

    const index = Number(totalForms.value);
    const maxForms = Number(root.querySelector("#id_parameters-MAX_NUM_FORMS").value);
    if (index >= maxForms) return;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = parameterTemplate.innerHTML.replaceAll("__prefix__", String(index));
    const row = wrapper.firstElementChild;
    parameterRows.append(row);
    totalForms.value = String(index + 1);
    addParameterButton.disabled = index + 1 >= maxForms;
    row.querySelector("input").focus();
  });

  for (const order of root.querySelectorAll(".variant-order-input input")) {
    const check = order.closest("[data-option]").querySelector('input[type="checkbox"]');
    const sync = () => { order.disabled = !check.checked; };
    check.addEventListener("change", sync);
    sync();
  }
  window.initManagementOptions(root);
};
window.initVariantGroup(document);
