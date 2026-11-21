const modal = document.querySelector(".product-modal");
const modalMainImage = document.querySelector(".modal-main-image");
const modalBadge = document.querySelector(".modal-badge");
const modalMeta = document.querySelector(".modal-meta");
const modalTitle = document.querySelector("#modal-title");
const modalDescription = document.querySelector(".modal-description");
const modalVariants = document.querySelector(".modal-variants");
const modalSpecs = document.querySelector(".modal-specs");
const modalPrice = document.querySelector(".modal-price");
const modalThumbs = document.querySelector(".modal-thumbs");
const modalImageFrame = document.querySelector(".modal-image-frame");
const imageLightbox = document.querySelector(".image-lightbox");
const imageLightboxImg = document.querySelector(".image-lightbox-img");
const catalogGrid = document.querySelector(".catalog-grid");
const catalogTopline = document.querySelector(".catalog-topline");
const catalogSidebar = document.querySelector(".catalog-sidebar");
const catalogCategorySection = document.querySelector(".catalog-category-section");

function useFallbackProductImage(image) {
  const fallback = document.body.dataset.productImageFallback;
  if (!fallback || !image.matches(".catalog-card-image img, .product-detail-page img, .image-lightbox-img")) return;
  if (image.src !== new URL(fallback, document.baseURI).href) image.src = fallback;
}

document.addEventListener("error", (event) => {
  if (event.target instanceof HTMLImageElement) useFallbackProductImage(event.target);
}, true);
document.querySelectorAll(".catalog-card-image img[src], .product-detail-page img[src]").forEach(image => {
  if (image.complete && !image.naturalWidth) useFallbackProductImage(image);
});

let modalTouchStartX = null;
let suppressModalImageClick = false;

modalImageFrame?.addEventListener("touchstart", (event) => {
  modalTouchStartX = event.changedTouches[0]?.clientX ?? null;
}, {passive: true});

modalImageFrame?.addEventListener("touchend", (event) => {
  if (modalTouchStartX === null) return;
  const delta = event.changedTouches[0].clientX - modalTouchStartX;
  modalTouchStartX = null;
  if (Math.abs(delta) < 40) return;
  const thumbs = [...(modalThumbs?.querySelectorAll(".modal-thumb") || [])];
  if (thumbs.length < 2) return;
  const currentIndex = Math.max(0, thumbs.findIndex((thumb) => thumb.classList.contains("active")));
  setModalImage(currentIndex + (delta < 0 ? 1 : -1));
  suppressModalImageClick = true;
  setTimeout(() => { suppressModalImageClick = false; }, 350);
}, {passive: true});

modalMainImage?.addEventListener("click", (event) => {
  if (!suppressModalImageClick) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, true);

function escapeCatalogHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function catalogApiUrl(url) {
  const target = new URL(url, window.location.origin);
  const apiUrl = new URL("/api/products/", window.location.origin);

  target.searchParams.forEach((value, name) => {
    if (["category", "scope", "hits", "q", "sort", "price_min", "price_max", "availability"].includes(name) || name.startsWith("filter_")) {
      apiUrl.searchParams.append(name, value);
    }
  });

  apiUrl.searchParams.set("cards", "1");
  return apiUrl;
}

function updateCatalogHeader(url, count) {
  if (!catalogTopline) {
    return;
  }

  const target = new URL(url, window.location.origin);
  const sort = document.querySelector(".catalog-toolbar-sort select");
  if (sort) sort.value = target.searchParams.get("sort") || "default";
  const resultCount = document.querySelector(".catalog-result-count");
  if (resultCount) resultCount.textContent = `${count} товаров`;
  const title = catalogTopline.querySelector("h1");
  const summary = catalogTopline.querySelector("div > p:last-child");
  const activeLink = catalogSidebar?.querySelector(`a[href="${target.pathname}${target.search}"]`);
  const query = target.searchParams.get("q") || "";

  if (title && activeLink) {
    title.textContent = activeLink.textContent.replace("›", "").trim();
  } else if (title && target.searchParams.get("hits") === "1") {
    title.textContent = "Хиты продаж";
  } else if (title && !target.searchParams.get("category")) {
    title.textContent = "Все товары";
  }

  if (summary) {
    summary.textContent = `${query ? `По запросу «${query}» · ` : ""}${count} товаров`;
  }
}

function updateCatalogActiveLinks(url) {
  if (!catalogSidebar) {
    return;
  }

  const target = new URL(url, window.location.origin);
  const activeCategory = target.searchParams.get("category") || "";
  const onlyHits = target.searchParams.get("hits") === "1";

  catalogSidebar.querySelectorAll("a").forEach((link) => {
    const linkUrl = new URL(link.href, window.location.origin);
    const linkCategory = linkUrl.searchParams.get("category") || "";
    const linkHits = linkUrl.searchParams.get("hits") === "1";
    const isActive = onlyHits ? linkHits : activeCategory ? linkCategory === activeCategory && !linkHits : !linkCategory && !linkHits;

    link.classList.toggle("active", isActive);
  });
}

function updateCatalogSearchState(url) {
  const target = new URL(url, window.location.origin);

  document.querySelectorAll("[data-catalog-search]").forEach((form) => {
    let categoryInput = form.querySelector('input[type="hidden"][name="category"]');
    let hitsInput = form.querySelector('input[type="hidden"][name="hits"]');
    const category = target.searchParams.get("category") || "";
    const hits = target.searchParams.get("hits") || "";
    if (category) {
      if (!categoryInput) {
        categoryInput = document.createElement("input");
        categoryInput.type = "hidden";
        categoryInput.name = "category";
        form.append(categoryInput);
      }
      categoryInput.value = category;
    } else {
      categoryInput?.remove();
    }
    if (hits) {
      if (!hitsInput) {
        hitsInput = document.createElement("input");
        hitsInput.type = "hidden";
        hitsInput.name = "hits";
        form.append(hitsInput);
      }
      hitsInput.value = hits;
    } else {
      hitsInput?.remove();
    }
    const scope = form.querySelector('input[name="scope"]');
    if (scope) {
      scope.checked = target.searchParams.get("scope") === "category";
      scope.closest(".catalog-search-scope").hidden = !category;
    }
  });
}

function updateCatalogCategoryVisibility(url) {
  if (!catalogCategorySection) {
    return;
  }

  const target = new URL(url, window.location.origin);
  catalogCategorySection.hidden = Boolean(
    target.searchParams.get("q") || target.searchParams.get("hits") === "1",
  );
}

let catalogRequest;

async function loadCatalogFromApi(url, pushState = true) {
  if (!catalogGrid) {
    return;
  }

  catalogRequest?.abort();
  const controller = new AbortController();
  catalogRequest = controller;
  catalogGrid.classList.add("is-loading");
  catalogGrid.setAttribute("aria-busy", "true");

  try {
    const response = await fetch(catalogApiUrl(url), {
      signal: controller.signal,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Не удалось загрузить товары");
    }

    if (controller.signal.aborted) return;
    catalogGrid.innerHTML = payload.cards_html;
    updateCatalogHeader(url, payload.count);
    if (payload.seo) {
      document.title = payload.seo.title;
      catalogTopline.querySelector('h1').textContent = payload.seo.h1;
      document.querySelector('link[rel="canonical"]').href = payload.seo.canonical;
      document.querySelector('meta[name="description"]').content = payload.seo.description;
      document.querySelector('meta[name="robots"]').content = payload.seo.noindex ? 'noindex,follow' : 'index,follow';
      for (const name of ['title','description','image']) {
        const tag = document.querySelector(`meta[property="og:${name}"]`);
        if (tag) tag.content = payload.seo[`og_${name}`] || '';
      }
      document.querySelector('meta[property="og:url"]').content = payload.seo.canonical;
    }
    updateCatalogActiveLinks(url);
    updateCatalogSearchState(url);
    updateCatalogCategoryVisibility(url);

    if (pushState) {
      window.history.pushState({}, "", url);
    }
  } catch (error) {
    if (controller.signal.aborted) return;
    catalogGrid.innerHTML = `<div class="catalog-empty"><h2>Не удалось загрузить товары</h2><p>${escapeCatalogHtml(error.message)}</p></div>`;
  } finally {
    if (catalogRequest === controller) {
      catalogGrid.classList.remove("is-loading");
      catalogGrid.setAttribute("aria-busy", "false");
    }
  }
}

function changeQuantity(control, delta, button) {
  const value = control.querySelector(".quantity-input");
  const minimum = Math.max(1, Number(value.min) || 1);
  const step = Math.max(1, Number(value.step) || 1);
  const current = normalizeQuantityValue(value.value, minimum, step);
  const next = delta > 0 ? current + step : Math.max(minimum, current - step);
  value.value = String(next);
  syncCardQuantity(control, button);
}

function syncCardQuantity(control, quantityButton = control.querySelector(".quantity-plus")) {
  const modalInfo = control.closest(".modal-info");

  if (modalInfo && typeof window.getProductCartQuantity === "function" && window.getProductCartQuantity(modal.dataset.productId) > 0) {
    const input = control.querySelector(".quantity-input");
    window.setProductCartQuantity(modal.dataset.productId, Number(input.value), quantityButton, input);
    return;
  }

  const purchase = control.closest(".catalog-card, .product-detail-purchase");
  if (!purchase) return;
  const button = purchase.querySelector(".add-to-cart, [data-add-detail-product]");
  if (!button || button.disabled) return;
  const productId = purchase.dataset.productId || button.dataset.addDetailProduct;
  const cartQuantity = window.getProductCartQuantity(productId);
  if (cartQuantity) {
    button.textContent = Number(control.querySelector(".quantity-input").value) === cartQuantity
      ? "В корзине" : "Обновить корзину";
  }
}

function setDetailGalleryImage(gallery, index) {
  const thumbnails = [...gallery.querySelectorAll("[data-detail-gallery-image]")];
  if (!thumbnails.length) {
    return;
  }
  const normalizedIndex = (index + thumbnails.length) % thumbnails.length;
  const thumbnail = thumbnails[normalizedIndex];
  const mainImage = gallery.querySelector("[data-detail-main-image]");
  if (mainImage) {
    mainImage.src = thumbnail.dataset.detailGalleryImage;
    mainImage.alt = thumbnail.dataset.galleryAlt || "";
    if (lightboxGallery === gallery) {
      imageLightboxImg.src = mainImage.src;
      imageLightboxImg.alt = mainImage.alt;
    }
  }
  thumbnails.forEach((item, itemIndex) => {
    item.setAttribute("aria-current", String(itemIndex === normalizedIndex));
  });
  gallery.dataset.imageIndex = String(normalizedIndex);
  const strip = thumbnail.parentElement;
  if (thumbnail.offsetLeft < strip.scrollLeft || thumbnail.offsetLeft + thumbnail.offsetWidth > strip.scrollLeft + strip.clientWidth) {
    strip.scrollLeft = thumbnail.offsetLeft;
  }
  const counter = gallery.querySelector("[data-detail-gallery-counter]");
  if (counter) {
    counter.textContent = `${normalizedIndex + 1} / ${thumbnails.length}`;
  }
}

function renderVariantLinks(variants) {
  if (!variants || variants.length < 2) return "";
  const links = `<div class="product-variant-list">${variants.map(variant =>
        `<a class="product-variant ${variant.current ? "is-current" : ""} ${variant.unavailable ? "is-unavailable" : ""}" href="${escapeCatalogHtml(variant.url)}" data-product-id="${escapeCatalogHtml(variant.id)}" data-product-url="${escapeCatalogHtml(variant.data_url || `/api/products/${variant.id}/`)}" ${variant.current ? 'aria-current="page"' : ""}><span>${escapeCatalogHtml(variant.label)}</span>${variant.show_identity ? `<small>${escapeCatalogHtml(variant.sku || variant.name)}</small>` : ""}${variant.unavailable ? "<small>Нет в наличии</small>" : variant.availability === "preorder" ? "<small>Под заказ</small>" : ""}</a>`
      ).join("")}</div>`;
  const choices = variants.length > 6
    ? `<details class="detail-variant-more"><summary>Все варианты (${variants.length})</summary>${links}</details>`
    : links;
  return `<h3>Выберите вариант</h3>${choices}`;
}

document.addEventListener("click", (event) => {
  const panelOpen = event.target.closest(".catalog-filter-open, .catalog-sort-open");
  if (panelOpen) {
    const panelId = panelOpen.classList.contains("catalog-filter-open")
      ? "catalog-mobile-filter-panel"
      : "catalog-mobile-sort-panel";
    const panel = document.getElementById(panelId);
    document.querySelectorAll(".catalog-mobile-filter-panel, .catalog-mobile-sort-panel").forEach((item) => {
      item.classList.remove("is-open");
      item.setAttribute("aria-hidden", "true");
    });
    panel?.classList.add("is-open");
    panel?.setAttribute("aria-hidden", "false");
    document.body.classList.add("catalog-panel-open");
    return;
  }
  if (event.target.closest("[data-close-catalog-panel]")) {
    const panel = event.target.closest(".catalog-mobile-filter-panel, .catalog-mobile-sort-panel");
    panel?.classList.remove("is-open");
    panel?.setAttribute("aria-hidden", "true");
    document.body.classList.remove("catalog-panel-open");
    return;
  }
  const categoryToggle = event.target.closest(".catalog-category-toggle");
  if (categoryToggle) {
    const expanded = categoryToggle.getAttribute("aria-expanded") === "true";
    const children = document.getElementById(categoryToggle.getAttribute("aria-controls"));
    if (children) {
      categoryToggle.setAttribute("aria-expanded", String(!expanded));
      categoryToggle.setAttribute(
        "aria-label",
        `${expanded ? "Показать" : "Скрыть"} подкатегории: ${categoryToggle.closest(".catalog-category-row").querySelector(".catalog-category-link").textContent.trim()}`,
      );
      children.hidden = expanded;
    }
    return;
  }

  const categoryOpen = event.target.closest(".catalog-category-open");
  const categoryClose = event.target.closest(".catalog-category-close");
  if (categoryOpen || categoryClose) {
    const tree = document.querySelector("#catalog-mobile-category-tree");
    const expanded = Boolean(categoryOpen);
    tree?.classList.toggle("is-open", expanded);
    tree?.setAttribute("aria-hidden", String(!expanded));
    document.querySelector(".catalog-category-open")?.setAttribute("aria-expanded", String(expanded));
    document.body.classList.toggle("catalog-category-drawer-open", expanded);
    return;
  }
  if (
    document.body.classList.contains("catalog-category-drawer-open")
    && !event.target.closest(".catalog-mobile-category-tree")
  ) {
    const tree = document.querySelector("#catalog-mobile-category-tree");
    tree?.classList.remove("is-open");
    tree?.setAttribute("aria-hidden", "true");
    document.querySelector(".catalog-category-open")?.setAttribute("aria-expanded", "false");
    document.body.classList.remove("catalog-category-drawer-open");
  }

  const galleryStep = event.target.closest("[data-detail-gallery-step], [data-lightbox-step]");
  if (galleryStep) {
    const gallery = galleryStep.closest("[data-detail-gallery]") || lightboxGallery;
    if (gallery) {
      const step = Number(galleryStep.dataset.detailGalleryStep ?? galleryStep.dataset.lightboxStep);
      setDetailGalleryImage(gallery, Number(gallery.dataset.imageIndex) + step);
    }
    return;
  }

  const thumbnail = event.target.closest("[data-detail-gallery-image]");
  if (thumbnail) {
    const gallery = thumbnail.closest("[data-detail-gallery]");
    const thumbnails = [...gallery.querySelectorAll("[data-detail-gallery-image]")];
    setDetailGalleryImage(gallery, thumbnails.indexOf(thumbnail));
    return;
  }

  const zoom = event.target.closest("[data-detail-gallery-zoom]");
  if (zoom) {
    const image = zoom.querySelector("[data-detail-main-image]");
    openImageLightbox(image.src, image.alt, zoom.closest("[data-detail-gallery]"));
    return;
  }

  const detailAdd = event.target.closest("[data-add-detail-product]");
  if (detailAdd) {
    const input = detailAdd.closest(".product-detail-purchase")?.querySelector(".quantity-input");
    const minimum = input?.min || detailAdd.dataset.detailMin;
    const step = input?.step || detailAdd.dataset.detailStep;
    const quantity = normalizeQuantityValue(input?.value || minimum, minimum, step);
    if (input) input.value = String(quantity);
    window.addProductToCart(detailAdd.dataset.addDetailProduct, quantity, detailAdd, {replaceQuantity: Boolean(input)});
    return;
  }

  if (event.target.closest(".product-gallery-controls, .gallery-thumbnails")) return;
  const minus = event.target.closest(".quantity-minus");
  const plus = event.target.closest(".quantity-plus");
  const addButton = event.target.closest(".add-to-cart");
  const openButton = event.target.closest(".open-product");
  const card = event.target.closest(".catalog-card");
  const closeButton = event.target.closest(".modal-close, .modal-backdrop");
  const lightboxClose = event.target.closest(".image-lightbox-close");
  const thumb = event.target.closest(".modal-thumb");
  const modalImageStep = event.target.closest("[data-modal-image-step]");
  const quantityInput = event.target.closest(".quantity-input");

  if (lightboxClose || event.target === imageLightbox) {
    closeImageLightbox();
    return;
  }

  if (event.target === modalMainImage) {
    openImageLightbox(modalMainImage.src, modalMainImage.alt);
    return;
  }

  if (modalImageStep) {
    const activeIndex = [...modalThumbs.querySelectorAll(".modal-thumb")]
      .findIndex((item) => item.classList.contains("active"));
    setModalImage(activeIndex + Number(modalImageStep.dataset.modalImageStep));
    return;
  }

  if (minus) {
    const control = minus.closest(".quantity-control");
    if (!control.matches(".cart-quantity, .favorite-quantity")) {
      changeQuantity(control, -1, minus);
    }
  }

  if (plus) {
    const control = plus.closest(".quantity-control");
    if (!control.matches(".cart-quantity, .favorite-quantity")) {
      changeQuantity(control, 1, plus);
    }
  }

  if (addButton && !addButton.closest(".cart-drawer")) {
    event.preventDefault();
    event.stopPropagation();
    const productId = addButton.closest(".modal-info")
      ? modal.dataset.productId
      : addButton.closest(".catalog-card").dataset.productId;
    const input = addButton.closest("article, .modal-info").querySelector(".quantity-input");
    const quantity = normalizeQuantityValue(input?.value || 1, input?.min, input?.step);
    if (input) input.value = String(quantity);
    window.addProductToCart(productId, quantity, addButton, {replaceQuantity: Boolean(input && card)});
    return;
  }

  if (quantityInput) {
    event.stopPropagation();
  }

  if (openButton) return;

  if (card && !event.target.closest("button, input, select, textarea, a, [role='button'], .quantity-control")) {
    const openLink = card.querySelector(".open-product");
    if (openLink) window.location.assign(openLink.href);
  }

  if (closeButton) {
    closeProductModal();
  }

  if (thumb) {
    const index = [...modalThumbs.querySelectorAll(".modal-thumb")].indexOf(thumb);
    setModalImage(index);
  }
});

if (catalogSidebar) {
  catalogSidebar.addEventListener("click", (event) => {
    const link = event.target.closest("a");

    if (!link) {
      return;
    }

    if (new URL(link.href, window.location.origin).searchParams.has("category")) {
      return;
    }

    event.preventDefault();
    loadCatalogFromApi(link.href);
  });
}

document.querySelectorAll("[data-catalog-search]").forEach((form) => {
  const input = form.querySelector('input[name="q"]');
  const suggestions = form.querySelector(".catalog-search-suggestions");
  if (!input || !suggestions) {
    return;
  }

  let debounceTimer;
  let activeRequest;
  let highlightedSuggestion = -1;
  const hideSuggestions = () => {
    suggestions.hidden = true;
    suggestions.replaceChildren();
    input.setAttribute("aria-expanded", "false");
  };
  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    activeRequest?.abort();
    const query = input.value.trim().replace(/\s+/g, " ");
    if (query.length < 2) {
      hideSuggestions();
      return;
    }

    debounceTimer = setTimeout(async () => {
      activeRequest = new AbortController();
      try {
        const response = await fetch(
          `/api/products/suggestions/?q=${encodeURIComponent(query)}`,
          {
            signal: activeRequest.signal,
            headers: {"X-Requested-With": "XMLHttpRequest"},
          },
        );
        if (!response.ok) {
          throw new Error("Не удалось загрузить подсказки поиска");
        }
        const payload = await response.json();
        suggestions.innerHTML = payload.suggestions.map((item) => `
          <a class="catalog-search-suggestion" role="option" aria-selected="false" href="${escapeCatalogHtml(item.url)}">
            <img src="${escapeCatalogHtml(item.image)}" alt="">
            <span class="catalog-search-suggestion-copy"><strong>${escapeCatalogHtml(item.name)}</strong><small>${escapeCatalogHtml(item.sku)}</small></span>
            <strong class="catalog-search-suggestion-price">${escapeCatalogHtml(item.price)} ₽</strong>
          </a>
        `).join("") || '<p class="catalog-search-no-suggestions">Ничего не найдено</p>';
        suggestions.hidden = false;
        input.setAttribute("aria-expanded", "true");
        highlightedSuggestion = -1;
      } catch (error) {
        if (error.name !== "AbortError") {
          suggestions.innerHTML = '<p class="catalog-search-no-suggestions">Не удалось загрузить подсказки. Попробуйте выполнить поиск.</p>';
          suggestions.hidden = false;
          input.setAttribute("aria-expanded", "true");
        }
      }
    }, 180);
  });
  form.addEventListener("submit", (event) => {
    const query = input.value.trim().replace(/\s+/g, " ");
    input.value = query;
    if (!query) {
      event.preventDefault();
    }
    hideSuggestions();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideSuggestions();
      return;
    }

    const options = [...suggestions.querySelectorAll(".catalog-search-suggestion")];
    if (!options.length || suggestions.hidden) {
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      highlightedSuggestion = (highlightedSuggestion + direction + options.length) % options.length;
      options.forEach((option, index) => {
        const selected = index === highlightedSuggestion;
        option.setAttribute("aria-selected", String(selected));
        option.classList.toggle("is-highlighted", selected);
      });
    } else if (event.key === "Enter" && highlightedSuggestion >= 0) {
      event.preventDefault();
      window.location.assign(options[highlightedSuggestion].href);
    }
  });
  document.addEventListener("click", (event) => {
    if (!form.contains(event.target)) {
      hideSuggestions();
    }
  });
});

window.addEventListener("popstate", () => {
  loadCatalogFromApi(window.location.href, false);
});

window.refreshCatalogProducts = () => loadCatalogFromApi(window.location.href, false);

document.querySelector(".catalog-toolbar-sort")?.addEventListener("submit", (event) => {
  event.preventDefault();
  const url = new URL(window.location.href);
  url.searchParams.set("sort", event.currentTarget.elements.sort.value);
  loadCatalogFromApi(url.href);
});

document.addEventListener("change", (event) => {
  const toolbarSelect = event.target.closest
    ? event.target.closest(".catalog-toolbar-category select, .catalog-toolbar-sort select")
    : null;
  if (toolbarSelect) {
    toolbarSelect.form?.requestSubmit();
    return;
  }

  const quantityInput = event.target.closest ? event.target.closest(".quantity-input") : null;

  if (!quantityInput) {
    return;
  }

  quantityInput.value = String(normalizeQuantityValue(quantityInput.value, quantityInput.min, quantityInput.step));
  syncCardQuantity(quantityInput.closest(".quantity-control"));
});

document.addEventListener("keydown", (event) => {
  const gallery = lightboxGallery || event.target.closest("[data-detail-gallery]");
  if (gallery && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
    event.preventDefault();
    setDetailGalleryImage(gallery, Number(gallery.dataset.imageIndex) + (event.key === "ArrowRight" ? 1 : -1));
    return;
  }
  if (imageLightbox.classList.contains("is-open") && event.key === "Tab") {
    const controls = [...imageLightbox.querySelectorAll("button:not([hidden])")];
    const index = controls.indexOf(document.activeElement);
    const next = (index + (event.shiftKey ? -1 : 1) + controls.length) % controls.length;
    event.preventDefault();
    controls[next].focus();
    return;
  }
  if (event.key === "Escape") {
    const catalogPanel = document.querySelector(".catalog-mobile-filter-panel.is-open, .catalog-mobile-sort-panel.is-open");
    if (catalogPanel) {
      catalogPanel.classList.remove("is-open");
      catalogPanel.setAttribute("aria-hidden", "true");
      document.body.classList.remove("catalog-panel-open");
      return;
    }
    if (document.body.classList.contains("catalog-category-drawer-open")) {
      document.querySelector(".catalog-category-close")?.click();
      return;
    }
    if (imageLightbox && imageLightbox.classList.contains("is-open")) {
      closeImageLightbox();
      return;
    }

    closeProductModal();
  }
});

let lightboxGallery = null;
let lightboxTrigger = null;

function openImageLightbox(image, alt, gallery = null) {
  if (!imageLightbox || !imageLightboxImg || !image) {
    return;
  }

  lightboxGallery = gallery;
  lightboxTrigger = document.activeElement;
  const showSteps = (gallery?.querySelectorAll("[data-detail-gallery-image]").length || 0) > 1;
  imageLightbox.querySelectorAll("[data-lightbox-step]").forEach(button => { button.hidden = !showSteps; });
  imageLightboxImg.src = image;
  imageLightboxImg.alt = alt || "";
  imageLightbox.classList.add("is-open");
  imageLightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("lightbox-open");
  imageLightbox.querySelector(".image-lightbox-close").focus();
}

function closeImageLightbox() {
  if (!imageLightbox) {
    return;
  }

  imageLightbox.classList.remove("is-open");
  imageLightbox.setAttribute("aria-hidden", "true");
  document.body.classList.remove("lightbox-open");
  lightboxGallery = null;
  lightboxTrigger?.focus();
  lightboxTrigger = null;
}

function setModalImage(index) {
  const thumbs = [...(modalThumbs?.querySelectorAll(".modal-thumb") || [])];
  if (!thumbs.length) return;
  const normalizedIndex = (index + thumbs.length) % thumbs.length;
  const activeThumb = thumbs[normalizedIndex];
  modalMainImage.src = activeThumb.dataset.image;
  thumbs.forEach((thumb, thumbIndex) => {
    thumb.classList.toggle("active", thumbIndex === normalizedIndex);
  });
}

function openProductModal(product) {
  window.renderProductMedia?.(product, modal.querySelector(".modal-info"));
  modalMainImage.src = product.image;
  modalMainImage.alt = product.name;
  modalBadge.textContent = product.badge || "";
  modalBadge.style.display = product.badge ? "inline-block" : "none";
  modalMeta.textContent = `${product.sku} · ${product.category}`;
  modalTitle.textContent = product.name;
  modalVariants.innerHTML = renderVariantLinks(product.variants);
  modalDescription.textContent = product.description;
  modalPrice.innerHTML = `${escapeCatalogHtml(product.price)} ₽ <span>/ ${escapeCatalogHtml(product.unit)}</span>`;
  modalSpecs.innerHTML = product.specs
    .map(([label, value]) => `<div><dt>${escapeCatalogHtml(label)}</dt><dd>${escapeCatalogHtml(value)}</dd></div>`)
    .join("");
  const images = [...new Set([product.image, ...(product.thumbs || [])].filter(Boolean))];
  modalThumbs.innerHTML = images
    .map(
      (image, index) =>
        `<button class="modal-thumb ${index === 0 ? "active" : ""}" type="button" data-image="${escapeCatalogHtml(image)}" aria-label="Фото ${index + 1}"><img src="${escapeCatalogHtml(image)}" alt=""></button>`,
    )
    .join("");
  modal.querySelectorAll(".modal-image-arrow").forEach((arrow) => {
    arrow.hidden = images.length < 2;
  });

  modal.dataset.productId = product.id;
  const favoriteButton = document.querySelector(`[data-product-id="${product.id}"] .favorite-button`);
  const productCard = document.querySelector(`[data-product-id="${product.id}"].catalog-card`);
  const cardInput = productCard ? productCard.querySelector(".quantity-input") : null;
  const cartQuantity = typeof window.getProductCartQuantity === "function" ? window.getProductCartQuantity(product.id) : 0;
  const modalInput = modal.querySelector(".modal-controls .quantity-input");
  modalInput.min = String(Math.max(1, Number(product.min_quantity) || 1));
  modalInput.step = String(Math.max(1, Number(product.quantity_step) || 1));

  modalInput.value = String(normalizeQuantityValue(
    cartQuantity || cardInput?.value || modalInput.min,
    modalInput.min,
    modalInput.step,
  ));
  modal.querySelector(".modal-favorite").classList.toggle("is-active", favoriteButton ? favoriteButton.classList.contains("is-active") : false);
  const modalAdd = modal.querySelector(".modal-add");
  modalAdd.disabled = product.can_purchase === false;
  modalAdd.textContent = product.can_purchase === false
    ? "Нет в наличии"
    : cartQuantity > 0 || (productCard && productCard.classList.contains("is-in-cart"))
      ? "В корзине"
      : "В корзину";
  const selectedVariant = modalVariants.querySelector(".product-variant.is-current");
  if (selectedVariant) {
    selectedVariant.setAttribute("aria-current", "page");
  }
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeProductModal() {
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

window.openProductDetails = openProductModal;

if (window.initialProductToOpen) {
  const cardToOpen = document.querySelector(`[data-product-id="${window.initialProductToOpen}"].catalog-card`);

  if (cardToOpen) {
    openProductModal(JSON.parse(cardToOpen.dataset.product));
  }
}
