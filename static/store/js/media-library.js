(() => {
  const search = document.querySelector("[data-library-search]");
  const rows = [...document.querySelectorAll("[data-library-item]")];
  const empty = document.querySelector("[data-library-no-results]");
  search.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    for (const row of rows) {
      const title = row.querySelector("[data-library-title]").textContent;
      row.hidden = ![title, row.dataset.fileName.split("/").at(-1)]
        .some(value => value.toLocaleLowerCase().includes(query));
    }
    empty.hidden = !query || rows.some(row => !row.hidden);
  });
  const form = document.querySelector("[data-library-upload]");
  const submit = form.querySelector('[type="submit"]');
  const status = form.querySelector("[data-library-status]");
  form.addEventListener("submit", event => {
    if (submit.disabled) event.preventDefault();
    else {
      submit.disabled = true;
      status.textContent = "Загрузка файла…";
    }
  });
  window.addEventListener("pageshow", () => { submit.disabled = false; status.textContent = ""; });
})();
