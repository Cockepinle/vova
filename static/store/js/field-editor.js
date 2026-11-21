(() => {
  const form = document.querySelector("[data-field-editor]");
  if (!form) return;

  const fields = form.elements;
  const typeHelp = form.querySelector("[data-field-type-help]");
  const choiceSettings = form.querySelector("[data-field-options]");
  const filterSettings = fields.filter_type.closest("label");
  const preview = form.querySelector("[data-field-preview]");
  const previewContent = form.querySelector("[data-field-preview-content]");
  const examples = {
    text: "Произвольный текст, например описание материала.",
    integer: "Число без дробной части, например количество штук.",
    decimal: "Число с дробной частью, например вес.",
    price: "Числовое значение цены. Подходит для дополнительной характеристики.",
    boolean: "Флажок для ответов «Да» и «Нет».",
    date: "Календарная дата, например дата производства.",
    choice: "В форме товара значения выбираются из готового списка.",
    image: "Загрузка изображения для характеристики товара.",
    file: "Загрузка документа или другого файла, например инструкции.",
    url: "Полный адрес страницы, например ссылка на инструкцию.",
  };

  function input(type) {
    const control = document.createElement("input");
    control.type = type;
    control.disabled = true;
    return control;
  }

  function renderPreview(type) {
    const title = document.createElement("strong");
    title.textContent = fields.name.value.trim() || "Название поля";
    if (fields.is_required.checked && type !== "boolean") title.textContent += " *";
    const fallback = fields.default_value.value.trim();
    let control;
    if (type === "choice") {
      const options = [...new Set(fields.choices_text.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean))];
      if (fields.filter_type.value === "multiple") {
        control = document.createElement("div");
        options.forEach(value => {
          const label = document.createElement("label");
          label.className = "catalog-config-toggle";
          const checkbox = input("checkbox");
          checkbox.checked = value === fallback;
          label.append(checkbox, document.createTextNode(value));
          control.append(label);
        });
        if (!options.length) control.textContent = "Добавьте варианты списка.";
      } else {
        control = document.createElement("select");
        control.disabled = true;
        control.add(new Option("Не выбрано", ""));
        options.forEach(value => control.add(new Option(value, value)));
        if (options.includes(fallback)) control.value = fallback;
      }
    } else if (type === "text") {
      control = document.createElement("textarea");
      control.rows = 2;
      control.disabled = true;
      control.value = fallback;
    } else {
      const nativeTypes = {
        integer: "number", decimal: "number", price: "number", boolean: "checkbox",
        date: "date", image: "file", file: "file", url: "url",
      };
      control = input(nativeTypes[type] || "text");
      if (control.type !== "file" && control.type !== "checkbox") control.value = fallback;
      if (control.type === "checkbox") control.checked = Boolean(fallback);
    }

    const unit = document.createElement("small");
    unit.textContent = fields.unit.value.trim();
    previewContent.replaceChildren(title, control, unit);
  }

  function refresh(event) {
    const type = fields.value_type.value;
    const isChoice = type === "choice";
    typeHelp.textContent = examples[type] || "";
    typeHelp.hidden = !typeHelp.textContent;
    choiceSettings.hidden = !isChoice && !choiceSettings.querySelector(".errorlist");
    filterSettings.hidden = !fields.is_filterable.checked && !isChoice && !filterSettings.querySelector(".errorlist");

    const mode = fields.filter_type;
    const allowsRange = ["integer", "decimal", "price"].includes(type);
    if (event?.target === fields.value_type && (
      (mode.value === "multiple" && !isChoice) || (mode.value === "range" && !allowsRange)
    )) mode.value = "single";
    mode.querySelector('[value="multiple"]').disabled = !isChoice && mode.value !== "multiple";
    mode.querySelector('[value="range"]').disabled = !allowsRange && mode.value !== "range";

    preview.hidden = false;
    renderPreview(type);
  }

  form.addEventListener("input", refresh);
  form.addEventListener("change", refresh);
  refresh();
})();
