(() => {
  const picker = document.querySelector("[data-media-picker]");
  if (!picker) return;
  const grid = picker.querySelector("[data-media-picker-grid]");
  const upload = picker.querySelector("[data-media-picker-upload]");
  const pending = picker.querySelector("[data-media-picker-pending]");
  const send = picker.querySelector("[data-media-picker-send]");
  const search = picker.querySelector("[data-media-picker-search]");
  const apply = picker.querySelector("[data-media-picker-apply]");
  const count = picker.querySelector("[data-media-picker-selection]");
  const status = picker.querySelector("[data-media-picker-status]");
  const closeButton = picker.querySelector("button[data-media-picker-close]");
  const workspace = document.querySelector(".mgmt-shell");
  let session = null;
  let queued = [];
  let scrollPosition;

  function setVisible(visible) {
    picker.hidden = !visible;
    if (workspace) workspace.inert = visible;
    const body = document.body;
    if (visible && !scrollPosition) {
      scrollPosition = {x: window.scrollX, y: window.scrollY};
      body.style.setProperty("--management-scroll-top", `${-scrollPosition.y}px`);
      body.style.setProperty("--management-scroll-right", `${window.innerWidth - document.documentElement.clientWidth}px`);
      body.classList.add("management-modal-open");
    } else if (!visible && scrollPosition) {
      body.classList.remove("management-modal-open");
      window.scrollTo({left: scrollPosition.x, top: scrollPosition.y, behavior: "instant"});
      scrollPosition = null;
    }
  }

  function close() {
    if (session?.uploading) return;
    const trigger = session?.trigger;
    queued = [];
    send.textContent = "Загрузить";
    session = null;
    setVisible(false);
    pending.hidden = true;
    upload.value = "";
    upload.dispatchEvent(new Event("upload-reset"));
    trigger?.focus({preventScroll: true});
  }

  function announce(message = "", error = false) {
    status.textContent = message;
    status.classList.toggle("error", error);
  }

  function updateSelection() {
    count.hidden = !session.multiple;
    count.textContent = "Выбрано: " + session.selected.size;
    apply.hidden = !session.multiple;
    apply.disabled = session.uploading || (!session.selected.size && (!session.allowEmpty || session.loading));
  }

  function finish(selection) {
    const callback = session.onSelect;
    session.uploading = false;
    close();
    callback(selection);
  }

  function render() {
    const query = search.value.trim().toLocaleLowerCase();
    const items = [...session.items.values()].filter(item => [item.title, item.filename].some(value => value?.toLocaleLowerCase().includes(query)));
    grid.replaceChildren();
    if (!items.length && !session.loading) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = query ? "По вашему запросу ничего не найдено." : "Подходящих файлов пока нет.";
      grid.append(empty);
    }
    items.forEach(item => {
      const key = String(item.id);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "media-picker-item";
      if (item.type === "image" && item.url) {
        const image = document.createElement("img");
        window.setManagementImageFallback(image);
        image.src = item.url;
        image.alt = "";
        image.loading = "lazy";
        button.append(image);
      } else {
        const icon = document.createElement("span");
        icon.className = "media-picker-file-icon";
        icon.textContent = item.type === "video" ? "Видео" : "Файл";
        button.append(icon);
      }
      const title = document.createElement("span");
      title.textContent = item.title;
      button.append(title);
      if (session.exclude.has(key)) {
        button.disabled = true;
        const note = document.createElement("span");
        note.textContent = "Уже добавлено";
        button.append(note);
      }
      if (session.multiple) button.setAttribute("aria-pressed", String(session.selected.has(key)));
      button.addEventListener("click", () => {
        if (session.uploading) return;
        if (!session.multiple) {
          finish([item]);
          return;
        }
        if (session.selected.has(key)) session.selected.delete(key);
        else session.selected.set(key, item);
        button.setAttribute("aria-pressed", String(session.selected.has(key)));
        updateSelection();
      });
      grid.append(button);
    });
  }

  async function open(trigger, options) {
    const current = session = {
      trigger, ...options, loading: true, uploading: false,
      selected: new Map((options.selected || []).map(item => [String(item.id), item])),
      exclude: new Set(options.exclude || []), items: new Map(),
    };
    setVisible(true);
    grid.replaceChildren();
    search.value = "";
    upload.multiple = current.multiple;
    const policy = JSON.parse(document.getElementById("upload-policy-" + current.kind).textContent);
    upload.dispatchEvent(new CustomEvent("upload-policy", {detail: policy}));
    updateSelection();
    closeButton.focus();
    announce("Загрузка медиатеки…");
    try {
      const url = new URL(document.body.dataset.mediaApi, document.baseURI);
      url.searchParams.set("kind", current.kind);
      const response = await fetch(url);
      if (response.redirected) throw new Error("Срок действия сессии истёк. Войдите в систему повторно");
      if (!response.ok) throw new Error("Не удалось загрузить медиатеку.");
      const {items} = await response.json();
      if (session !== current) return;
      items.forEach(item => current.items.set(String(item.id), item));
      announce();
    } catch (error) {
      if (session === current) announce(error instanceof TypeError ? "Не удалось подключиться к серверу. Попробуйте снова." : error.message, true);
    } finally {
      current.loading = false;
      if (session === current) {
        render();
        updateSelection();
      }
    }
  }
  window.openManagementMediaPicker = open;

  apply.addEventListener("click", () => finish([...session.selected.values()]));
  search.addEventListener("input", () => { if (session) render(); });
  picker.querySelectorAll("[data-media-picker-close]").forEach(button => button.addEventListener("click", close));
  picker.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "Tab") {
      const controls = [...picker.querySelectorAll("button:enabled, input:enabled")].filter(el => el.getClientRects().length);
      const first = controls[0];
      const last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  });

  upload.addEventListener("change", () => { queued = []; pending.hidden = true; });
  upload.addEventListener("image-upload-ready", () => {
    queued = [...upload.files];
    send.textContent = "Загрузить";
    pending.hidden = !session;
    announce();
  });
  send.addEventListener("click", async () => {
    if (!session || session.uploading || !queued.length) return;
    const current = session;
    const files = queued;
    queued = [];
    const csrf = picker.querySelector('[name="csrfmiddlewaretoken"]').value;
    current.uploading = true;
    upload.disabled = true;
    send.disabled = true;
    updateSelection();
    const failures = [];
    try {
      for (const [index, file] of files.entries()) {
        if (session !== current) return;
        announce("Загрузка " + (index + 1) + " из " + files.length + "…");
        const data = new FormData();
        data.set("title", file.name.replace(/\.[^.]+$/, "").slice(0, 160));
        data.set("file", file);
        data.set("kind", current.kind);
        try {
          const item = await window.uploadManagementMedia(data, csrf);
          if (session !== current) return;
          current.items.set(String(item.id), item);
          if (current.multiple) current.selected.set(String(item.id), item);
        } catch (error) {
          queued.push(file);
          failures.push(file.name + " — " + (error instanceof TypeError
            ? "Не удалось подключиться к серверу. Попробуйте повторить загрузку" : error.message));
        }
      }
      if (session !== current) return;
      if (failures.length < files.length) search.value = "";
      render();
      announce(failures.length ? failures.join(" · ") : current.multiple
        ? "Файлы загружены и отмечены для выбора." : "Файл загружен. Нажмите на его миниатюру для выбора.", failures.length > 0);
    } finally {
      current.uploading = false;
      upload.disabled = false;
      send.disabled = false;
      pending.hidden = !queued.length;
      send.textContent = queued.length ? "Повторить загрузку" : "Загрузить";
      if (!queued.length) {
        upload.value = "";
        upload.dispatchEvent(new Event("upload-reset"));
      }
      if (session === current) updateSelection();
    }
  });

  document.querySelectorAll("select[data-media-field]").forEach(select => {
    const label = select.closest("label");
    if (!label) return;
    const fieldName = label.firstChild?.textContent.trim() || label.querySelector("span")?.textContent.trim() || "Файл";
    const legacy = label.matches("[data-content-image]") ? label : null;
    const removeLegacy = legacy?.querySelector('input[type="hidden"]');
    const directUpload = legacy && document.getElementById(legacy.dataset.directUpload);
    const wrapper = document.createElement("div");
    wrapper.className = "media-picker-control";
    const controls = document.createElement("div");
    controls.className = "media-picker-field-actions";
    const choose = document.createElement("button");
    choose.type = "button";
    choose.className = "ghost-button";
    choose.textContent = "Выбрать из медиатеки";
    choose.setAttribute("aria-label", fieldName + " — выбрать из медиатеки");
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "ghost-button";
    clear.textContent = "Убрать выбор";
    const previews = document.createElement("div");
    previews.className = "media-picker-field-previews";
    const readSelected = () => [...select.selectedOptions].filter(option => option.value).map(option => ({
      id: option.value, title: option.textContent, alt: option.dataset.alt, url: option.dataset.url, type: option.dataset.type,
    }));
    const refresh = () => {
      const selected = readSelected();
      if (!selected.length && !directUpload?.files.length && legacy?.dataset.fallbackUrl && removeLegacy?.value !== "1") {
        selected.push({url: legacy.dataset.fallbackUrl, type: "image", title: "Текущее изображение"});
      }
      previews.replaceChildren(...selected.map(item => {
        const tile = document.createElement("div");
        if (item.url && item.type === "image") {
          const image = document.createElement("img");
          window.setManagementImageFallback(image);
          image.src = item.url;
          image.alt = "";
          tile.append(image);
        }
        const title = document.createElement("span");
        title.textContent = item.title;
        tile.append(title);
        return tile;
      }));
      clear.hidden = !selected.length || select.required;
    };
    const changeSelection = items => {
      if (directUpload) {
        directUpload.value = "";
        directUpload.dispatchEvent(new Event("upload-reset"));
      }
      if (removeLegacy) removeLegacy.value = items.length ? "" : "1";
      const byId = new Map(items.map(item => [String(item.id), item]));
      items.forEach(item => {
        const value = String(item.id);
        const option = [...select.options].find(entry => entry.value === value) || new Option(item.title, value);
        option.dataset.url = item.url || "";
        option.dataset.alt = item.alt || "";
        option.dataset.type = item.type || "";
        if (!option.parentNode) select.add(option);
      });
      if (select.multiple) [...select.options].forEach(option => { option.selected = byId.has(option.value); });
      else select.value = items.length ? String(items[0].id) : "";
      select.dispatchEvent(new Event("change", {bubbles: true}));
    };
    choose.addEventListener("click", () => open(choose, {
      kind: select.dataset.mediaField, multiple: select.multiple, allowEmpty: !select.required,
      selected: readSelected(), onSelect: changeSelection,
    }));
    clear.addEventListener("click", () => { changeSelection([]); choose.focus(); });
    select.addEventListener("change", refresh);
    select.addEventListener("media-picker-sync", refresh);
    directUpload?.addEventListener("image-upload-ready", () => {
      removeLegacy.value = "";
      select.value = "";
      select.dispatchEvent(new Event("change", {bubbles: true}));
    });
    select.classList.add("media-picker-select");
    if (legacy) {
      choose.textContent = "Выбрать или загрузить";
      choose.setAttribute("aria-label", fieldName + " — выбрать или загрузить изображение");
      clear.textContent = "Убрать изображение";
    }
    controls.append(choose, clear);
    wrapper.append(previews, controls);
    label.append(wrapper);
    refresh();
  });
  document.querySelectorAll("[data-block-image]").forEach(component => {
    const choose = component.querySelector("[data-block-choose]");
    const clear = component.querySelector("[data-block-clear]");
    const picture = component.querySelector("[data-block-thumbnail]");
    window.setManagementImageFallback(picture);
    const url = component.querySelector("[data-block-image-url]");
    const replacement = component.querySelector('[name="replace-image"]');
    const render = () => {
      const value = url.value.trim();
      picture.hidden = !value;
      clear.hidden = !value;
      if (value) picture.src = value;
      else picture.removeAttribute("src");
    };
    const setImage = (value, id = "") => {
      url.value = value;
      url.dispatchEvent(new Event("input", {bubbles: true}));
      replacement.value = id;
    };
    url.addEventListener("input", () => {
      replacement.value = "";
      render();
    });
    choose.addEventListener("click", () => open(choose, {
      kind: "image", multiple: false,
      onSelect: ([item]) => setImage(item?.url || "", item?.id || ""),
    }));
    clear.addEventListener("click", () => {
      setImage("");
      choose.focus();
    });
  });
})();
