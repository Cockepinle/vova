(() => {
  const editor = document.querySelector("[data-product-gallery]");
  if (!editor || !window.openManagementMediaPicker) return;
  const grid = editor.querySelector("[data-gallery-grid]");
  const template = editor.querySelector("[data-gallery-tile]");
  const field = editor.querySelector("[data-gallery-manifest]");
  const empty = editor.querySelector("[data-gallery-empty]");
  const status = editor.querySelector("[data-gallery-status]");
  const pick = editor.querySelector("[data-gallery-pick]");
  const urlInput = editor.querySelector("[data-gallery-url]");
  const items = JSON.parse(document.getElementById("product-gallery-items").textContent);
  let primary = items.find(item => item.primary)?.key ?? null;
  let dragKey = null;
  let nextUrlKey = Date.now();

  function sync() {
    field.dataset.draftPreviews = JSON.stringify(Object.fromEntries(items
      .filter(item => item.key.startsWith("media:")).map(item => [item.key, item.url])));
    field.value = JSON.stringify({
      primary,
      items: items.map(({key, alt, url}) => ({key, alt, ...(key.startsWith("url:") ? {url} : {})})),
    });
    field.dispatchEvent(new Event("change", {bubbles: true}));
  }

  function render(focusKey, selector = "[data-gallery-open]") {
    grid.replaceChildren(...items.map((item, index) => {
      const tile = template.content.firstElementChild.cloneNode(true);
      tile.dataset.key = item.key;
      tile.classList.toggle("is-primary", item.key === primary);
      tile.querySelector("[data-gallery-badge]").hidden = item.key !== primary;
      const button = tile.querySelector("[data-gallery-primary]");
      button.hidden = item.key === primary;
      const link = tile.querySelector("[data-gallery-open]");
      try {
        const url = new URL(item.url, document.baseURI);
        if (["https:", "http:"].includes(url.protocol)) link.href = url.href;
      } catch {
        // A legacy photo address can still be removed from the gallery.
      }
      link.draggable = false;
      const img = link.querySelector("img");
      img.src = item.url;
      img.alt = item.alt || `Фотография ${index + 1}`;
      img.draggable = false;
      tile.querySelector('[data-gallery-step="-1"]').disabled = index === 0;
      tile.querySelector('[data-gallery-step="1"]').disabled = index === items.length - 1;
      tile.querySelector("[data-gallery-alt]").value = item.alt;
      return tile;
    }));
    empty.hidden = items.length > 0;
    sync();
    if (focusKey) {
      const tile = [...grid.children].find(element => element.dataset.key === focusKey);
      const focusTarget = tile?.querySelector(selector);
      if (focusTarget && !focusTarget.disabled && !focusTarget.hidden) focusTarget.focus();
      else (tile?.querySelector("[data-gallery-open]") || pick).focus();
    }
  }

  function announce(message) {
    status.textContent = `${message} Сохраните товар, чтобы применить изменения.`;
  }

  function append(itemsToAdd) {
    if (!itemsToAdd.length) return;
    items.push(...itemsToAdd);
    primary ??= items[0].key;
    render();
    announce(`Добавлено фотографий: ${itemsToAdd.length}.`);
  }

  function move(from, to, selector) {
    if (from < 0 || to < 0 || to >= items.length || from === to) return;
    const [item] = items.splice(from, 1);
    items.splice(to, 0, item);
    render(item.key, selector);
    announce(`Фото перемещено на позицию ${to + 1}.`);
  }

  pick.addEventListener("click", () => {
    window.openManagementMediaPicker(pick, {
      kind: "image",
      multiple: true,
      exclude: items.filter(item => item.mediaId).map(item => String(item.mediaId)),
      onSelect: selection => append(selection.map(item => ({
        key: `media:${item.id}`, url: item.url, alt: item.alt || "", mediaId: item.id,
      }))),
    });
  });

  editor.querySelector("[data-gallery-add-url]").addEventListener("click", () => {
    const value = urlInput.value.trim();
    try {
      const url = new URL(value);
      if (!["https:", "http:"].includes(url.protocol) || !url.hostname || value.length > 200) throw new Error();
      if (items.some(item => item.url === url.href)) {
        status.textContent = "Эта фотография уже есть в галерее.";
        return;
      }
      append([{key: `url:${nextUrlKey++}`, url: url.href, alt: ""}]);
      urlInput.value = "";
    } catch {
      status.textContent = "Введите полный адрес фотографии http:// или https://, до 200 символов.";
      urlInput.focus();
    }
  });
  urlInput.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    editor.querySelector("[data-gallery-add-url]").click();
  });

  grid.addEventListener("click", event => {
    const tile = event.target.closest("[data-key]");
    const button = event.target.closest("button");
    if (!tile || !button) return;
    const index = items.findIndex(item => item.key === tile.dataset.key);
    if (button.hasAttribute("data-gallery-primary")) {
      primary = tile.dataset.key;
      render(primary);
      announce("Главное фото выбрано.");
    } else if (button.hasAttribute("data-gallery-remove")) {
      const [removed] = items.splice(index, 1);
      if (primary === removed.key) primary = items[0]?.key ?? null;
      render(items[Math.min(index, items.length - 1)]?.key || removed.key);
      announce("Фото убрано из товара.");
    } else if (button.dataset.galleryStep) {
      move(index, index + Number(button.dataset.galleryStep), `[data-gallery-step="${button.dataset.galleryStep}"]`);
    }
  });
  grid.addEventListener("input", event => {
    if (!event.target.matches("[data-gallery-alt]")) return;
    const key = event.target.closest("[data-key]").dataset.key;
    items.find(item => item.key === key).alt = event.target.value;
    sync();
  });
  grid.addEventListener("dragstart", event => {
    if (!event.target.matches("[data-key]")) return;
    dragKey = event.target.dataset.key;
    event.dataTransfer.setData("text/plain", dragKey);
    event.dataTransfer.effectAllowed = "move";
  });
  grid.addEventListener("dragover", event => {
    const tile = event.target.closest("[data-key]");
    if (!dragKey || !tile || tile.dataset.key === dragKey) return;
    event.preventDefault();
    grid.querySelector(".is-drop-target")?.classList.remove("is-drop-target");
    tile.classList.add("is-drop-target");
  });
  grid.addEventListener("drop", event => {
    const tile = event.target.closest("[data-key]");
    if (!dragKey || !tile) return;
    event.preventDefault();
    move(items.findIndex(item => item.key === dragKey), items.findIndex(item => item.key === tile.dataset.key));
  });
  grid.addEventListener("dragend", () => {
    dragKey = null;
    grid.querySelector(".is-drop-target")?.classList.remove("is-drop-target");
  });

  editor.closest("form").addEventListener("management-draft-restored", event => {
    const saved = event.detail.gallery_manifest?.[0];
    if (!saved) return;
    try {
      const manifest = JSON.parse(saved);
      const previews = JSON.parse(event.detail.gallery_previews?.[0] || "{}");
      const originals = new Map(items.map(item => [item.key, item]));
      const restored = manifest.items.flatMap(entry => {
        const original = originals.get(entry.key);
        const url = original?.url || entry.url || previews[entry.key];
        if (!url || !["http:", "https:"].includes(new URL(url, location.href).protocol)) return [];
        return [{...original, key: entry.key, url, alt: entry.alt,
          primary: entry.key === manifest.primary}];
      });
      items.splice(0, items.length, ...restored);
      primary = restored.some(item => item.key === manifest.primary) ? manifest.primary : restored[0]?.key ?? null;
      render();
    } catch {}
  });
  render();
  field.disabled = false;
})();
