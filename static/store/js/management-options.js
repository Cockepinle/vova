(() => {
  window.initManagementOptions = (scope = document) => {
    for (const root of scope.querySelectorAll("[data-management-options]")) {
      if (root.dataset.optionsReady) continue;
      root.dataset.optionsReady = "1";
      const search = root.querySelector("[data-options-search]");
      const selected = root.querySelector("[data-options-selected]");
      const count = root.querySelector("[data-options-count]");
      const chips = root.querySelector("[data-options-chips]");
      const empty = root.querySelector("[data-options-empty]");
      const rows = [...root.querySelectorAll("[data-option]")].map(row => ({
        row, check: row.querySelector('input[type="checkbox"]'),
        title: row.querySelector("[data-option-title]").textContent,
        text: (row.dataset.optionSearch || row.textContent).toLocaleLowerCase(),
      }));
      function render() {
        const query = search.value.trim().toLocaleLowerCase();
        let visible = 0;
        const buttons = [];
        for (const {row, check, title, text} of rows) {
          row.hidden = (selected.checked && !check.checked) || !text.includes(query);
          if (!row.hidden) visible++;
          if (!check.checked) continue;
          const button = document.createElement("button");
          button.type = "button";
          button.className = "ghost-button";
          button.textContent = title + " ×";
          button.setAttribute("aria-label", "Убрать " + title);
          button.onclick = () => { search.focus(); check.click(); };
          buttons.push(button);
        }
        chips.replaceChildren(...buttons);
        chips.hidden = !buttons.length;
        count.textContent = `Найдено: ${visible} · Выбрано: ${buttons.length}`;
        empty.hidden = visible > 0;
      }
      root.querySelector("[data-options-toolbar]").hidden = count.hidden = false;
      root.addEventListener("change", render);
      search.addEventListener("input", render);
      search.addEventListener("keydown", event => { if (event.key === "Enter") event.preventDefault(); });
      render();
    }
  };
  window.initManagementOptions();
})();
