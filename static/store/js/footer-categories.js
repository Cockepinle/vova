document.querySelectorAll("[data-footer-categories]").forEach(tree => {
  let openRoot = null;

  function setExpanded(button, expanded) {
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    if (!expanded && panel.contains(document.activeElement)) button.focus();
    panel.inert = !expanded;
    button.setAttribute("aria-expanded", String(expanded));
    panel.classList.toggle("is-open", expanded);
  }

  for (const button of tree.querySelectorAll("[data-footer-toggle]")) {
    const panel = document.getElementById(button.getAttribute("aria-controls"));
    panel.hidden = false;
    button.hidden = false;
    const isRoot = button.closest("li").parentElement.hasAttribute("data-footer-category-roots");
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "false";
      if (isRoot) {
        if (openRoot && openRoot !== button) setExpanded(openRoot, false);
        openRoot = expanded ? button : null;
      }
      setExpanded(button, expanded);
    });
  }
});
