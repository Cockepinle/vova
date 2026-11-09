(() => {
  const header = document.querySelector('.site-header');
  if (header && window.ResizeObserver) new ResizeObserver(() => {
    document.documentElement.style.setProperty('--site-header-height', `${header.offsetHeight}px`);
  }).observe(header);
  const nav = document.querySelector('.main-nav');
  if (nav) {
    nav.id = 'site-navigation';
    const toggle = document.querySelector('.mobile-menu-toggle');
    const close = () => { nav.classList.remove('is-expanded'); toggle?.setAttribute('aria-expanded', 'false'); toggle?.classList.remove('is-active'); };
    toggle?.addEventListener('click', () => {
      const expanded = nav.classList.toggle('is-expanded');
      toggle.setAttribute('aria-expanded', String(expanded));
      toggle.classList.toggle('is-active', expanded);
    });
    nav.querySelector('.mobile-nav-close')?.addEventListener('click', close);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    document.addEventListener('click', e => { if (!e.target.closest('.site-header, .mobile-actions')) close(); });
  }
  const bar = document.querySelector('.mobile-actions');
  if (bar && window.ResizeObserver) new ResizeObserver(() => {
    if (bar.offsetHeight) document.documentElement.style.setProperty('--mobile-actions-height', `${bar.offsetHeight - (parseFloat(getComputedStyle(bar).paddingBottom) - 12)}px`);
  }).observe(bar);
  // Observe existing drawers so every entry point shares focus and scroll behaviour.
  const overlays = [...document.querySelectorAll('.product-modal, .cart-drawer, .checkout-drawer, .side-drawer, .cookie-modal, .image-lightbox, .catalog-mobile-category-tree, .catalog-mobile-filter-panel, .catalog-mobile-sort-panel')];
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
      top.querySelector('.modal-close, .cart-close, .checkout-close, .drawer-close, .cookie-close, .image-lightbox-close, .catalog-category-close, .catalog-panel-close, [data-close-catalog-panel]')?.click();
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

// Enhance existing cards; the product payload remains the source of gallery images.
(() => {
  function enhance(card) {
    const frame = card.querySelector('.product-image, .catalog-card-image');
    if (!frame || frame.dataset.galleryReady) return;
    frame.dataset.galleryReady = 'true';
    let product;
    try { product = JSON.parse(card.dataset.product); } catch (_) { return; }
    // Preserve gallery entries exactly as configured in CMS, including repeated URLs.
    const images = (Array.isArray(product.thumbs) ? product.thumbs : [])
      .filter(src => typeof src === 'string' && src);
    if (product.image && images[0] !== product.image) images.unshift(product.image);
    const image = frame.querySelector('img');
    if (!image) return;
    if (card.hasAttribute('data-product-detail-card')) {
      const setAspectRatio = activeImage => {
        if (activeImage.naturalWidth && activeImage.naturalHeight) {
          frame.style.aspectRatio = `${activeImage.naturalWidth} / ${activeImage.naturalHeight}`;
        }
      };
      if (image.complete) setAspectRatio(image);
      else image.addEventListener('load', () => setAspectRatio(image), {once: true});
    }
    if (images.length < 2) return;
    const controls = document.createElement('div');
    controls.className = 'product-gallery-controls';
    controls.setAttribute('role', 'group');
    controls.setAttribute('aria-label', `Фотографии: ${product.name}`);
    const previous = document.createElement('button');
    const next = document.createElement('button');
    const counter = document.createElement('span');
    previous.type = next.type = 'button';
    previous.className = 'gallery-arrow gallery-previous';
    next.className = 'gallery-arrow gallery-next';
    previous.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>';
    next.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>';
    previous.setAttribute('aria-label', 'Предыдущее фото');
    next.setAttribute('aria-label', 'Следующее фото');
    counter.className = 'gallery-counter';
    counter.setAttribute('aria-live', 'polite');
    counter.setAttribute('aria-atomic', 'true');
    const track = document.createElement('div');
    track.className = 'product-gallery-track';
    track.setAttribute('aria-label', `Фото товара: ${product.name}`);
    images.forEach((src, i) => {
      const slide = i === 0 ? image : document.createElement('img');
      slide.src = src;
      slide.alt = `${product.name} — фото ${i + 1}`;
      slide.draggable = false;
      if (i > 0) slide.loading = 'lazy';
      track.append(slide);
    });
    frame.prepend(track);
    const dots = document.createElement('div');
    dots.className = 'gallery-dots';
    const thumbnails = card.hasAttribute('data-product-detail-card') && images.length > 1
      ? document.createElement('div')
      : null;
    if (thumbnails) {
      thumbnails.className = 'gallery-thumbnails';
      thumbnails.setAttribute('role', 'group');
      thumbnails.setAttribute('aria-label', 'Фотографии товара');
    }
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let index = 0;
    function update() {
      counter.textContent = `${index + 1} / ${images.length}`;
      const activeImage = track.children[index];
      if (card.hasAttribute('data-product-detail-card') && activeImage?.complete) {
        const width = activeImage.naturalWidth;
        const height = activeImage.naturalHeight;
        if (width && height) frame.style.aspectRatio = `${width} / ${height}`;
      }
      [...dots.children].forEach((dot, i) => {
        dot.setAttribute('aria-current', String(i === index));
      });
      [...(thumbnails?.children || [])].forEach((thumbnail, i) => {
        thumbnail.setAttribute('aria-current', String(i === index));
      });
    }
    function goTo(nextIndex, behavior = reducedMotion.matches ? 'auto' : 'smooth') {
      index = (nextIndex + images.length) % images.length;
      track.scrollTo({left: index * track.clientWidth, behavior});
      update();
    }
    images.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'gallery-dot';
      dot.setAttribute('aria-label', `Показать фото ${i + 1}`);
      dot.addEventListener('click', () => goTo(i));
      dots.append(dot);
      if (thumbnails) {
        const thumbnail = document.createElement('button');
        const preview = document.createElement('img');
        thumbnail.type = 'button';
        thumbnail.className = 'gallery-thumbnail';
        thumbnail.setAttribute('aria-label', `Показать фото ${i + 1}`);
        thumbnail.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          goTo(i);
        });
        preview.src = src;
        preview.alt = '';
        preview.loading = 'lazy';
        thumbnail.append(preview);
        thumbnails.append(thumbnail);
      }
    });
    track.querySelectorAll('img').forEach(slide => {
      slide.addEventListener('load', () => {
        if (track.children[index] === slide) update();
      });
    });
    previous.addEventListener('click', () => goTo(index - 1));
    next.addEventListener('click', () => goTo(index + 1));
    controls.addEventListener('click', event => event.stopPropagation());
    controls.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        goTo(index + (event.key === 'ArrowLeft' ? -1 : 1));
      }
      event.stopPropagation();
    });
    track.addEventListener('scroll', () => {
      if (!track.clientWidth) return;
      index = Math.max(0, Math.min(images.length - 1, Math.round(track.scrollLeft / track.clientWidth)));
      update();
    }, {passive: true});
    // A regular desktop mouse emits vertical wheel events, not horizontal ones.
    // Convert them to photo steps; let the page scroll beyond either end.
    const desktopPointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    let wheelTotal = 0;
    let lastWheel = -Infinity;
    let lastStep = -Infinity;
    frame.addEventListener('wheel', event => {
      if (!desktopPointer.matches || event.ctrlKey || event.shiftKey ||
          Math.abs(event.deltaX) >= Math.abs(event.deltaY) || !event.deltaY ||
          event.target.closest('button')) return;
      const now = performance.now();
      if (now - lastStep < 450) {
        event.preventDefault();
        return;
      }
      const direction = Math.sign(event.deltaY);
      if ((direction < 0 && index === 0) || (direction > 0 && index === images.length - 1)) return;
      event.preventDefault();
      if (now - lastWheel > 180 || Math.sign(wheelTotal) !== direction) wheelTotal = 0;
      lastWheel = now;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? track.clientHeight : 1;
      wheelTotal += event.deltaY * unit;
      if (Math.abs(wheelTotal) >= 30) {
        goTo(index + direction);
        lastStep = now;
        wheelTotal = 0;
      }
    }, {passive: false});
    // Touch and trackpads scroll natively; desktop users can also drag the photo.
    let drag = null;
    let touchStart = null;
    let suppressClick = false;
    track.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'mouse' || event.button !== 0) return;
      drag = {x: event.clientX, left: track.scrollLeft, index, moved: false};
      suppressClick = false;
    });
    track.addEventListener('touchstart', event => {
      if (event.changedTouches.length) {
        touchStart = {x: event.changedTouches[0].clientX, index};
      }
    }, {passive: true});
    track.addEventListener('touchend', event => {
      if (!touchStart || !event.changedTouches.length) return;
      const current = touchStart;
      touchStart = null;
      const dx = event.changedTouches[0].clientX - current.x;
      if (Math.abs(dx) > 40) goTo(current.index + (dx < 0 ? 1 : -1));
    });
    track.addEventListener('touchcancel', () => { touchStart = null; }, {passive: true});
    track.addEventListener('pointermove', event => {
      if (!drag) return;
      const dx = event.clientX - drag.x;
      if (!drag.moved && Math.abs(dx) < 6) return;
      if (!drag.moved) track.setPointerCapture(event.pointerId);
      drag.moved = true;
      track.classList.add('is-dragging');
      track.scrollLeft = drag.left - dx;
    });
    const finishDrag = event => {
      if (!drag) return;
      const current = drag;
      drag = null;
      track.classList.remove('is-dragging');
      if (track.hasPointerCapture(event.pointerId)) track.releasePointerCapture(event.pointerId);
      if (!current.moved) return;
      suppressClick = true;
      const dx = event.clientX - current.x;
      const target = Math.abs(dx) > 40 ? current.index + (dx < 0 ? 1 : -1) : current.index;
      goTo(target);
      setTimeout(() => { suppressClick = false; }, 400);
    };
    track.addEventListener('pointerup', finishDrag);
    track.addEventListener('pointercancel', finishDrag);
    track.addEventListener('pointerleave', event => { if (drag && !drag.moved) drag = null; });
    track.addEventListener('click', event => {
      if (suppressClick) { event.preventDefault(); event.stopPropagation(); suppressClick = false; }
    }, true);
    if (window.ResizeObserver) new ResizeObserver(() => goTo(index, 'instant')).observe(track);
    controls.append(previous, dots, counter, next);
    frame.append(controls);
    if (thumbnails) frame.after(thumbnails);
    update();
  }
  window.refreshProductCardGallery = card => {
    const frame = card?.querySelector('.product-image, .catalog-card-image');
    const track = frame?.querySelector('.product-gallery-track');
    const image = track?.querySelector('img') || frame?.querySelector('img');
    if (!frame || !image) return;
    image.remove();
    frame.querySelector('.product-gallery-track')?.remove();
    frame.querySelector('.product-gallery-controls')?.remove();
    frame.querySelector('.gallery-dots')?.remove();
    frame.parentElement?.querySelector('.gallery-thumbnails')?.remove();
    frame.append(image);
    frame.dataset.galleryReady = '';
    enhance(card);
  };
  document.querySelectorAll('.product-grid, .catalog-grid').forEach(grid => {
    [...grid.children].forEach(enhance);
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === 1 && node.matches('[data-product]')) enhance(node);
    }))).observe(grid, {childList: true});
  });
})();

// Media uses the existing product/modal lifecycle, without third-party players.
window.renderProductMedia = (product, info) => {
  if (!info) return;
  info.querySelector('.product-media')?.remove();
  const container = document.createElement('div');
  container.className = 'product-media';
  for (const media of product.media || []) {
    const url = new URL(media.url, location.origin);
    if (!['http:', 'https:'].includes(url.protocol)) continue;
    if (media.is_video) {
      const figure = document.createElement('figure');
      const video = document.createElement('video');
      video.controls = true;
      video.preload = 'metadata';
      video.src = url.href;
      const caption = document.createElement('figcaption');
      caption.textContent = media.title;
      figure.append(video, caption);
      container.append(figure);
    } else {
      const link = document.createElement('a');
      link.href = url.href;
      link.textContent = media.title;
      link.target = '_blank';
      link.rel = 'noopener';
      container.append(link);
    }
  }
  if (container.childElementCount) info.append(container);
};
(() => {
  const modal = document.querySelector('.product-modal');
  if (!modal) return;
  if (modal.dataset.productId) {
    const card = [...document.querySelectorAll('[data-product]')].find(card => card.dataset.productId === modal.dataset.productId);
    if (card) window.renderProductMedia(JSON.parse(card.dataset.product), modal.querySelector('.modal-info'));
  }
  new MutationObserver(() => {
    if (!modal.classList.contains('is-open')) modal.querySelectorAll('video').forEach(video => video.pause());
  }).observe(modal, {attributes: true, attributeFilter: ['class']});
})();
