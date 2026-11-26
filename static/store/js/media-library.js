(() => {
  const search = document.querySelector("[data-library-search]");
  const list = document.querySelector(".media-list");
  const empty = document.querySelector("[data-library-no-results]");
  function filter() {
    const query = search.value.trim().toLocaleLowerCase();
    const rows = [...list.querySelectorAll("[data-library-item]")];
    for (const row of rows) {
      const title = row.querySelector("[data-library-title]").textContent;
      row.hidden = ![title, row.dataset.fileName.split("/").at(-1)]
        .some(value => value.toLocaleLowerCase().includes(query));
    }
    empty.hidden = rows.some(row => !row.hidden);
  }
  search.addEventListener("input", filter);
  const form = document.querySelector("[data-library-upload]");
  const submit = form.querySelector('[type="submit"]');
  const status = form.querySelector("[data-library-status]");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submit.disabled) return;
    const data = new FormData(form);
    data.set("library", "1");
    submit.disabled = true;
    form.inert = true;
    status.textContent = "Загрузка файла…";
    try {
      const item = await window.uploadManagementMedia(data, data.get("csrfmiddlewaretoken"));
      if (!item.html) throw new Error("Файл сохранён. Обновите страницу, чтобы увидеть его в медиатеке.");
      list.insertAdjacentHTML("afterbegin", item.html);
      window.initManagementUploads(list.firstElementChild);
      form.reset();
      search.value = "";
      filter();
      status.textContent = "Файл загружен в медиатеку.";
    } catch (error) {
      status.textContent = error.message;
    } finally {
      submit.disabled = false;
      form.inert = false;
    }
  });
  window.addEventListener("pageshow", () => { submit.disabled = false; status.textContent = ""; });
})();
