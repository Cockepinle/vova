(() => {
  const form = document.querySelector("[data-legal-editor]");
  if (!form) return;
  const editor = form.querySelector(".legal-surface");
  const source = form.querySelector("[data-legal-source]");
  const toolbar = form.querySelector(".legal-toolbar");
  const selection = window.getSelection();
  const allowed = new Set("a b blockquote br div em h2 h3 h4 h5 h6 i li ol p span strong u ul table caption thead tbody tfoot tr td th".split(" "));
  const blocked = new Set("script style iframe object embed svg math form template input textarea button select link meta img video audio".split(" "));
  const alignments = new Set(["left", "center", "right", "justify"]);
  const alignedBlocks = "p, div, h2, h3, h4, h5, h6, li, td, th";
  let range;

  function safeLink(value) {
    value = value?.trim() || "";
    if (!value || /[\\\x00-\x1f]/.test(value) || value.startsWith("//")) return "";
    if (/^(\/|#)/.test(value)) return value;
    try {
      const url = new URL(value);
      if (["http:", "https:", "mailto:", "tel:"].includes(url.protocol)) return value;
    } catch {}
    return "";
  }

  function normalizeWordLists(fragment) {
    const stack = [];
    let previous;
    for (const paragraph of fragment.querySelectorAll("p")) {
      const style = paragraph.getAttribute("style") || "";
      const match = /mso-list\s*:\s*(l\d+)\s+level(\d+)\s+(lfo\d+)/i.exec(style);
      if (!match) {
        stack.length = 0;
        previous = null;
        continue;
      }
      const [ , list, level, instance] = match;
      const marker = [...paragraph.querySelectorAll("span[style]")]
        .find(span => /mso-list\s*:\s*ignore/i.test(span.getAttribute("style")));
      const numbering = marker?.textContent.trim() || "";
      marker?.remove();
      const kind = /^[•·○▪■◦\uF000-\uF8FF\u2013\u2014-]/.test(numbering) ? "ul" : "ol";
      if (previous !== paragraph.previousElementSibling) stack.length = 0;
      const depth = Math.min(Number(level), stack.length + 1);
      stack.length = Math.min(depth, stack.length);
      const key = list + instance + kind;
      let entry = stack[depth - 1];
      if (!entry || entry.key !== key) {
        const node = document.createElement(kind);
        const start = /^([1-9]\d{0,3})[.)]/.exec(numbering)?.[1];
        if (kind === "ol" && start && start !== "1") node.setAttribute("start", start);
        if (depth > 1) stack[depth - 2].item.append(node);
        else paragraph.before(node);
        entry = {key, node};
        stack[depth - 1] = entry;
      }
      const item = document.createElement("li");
      item.append(...paragraph.childNodes);
      entry.node.append(item);
      entry.item = item;
      previous = paragraph.previousElementSibling;
      paragraph.remove();
    }
  }

  function cleanFragment(html, fromClipboard = false) {
    const template = document.createElement("template");
    template.innerHTML = html;
    if (fromClipboard) normalizeWordLists(template.content);
    for (const node of [...template.content.querySelectorAll("*")]) {
      if (!template.content.contains(node)) continue;
      const tag = node.localName;
      if (blocked.has(tag) || node.namespaceURI !== "http://www.w3.org/1999/xhtml") {
        node.remove();
        continue;
      }
      if (fromClipboard || tag === "span") {
        const styles = node.style;
        const wrapperTags = [];
        if (styles.fontWeight === "bold" || Number(styles.fontWeight) >= 600) wrapperTags.push("strong");
        if (styles.fontStyle === "italic") wrapperTags.push("em");
        if ((styles.textDecorationLine || styles.textDecoration || "").includes("underline")) wrapperTags.push("u");
        for (const name of wrapperTags) {
          const wrapper = document.createElement(name);
          wrapper.append(...node.childNodes);
          node.append(wrapper);
        }
      }
      if (!allowed.has(tag) && tag !== "h1") {
        node.replaceWith(...node.childNodes);
        continue;
      }
      const align = node.style.textAlign || node.getAttribute("align");
      const oldClass = node.getAttribute("class");
      const href = safeLink(node.getAttribute("href"));
      const numeric = {ol: ["start"], li: ["value"], td: ["rowspan", "colspan"], th: ["rowspan", "colspan"]};
      const attributes = (numeric[tag] || []).map(name => [name, node.getAttribute(name)])
        .filter(([, value]) => /^\d{1,4}$/.test(value || "") && Number(value) > 0);
      if (tag === "ol" && /^(1|a|A|i|I)$/.test(node.getAttribute("type") || "")) {
        attributes.push(["type", node.getAttribute("type")]);
      }
      for (const attr of [...node.attributes]) node.removeAttribute(attr.name);
      if (!fromClipboard && ((tag === "p" && oldClass === "document-lead") ||
          (tag === "div" && ["document-section", "document-note"].includes(oldClass)))) node.className = oldClass;
      for (const [name, value] of attributes) node.setAttribute(name, value);
      if (tag === "a" && href) node.setAttribute("href", href);
      if (node.matches(alignedBlocks) && alignments.has(align)) node.style.textAlign = align;
      if (tag === "h1") {
        const heading = document.createElement("h2");
        heading.append(...node.childNodes);
        if (alignments.has(align)) heading.style.textAlign = align;
        node.replaceWith(heading);
      }
    }
    const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_COMMENT);
    const comments = [];
    while (walker.nextNode()) comments.push(walker.currentNode);
    comments.forEach(node => node.remove());
    return template;
  }

  function storeSelection() {
    if (selection.rangeCount && editor.contains(selection.getRangeAt(0).commonAncestorContainer)) {
      range = selection.getRangeAt(0).cloneRange();
    }
  }

  function sync() { source.value = editor.innerHTML; }

  function apply(command, value = null) {
    editor.focus();
    if (range && editor.contains(range.commonAncestorContainer)) {
      selection.removeAllRanges();
      selection.addRange(range);
    }
    document.execCommand(command, false, value);
    storeSelection();
    sync();
  }

  editor.append(cleanFragment(source.value).content);
  source.hidden = true;
  source.required = false;
  editor.hidden = false;
  toolbar.hidden = false;
  document.addEventListener("selectionchange", storeSelection);
  editor.addEventListener("input", sync);
  form.addEventListener("submit", sync);
  toolbar.addEventListener("mousedown", event => {
    if (event.target.closest("button")) event.preventDefault();
  });
  toolbar.addEventListener("click", event => {
    const button = event.target.closest("[data-command]");
    if (!button) return;
    const command = button.dataset.command;
    if (command === "createLink") {
      const url = safeLink(window.prompt("Адрес ссылки", "https://"));
      if (!url) return;
      if (!range || range.collapsed) {
        const link = document.createElement("a");
        link.href = url;
        link.textContent = url;
        apply("insertHTML", link.outerHTML);
      } else apply(command, url);
    } else if (command === "table") {
      const columns = Number(window.prompt("Количество столбцов (1–12)", "2"));
      if (!Number.isInteger(columns) || columns < 1 || columns > 12) return;
      const rows = Number(window.prompt("Количество строк (1–40)", "3"));
      if (!Number.isInteger(rows) || rows < 1 || rows > 40) return;
      const header = "<tr>" + "<th><br></th>".repeat(columns) + "</tr>";
      const row = "<tr>" + "<td><br></td>".repeat(columns) + "</tr>";
      apply("insertHTML", "<table><thead>" + header + "</thead><tbody>" + row.repeat(rows - 1) + "</tbody></table><p><br></p>");
    } else apply(command);
  });
  form.querySelector("[data-legal-block]").addEventListener("change", event => apply("formatBlock", event.target.value));
  form.querySelector("[data-legal-align]").addEventListener("change", event => {
    if (event.target.value) apply(event.target.value);
    event.target.value = "";
  });
  editor.addEventListener("paste", event => {
    if (!event.clipboardData) return;
    event.preventDefault();
    storeSelection();
    const rich = event.clipboardData.getData("text/html");
    if (rich) apply("insertHTML", cleanFragment(rich, true).innerHTML);
    else apply("insertText", event.clipboardData.getData("text/plain"));
  });
  editor.addEventListener("drop", event => event.preventDefault());
})();
