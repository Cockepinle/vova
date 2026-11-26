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
  const input = form.elements.file;
  const title = form.elements.title;
  input.multiple = true;
  title.required = false;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submit.disabled) return;
    const data = new FormData(form);
    const files = [...input.files];
    const failed = new DataTransfer();
    const errors = [];
    data.set("library", "1");
    submit.disabled = true;
    form.inert = true;
    status.textContent = "Загрузка файла…";
    try {
      for (const file of files) {
        data.set("file", file);
        data.set("title", files.length === 1 && title.value.trim() ? title.value.trim() : file.name.slice(0, 160));
        try {
          const item = await window.uploadManagementMedia(data, data.get("csrfmiddlewaretoken"));
          list.insertAdjacentHTML("afterbegin", item.html);
          window.initManagementUploads(list.firstElementChild);
        } catch (error) {
          failed.items.add(file);
          errors.push(file.name + " — " + error.message);
        }
      }
      const uploaded = files.length - failed.files.length;
      if (uploaded) search.value = "";
      filter();
      if (!failed.files.length) form.reset();
      else {
        input.files = failed.files;
        input.dispatchEvent(new Event("change", {bubbles: true}));
      }
      status.textContent = [uploaded ? `Загружено: ${uploaded} из ${files.length}.` : "", ...errors].filter(Boolean).join("\n");
    } finally {
      submit.disabled = false;
      form.inert = false;
    }
  });
  window.addEventListener("pageshow", () => { submit.disabled = false; status.textContent = ""; });
})();
