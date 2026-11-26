(() => {
  const user = document.body.dataset.managementUser;
  if (!user) return;
  const prefix = "mgmt-draft:" + user + ":";
  let storage;
  try {
    storage = sessionStorage;
    for (const key of Object.keys(storage).filter(key => key.startsWith(prefix + "pending:"))) {
      const token = key.slice((prefix + "pending:").length);
      const cookie = "mgmt_saved_" + token;
      if (document.cookie.split("; ").includes(cookie + "=1")) {
        const {draft, path} = JSON.parse(storage.getItem(key));
        storage.removeItem(draft);
        const related = JSON.parse(storage.getItem(prefix + "related") || "null");
        const match = location.pathname.match(/\/(?:categories|fields)\/(\d+)\/edit\/$/);
        if (related?.target === path && (match || (path === "/management/fields/new/" && location.pathname === "/management/fields/"))) {
          related.id = match?.[1];
          related.saved = location.pathname;
          storage.setItem(prefix + "related", JSON.stringify(related));
        }
        document.cookie = cookie + "=; Max-Age=0; Path=/management/; SameSite=Strict";
      }
      storage.removeItem(key);
    }
  } catch { storage = null; }

  let related;
  try { related = JSON.parse(storage.getItem(prefix + "related") || "null"); } catch {}
  if (related?.saved === location.pathname && related.origin.startsWith("/management/")) {
    const back = document.createElement("a");
    back.href = related.origin;
    back.className = "ghost-button";
    back.textContent = "Вернуться к исходной форме";
    document.querySelector(".mgmt-topbar")?.after(back);
  }
  let reloading = false;
  const forms = [...document.querySelectorAll(
    'form.mgmt-form-grid[method="post"], form.mgmt-form[method="post"], form[data-draft-form], form[data-warn-unsaved]'
  )];
  const ignored = new Set(["csrfmiddlewaretoken", "_draft_token", "gallery_revision", "version"]);
  const privateField = name => name === "customer_price_draft" || name === "price_customers" ||
    /^(customer_price_|prices-)/.test(name);
  forms.forEach((form, index) => {
    if (form.closest("dialog")) return;
    const storesDraft = storage && !form.hasAttribute("data-no-draft") &&
      /^\/management\/(products|categories|fields|variant-groups)\/(new|\d+\/edit)\/$/.test(location.pathname);
    const files = () => [...form.querySelectorAll('input[type="file"]')].some(input => input.files.length);
    const query = new URLSearchParams(location.search);
    const key = prefix + (form.getAttribute("action") || location.pathname) +
      ":" + index + ":" + (query.get("parent") || query.get("tab") || "");
    const controls = () => [...form.elements].filter(control =>
      ["INPUT", "SELECT", "TEXTAREA"].includes(control.tagName) && control.name && !ignored.has(control.name) &&
      !["file", "submit", "button", "reset", "password"].includes(control.type) &&
      (!control.disabled || control.closest(".variant-order-input")));
    function snapshot() {
      const groups = {};
      for (const control of controls()) {
        const values = groups[control.name] ??= [];
        if (control.type === "checkbox" || control.type === "radio") {
          if (control.checked) values.push([control.value, true]);
        } else {
          values.push(control.multiple ? [...control.selectedOptions].map(option => option.value) : control.value);
        }
      }
      const gallery = form.querySelector("[data-gallery-manifest]");
      if (gallery?.dataset.draftPreviews) groups.gallery_previews = [gallery.dataset.draftPreviews];
      return groups;
    }
    const baseline = snapshot();
    let submitting = false;
    const dirty = () => form.dataset.bound === "1" || files() || JSON.stringify(snapshot()) !== JSON.stringify(baseline);
    function warn(event) {
      if (submitting || discarded || reloading || !dirty()) return;
      event.preventDefault();
      event.returnValue = "";
    }
    function track() {
      window.removeEventListener("beforeunload", warn);
      if (dirty()) window.addEventListener("beforeunload", warn);
    }
    form.addEventListener("input", track);
    form.addEventListener("change", track);
    window.addEventListener("pageshow", () => { submitting = false; track(); });
    form.addEventListener("submit", event => { submitting = !event.defaultPrevented; });
    let discarded = false;
    if (!storesDraft) {
      track();
      return;
    }
    let previous = {};
    try {
      previous = JSON.parse(storage.getItem(key) || "{}");
      const safe = Object.fromEntries(Object.entries(previous).filter(([name]) => !privateField(name)));
      if (Object.keys(safe).length !== Object.keys(previous).length) storage.setItem(key, JSON.stringify(safe));
      previous = safe;
    } catch { previous = {}; }
    const bar = document.createElement("div");
    bar.className = "draft-bar";
    const message = document.createElement("span");
    message.setAttribute("role", "status");
    const reset = document.createElement("button");
    reset.className = "ghost-button";
    reset.type = "button";
    reset.textContent = "Сбросить черновик";
    bar.append(message, reset);
    bar.hidden = true;
    form.prepend(bar);
    const notice = "Черновик сохранён в этой вкладке.";
    let restoring = false;

    function persist() {
      if (restoring || discarded || reloading) return;
      const state = snapshot();
      const diff = Object.fromEntries(Object.entries(state).filter(([name, value]) => !privateField(name) &&
        (JSON.stringify(value) !== JSON.stringify(baseline[name]) || Object.hasOwn(previous, name))));
      bar.hidden = !Object.keys(diff).length;
      try {
        if (bar.hidden) storage.removeItem(key);
        else storage.setItem(key, JSON.stringify(diff));
        message.textContent = notice;
      } catch {
        message.textContent = "Не удалось сохранить черновик в браузере.";
      }
    }
    function restore(data, notify = true) {
      restoring = true;
      for (const [totalName, addSelector] of [
        ["parameters-TOTAL_FORMS", "[data-add-parameter]"], ["links-TOTAL_FORMS", "[data-add-link]"],
      ]) {
        const total = form.elements.namedItem(totalName);
        const add = form.querySelector(addSelector);
        const count = Math.min(Number(data[totalName]?.[0]) || 0, 100);
        for (let attempts = 0; total && add && Number(total.value) < count && attempts < count; attempts++) add.click();
      }
      const indices = {};
      const checkedValues = new Map();
      const changed = [];
      for (const control of controls()) {
        const index = indices[control.name] ?? 0;
        indices[control.name] = index + 1;
        const value = data[control.name]?.[index];
        if (!data[control.name]) continue;
        if (control.type === "checkbox" || control.type === "radio") {
          if (!checkedValues.has(control.name)) {
            checkedValues.set(control.name, new Set(data[control.name].filter(entry =>
              Array.isArray(entry) && entry[1]).map(entry => entry[0])));
          }
          const checked = checkedValues.get(control.name).has(control.value);
          if (control.checked === checked) continue;
          control.checked = checked;
        } else if (value === undefined) continue;
        else if (control.multiple) {
          for (const option of control.options) option.selected = value.includes(option.value);
        } else if (control.tagName !== "SELECT" || [...control.options].some(option => option.value === value)) {
          control.value = value;
        }
        changed.push(control);
      }
      for (const control of changed) {
        if (control.name !== "name" && control.name !== "slug" && control.name !== "h1" && control.name !== "seo_title") {
          control.dispatchEvent(new Event("change", {bubbles: true}));
        }
      }
      if (notify) form.dispatchEvent(new CustomEvent("management-draft-restored", {detail: data}));
      restoring = false;
    }
    if (Object.keys(previous).length) {
      if (document.body.dataset.managementPost !== "POST") restore(previous);
      bar.hidden = false;
      message.textContent = "Черновик восстановлен. Файлы с компьютера нужно выбрать повторно.";
    }
    if (index === 0 && related?.saved && related.origin === location.pathname + location.search) {
      const field = form.elements.namedItem(related.field);
      if (related.id && field?.tagName === "SELECT" && [...field.options].some(option => option.value === related.id)) {
        field.value = related.id;
        field.dispatchEvent(new Event("change", {bubbles: true}));
        persist();
      }
      storage.removeItem(prefix + "related");
    }
    reset.onclick = () => {
      if (!confirm("Сбросить черновик и открыть сохранённую версию?")) return;
      storage.removeItem(key);
      discarded = true;
      form.dataset.draftReloading = "1";
      location.replace(location.href);
    };
    form.addEventListener("click", event => {
      const link = event.target.closest("[data-draft-related]");
      if (!link) return;
      persist();
      const state = snapshot();
      if (files() || Object.entries(state).some(([name, value]) => privateField(name) &&
          JSON.stringify(value) !== JSON.stringify(baseline[name]))) {
        link.target = "_blank";
        link.rel = "noopener";
        return;
      }
      link.removeAttribute("target");
      try { storage.setItem(prefix + "related", JSON.stringify({
        origin: location.pathname + location.search, target: new URL(link.href).pathname, field: link.dataset.draftRelated,
      })); } catch {}
    });
    form.addEventListener("input", persist);
    form.addEventListener("change", persist);
    form.addEventListener("submit", event => {
      if (event.defaultPrevented || event.submitter?.name === "save_customer_prices" ||
          event.submitter?.hasAttribute("formaction")) return;
      persist();
      const token = [...crypto.getRandomValues(new Uint8Array(16))].map(byte => byte.toString(16).padStart(2, "0")).join("");
      let input = form.elements.namedItem("_draft_token");
      if (!input) {
        input = document.createElement("input");
        Object.assign(input, {type: "hidden", name: "_draft_token"});
        form.append(input);
      }
      input.value = token;
      try { storage.setItem(prefix + "pending:" + token, JSON.stringify({draft: key, path: location.pathname})); } catch {}
    });
    track();
    window.addEventListener("pagehide", persist);
  });
  window.addEventListener("pageshow", event => {
    if (!event.persisted || forms.some(form => [...form.querySelectorAll('input[type="file"]')].some(input => input.files.length))) return;
    reloading = true;
    for (const form of forms) form.dataset.draftReloading = "1";
    location.reload();
  });
})();
