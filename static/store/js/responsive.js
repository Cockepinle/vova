(() => {
  const nav = document.querySelector('.main-nav');
  if (nav) {
    nav.id = 'site-navigation';
    const toggle = document.createElement('button');
    toggle.className = 'mobile-menu-toggle';
    toggle.type = 'button';
    toggle.textContent = '☰';
    toggle.setAttribute('aria-label', 'Меню');
    toggle.setAttribute('aria-controls', nav.id);
    toggle.setAttribute('aria-expanded', 'false');
    nav.before(toggle);
    document.body.classList.add('has-mobile-menu');
    const close = () => { nav.classList.remove('is-expanded'); toggle.setAttribute('aria-expanded', 'false'); };
    toggle.addEventListener('click', () => {
      const expanded = nav.classList.toggle('is-expanded');
      toggle.setAttribute('aria-expanded', String(expanded));
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    document.addEventListener('click', e => { if (!e.target.closest('.site-header')) close(); });
  }
  const bar = document.querySelector('.mobile-actions');
  if (bar && window.ResizeObserver) new ResizeObserver(() => {
    if (bar.offsetHeight) document.documentElement.style.setProperty('--mobile-actions-height', `${bar.offsetHeight - (parseFloat(getComputedStyle(bar).paddingBottom) - 12)}px`);
  }).observe(bar);
  // Observe existing drawers so every entry point shares focus and scroll behaviour.
  const overlays = [...document.querySelectorAll('.product-modal, .cart-drawer, .checkout-drawer, .side-drawer, .cookie-modal, .image-lightbox')];
  let stack = [];
  const returnFocus = new Map();
  const focusable = root => [...root.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')].filter(el => !el.disabled && el.tabIndex >= 0 && el.getClientRects().length);
  function sync() {
    const opened = overlays.filter(el => el.classList.contains('is-open'));
    for (const el of opened) if (!stack.includes(el)) {
      returnFocus.set(el, document.activeElement);
      stack.push(el);
      (focusable(el)[0] || el).focus({preventScroll: true});
    }
    for (const el of [...stack].reverse()) if (!opened.includes(el)) {
      stack = stack.filter(item => item !== el);
      const previous = returnFocus.get(el);
      if (previous?.isConnected) previous.focus({preventScroll: true});
      returnFocus.delete(el);
    }
    document.body.classList.toggle('overlay-active', opened.length > 0);
  }
  overlays.forEach(el => new MutationObserver(sync).observe(el, {attributes: true, attributeFilter: ['class']}));
  document.addEventListener('keydown', e => {
    const top = stack.at(-1);
    if (!top) return;
    if (e.key === 'Escape') {
      e.preventDefault(); e.stopImmediatePropagation();
      top.querySelector('.modal-close, .cart-close, .checkout-close, .drawer-close, .cookie-close, .image-lightbox-close')?.click();
    }
    if (e.key === 'Tab') {
      const items = focusable(top);
      const index = items.indexOf(document.activeElement);
      if (items.length && (index < 0 || (e.shiftKey && index === 0) || (!e.shiftKey && index === items.length - 1))) {
        e.preventDefault(); items[e.shiftKey ? items.length - 1 : 0].focus();
      }
    }
  }, true);
  if (window.visualViewport) {
    const keyboard = () => document.body.classList.toggle('keyboard-open', /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName) && window.innerHeight - visualViewport.height > 120);
    visualViewport.addEventListener('resize', keyboard);
    document.addEventListener('focusout', () => setTimeout(keyboard, 0));
  }
  sync();
})();
