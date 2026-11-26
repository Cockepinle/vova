(() => {
  function extension(file) {
    return file.name.match(/\.[^.]+$/)?.[0].toLowerCase();
  }

  function fallback(image) {
    const placeholder = document.body.dataset.missingImage;
    if (!placeholder) return;
    const replace = () => {
      image.alt = "Изображение недоступно";
      image.src = placeholder;
    };
    if (image.complete && image.naturalWidth === 0 && image.getAttribute("src")) replace();
    else image.addEventListener("error", replace, {once: true});
  }

  function setup(input) {
    if (input.dataset.uploadReady) return;
    const label = input.closest("label");
    if (!label) return;
    input.dataset.uploadReady = "1";
    const hint = document.createElement("small");
    hint.className = "upload-hint";
    hint.textContent = input.dataset.uploadHint;
    if (input.id) {
      hint.id = input.id + "-upload-hint";
      input.setAttribute("aria-describedby", [input.getAttribute("aria-describedby"), hint.id].filter(Boolean).join(" "));
    }
    const feedback = document.createElement("span");
    feedback.className = "image-upload-feedback";
    feedback.setAttribute("role", "status");
    label.append(hint, feedback);
    const picker = input.matches("[data-media-picker-upload]");
    const category = input.closest("[data-category-image]");
    let objectUrls = [];
    let generation = 0;
    const current = label.parentElement.querySelector("[data-current-preview]") || document.createElement("img");
    const linkedPicker = [...document.querySelectorAll("[data-direct-upload]")].some(label => label.dataset.directUpload === input.id);
    if (input.dataset.currentImage && !category && !linkedPicker && !current.isConnected) {
      current.className = "current-image-preview";
      current.alt = "Текущее изображение";
      fallback(current);
      current.src = input.dataset.currentImage;
      feedback.before(current);
    }

    function reset() {
      generation += 1;
      objectUrls.forEach(url => URL.revokeObjectURL(url));
      objectUrls = [];
      feedback.replaceChildren();
      feedback.classList.remove("is-error");
      current.hidden = false;
      input.setCustomValidity("");
    }

    function setPolicy(policy) {
      reset();
      input.value = "";
      input.accept = policy.accept;
      input.dataset.uploadLimit = policy["data-upload-limit"];
      hint.textContent = policy["data-upload-hint"];
    }

    if (picker) {
      input.addEventListener("upload-policy", event => setPolicy(event.detail));
    }
    input.addEventListener("upload-reset", reset);

    input.addEventListener("change", async () => {
      reset();
      const version = generation;
      const files = [...input.files];
      if (!files.length) return;
      const accepted = input.accept.split(",");
      const invalid = files.find(file => !accepted.includes(extension(file)) || file.size > Number(input.dataset.uploadLimit) || !file.size);
      if (invalid) {
        const message = !invalid.size ? "Файл пуст."
          : invalid.size > Number(input.dataset.uploadLimit) ? "Размер файла превышает допустимые 4 МБ"
          : "Данный формат файла не поддерживается";
        showError(invalid.name + " — " + message);
        return;
      }

      const previews = files.map(file => {
        const tile = document.createElement("span");
        const caption = document.createElement("span");
        caption.textContent = file.name + " · " + new Intl.NumberFormat("ru", {style: "unit", unit: "kilobyte", maximumFractionDigits: 1}).format(file.size / 1000);
        if ([".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico"].includes(extension(file))) {
          const image = document.createElement("img");
          image.className = "current-image-preview";
          image.alt = "Предпросмотр выбранного изображения";
          const url = URL.createObjectURL(file);
          objectUrls.push(url);
          image.src = url;
          tile.append(image);
        }
        tile.append(caption);
        return tile;
      });
      input.setCustomValidity("Подождите, пока проверяется изображение.");
      try {
        await Promise.all(previews.flatMap(tile => [...tile.querySelectorAll("img")].map(image => image.decode())));
      } catch {
        if (version === generation) showError("Не удалось открыть изображение. Выберите другой файл.");
        return;
      }
      if (version !== generation) return;
      input.setCustomValidity("");
      if (!category) {
        current.hidden = true;
        feedback.append(...previews);
      }
      input.dispatchEvent(new Event("image-upload-ready"));
    });

    function showError(message) {
      reset();
      input.value = "";
      feedback.textContent = message;
      feedback.classList.add("is-error");
      if (!picker) input.setCustomValidity(message);
    }

    input.form?.addEventListener("reset", reset);
  }

  window.initManagementUploads = (scope = document) => {
    scope.querySelectorAll("[data-media-fallback]").forEach(fallback);
    scope.querySelectorAll("input[type=file][data-upload-limit]").forEach(setup);
  };
  window.initManagementUploads();
  window.setManagementImageFallback = fallback;
})();
