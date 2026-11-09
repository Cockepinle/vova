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

function productCardHtml(product) {
  const quantity = typeof window.getProductCartQuantity === "function" ? window.getProductCartQuantity(product.id) : 0;
  const isInCart = quantity > 0;
  const isFavorite = typeof window.isProductFavorite === "function" && window.isProductFavorite(product.id);
  const badge = (product.badges || []).map(label =>
    `<span class="hit-badge">${escapeCatalogHtml(label)}</span>`
  ).join("");

  return `
    <article class="catalog-card ${isInCart ? "is-in-cart" : ""}" data-product-id="${escapeCatalogHtml(product.id)}" data-product='${escapeCatalogHtml(JSON.stringify(product))}'>
      <div class="open-product" role="button" tabindex="0" aria-label="Открыть карточку ${escapeCatalogHtml(product.name)}">
        <div class="catalog-card-image">
          <div class="catalog-card-badges">${badge}</div>
          <button class="favorite-button ${isFavorite ? "is-active" : ""}" type="button" aria-label="Добавить в избранное">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 0 1 12 6a5 5 0 0 1 7.5 6.6Z"/></svg>
          </button>
          <img src="${escapeCatalogHtml(product.image)}" alt="${escapeCatalogHtml(product.name)}">
        </div>
        <div class="catalog-card-info">
          <span class="product-sku">${escapeCatalogHtml(product.sku)}</span>
          <h2>${escapeCatalogHtml(product.name)}</h2>
          <span class="product-availability">${escapeCatalogHtml(product.availability_label || "")}${product.stock_quantity ? ` · ${escapeCatalogHtml(product.stock_quantity)} ${escapeCatalogHtml(product.unit)}` : ""}</span>
          <p class="product-card-description">${escapeCatalogHtml(product.description)}</p>
        </div>
      </div>
      <div class="catalog-card-buy">
        <div class="product-buy-row">
          <p class="price">${escapeCatalogHtml(product.price)} ₽ <span>/ ${escapeCatalogHtml(product.unit)}</span></p>
          <div class="quantity-control" aria-label="Количество">
            <button class="quantity-minus" type="button" aria-label="Уменьшить количество">−</button>
            <input class="quantity-input" type="number" min="${Number(product.min_quantity) || 1}" step="1" value="${isInCart ? quantity : Number(product.min_quantity) || 1}" aria-label="Количество товара">
            <button class="quantity-plus" type="button" aria-label="Увеличить количество">+</button>
          </div>
        </div>
        <button class="add-to-cart" type="button" ${product.can_purchase === false ? "disabled" : ""}>${product.can_purchase === false ? "Нет в наличии" : isInCart ? "В корзине" : "В корзину"}</button>
      </div>
    </article>
  `;
}

function catalogApiUrl(url) {
  const target = new URL(url, window.location.origin);
  const apiUrl = new URL("/api/products/", window.location.origin);

  target.searchParams.forEach((value, name) => {
    if (["category", "scope", "hits", "q", "sort", "price_min", "price_max", "availability"].includes(name) || name.startsWith("filter_")) {
      apiUrl.searchParams.append(name, value);
    }
  });

  return apiUrl;
}

function updateCatalogHeader(url, count) {
  if (!catalogTopline) {
    return;
  }

  const target = new URL(url, window.location.origin);
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

async function loadCatalogFromApi(url, pushState = true) {
  if (!catalogGrid) {
    return;
  }

  catalogGrid.classList.add("is-loading");

  try {
    const response = await fetch(catalogApiUrl(url), {
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Не удалось загрузить товары");
    }

    catalogGrid.innerHTML = payload.products.length
      ? payload.products.map(productCardHtml).join("")
      : '<div class="catalog-empty"><h2>Товары скоро появятся</h2><p>По выбранным условиям ничего не найдено.</p></div>';
    updateCatalogHeader(url, payload.products.length);
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
    catalogGrid.innerHTML = `<div class="catalog-empty"><h2>Не удалось загрузить товары</h2><p>${escapeCatalogHtml(error.message)}</p></div>`;
  } finally {
    catalogGrid.classList.remove("is-loading");
  }
}

function changeQuantity(control, delta) {
  const value = control.querySelector(".quantity-input");
  value.value = String(Math.max(Number(value.min) || 1, (Number(value.value) || Number(value.min) || 1) + delta));
  syncCardQuantity(control);
}

function syncCardQuantity(control) {
  const modalInfo = control.closest(".modal-info");

  if (modalInfo && typeof window.getProductCartQuantity === "function" && window.getProductCartQuantity(modal.dataset.productId) > 0) {
    window.setProductCartQuantity(modal.dataset.productId, Number(control.querySelector(".quantity-input").value));
    return;
  }

  const card = control.closest(".catalog-card");

  if (!card || !card.classList.contains("is-in-cart")) {
    return;
  }

  window.setProductCartQuantity(card.dataset.productId, Number(control.querySelector(".quantity-input").value));
}

async function loadVariantProduct(variantLink) {
  const productId = variantLink.dataset.productId;
  const dataUrl = variantLink.dataset.productUrl || `/api/products/${encodeURIComponent(productId)}/`;
  if (!productId) {
    return;
  }

  const variantList = variantLink.closest(".product-variant-list");
  variantList?.classList.add("is-loading");
  try {
    const response = await fetch(dataUrl, {
      headers: {"X-Requested-With": "XMLHttpRequest"},
    });
    const payload = await response.json();
    if (!response.ok || !payload.product) {
      throw new Error(payload.error || "Не удалось загрузить вариант товара");
    }

    const product = payload.product;
    updateProductDetailPanel(product);
    updateProductCard(product);
    if (modal?.classList.contains("is-open")) {
      const info = modal.querySelector(".modal-info");
      const previousScroll = info.scrollTop;
      openProductModal(product);
      info.scrollTop = previousScroll;
    }
    window.history.replaceState(
      {productVariantId: product.id},
      "",
      product.url,
    );
    if (catalogGrid && !document.querySelector("[data-product-detail]")) {
      document.title = product.name;
    }
  } catch (error) {
    let status = variantList?.querySelector(".variant-load-error");
    if (variantList && !status) {
      status = document.createElement("p");
      status.className = "variant-load-error";
      status.setAttribute("role", "status");
      variantList.append(status);
    }
    if (status) {
      status.textContent = error.message || "Не удалось загрузить вариант товара";
    }
  } finally {
    variantList?.classList.remove("is-loading");
  }
}

function renderVariantLinks(variants) {
  return variants && variants.length > 1
    ? `<h3>Выберите вариант</h3><div class="product-variant-list">${variants.map(variant =>
        `<a class="product-variant ${variant.current ? "is-current" : ""} ${variant.unavailable ? "is-unavailable" : ""}" href="${escapeCatalogHtml(variant.url)}" data-product-id="${escapeCatalogHtml(variant.id)}" data-product-url="${escapeCatalogHtml(variant.data_url || `/api/products/${variant.id}/`)}" ${variant.current ? 'aria-current="page"' : ""}><span>${escapeCatalogHtml(variant.label)}</span>${variant.unavailable ? "<small>Нет в наличии</small>" : variant.availability === "preorder" ? "<small>Под заказ</small>" : ""}</a>`
      ).join("")}</div>`
    : "";
}

function updateProductDetailPanel(product) {
  const detail = document.querySelector("[data-product-detail]");
  if (!detail) {
    return;
  }

  detail.dataset.productId = product.id;
  const description = detail.querySelector("[data-detail-description]");
  if (description) {
    description.innerHTML = escapeCatalogHtml(product.description).replace(/\r?\n/g, "<br>");
  }
  const specs = detail.querySelector("[data-detail-specs]");
  if (specs) {
    specs.innerHTML = product.specs
      .map(([label, value]) => `<div><dt>${escapeCatalogHtml(label)}</dt><dd>${escapeCatalogHtml(value)}</dd></div>`)
      .join("");
  }
  const variants = detail.querySelector("[data-detail-variants]");
  if (variants) {
    variants.innerHTML = product.variants.map(variant =>
      `<a href="${escapeCatalogHtml(variant.url)}" data-product-id="${escapeCatalogHtml(variant.id)}" data-product-url="${escapeCatalogHtml(variant.data_url || `/api/products/${variant.id}/`)}" class="product-variant ${variant.current ? "is-current" : ""} ${variant.unavailable ? "is-unavailable" : ""}" ${variant.current ? 'aria-current="page"' : ""}><span>${escapeCatalogHtml(variant.label)}</span>${variant.unavailable ? "<small>Нет в наличии</small>" : variant.availability === "preorder" ? "<small>Под заказ</small>" : ""}</a>`
    ).join("");
  }
  window.renderProductMedia?.(product, detail);

  const heading = document.querySelector(".catalog-topline h1");
  if (heading) {
    heading.textContent = product.name;
  }
}

function updateProductCard(product) {
  const card = document.querySelector(".catalog-card[data-product-detail-card]")
    || document.querySelector(`.catalog-card[data-product-id="${CSS.escape(product.id)}"]`);
  if (!card) {
    return;
  }

  card.dataset.productId = product.id;
  card.dataset.product = JSON.stringify(product);
  const openButton = card.querySelector(".open-product");
  if (openButton) {
    openButton.setAttribute("aria-label", `Открыть карточку ${product.name}`);
  }
  const description = card.querySelector(".product-card-description");
  if (description) {
    description.textContent = product.description || "";
  }
  const image = card.querySelector(".catalog-card-image img");
  if (image) {
    image.src = product.image;
    image.alt = product.name;
  }
  const sku = card.querySelector(".product-sku");
  if (sku) {
    sku.textContent = product.sku;
  }
  const name = card.querySelector(".catalog-card-info h2");
  if (name) {
    name.textContent = product.name;
  }
  const availability = card.querySelector(".product-availability");
  if (availability) {
    availability.textContent = `${product.availability_label || ""}${product.stock_quantity ? ` · ${product.stock_quantity} ${product.unit}` : ""}`;
  }
  const badges = card.querySelector(".catalog-card-badges");
  if (badges) {
    badges.innerHTML = (product.badges || []).map(label =>
      `<span class="hit-badge">${escapeCatalogHtml(label)}</span>`
    ).join("");
  }
  const price = card.querySelector(".product-buy-row .price");
  if (price) {
    price.innerHTML = `${escapeCatalogHtml(product.price)} ₽ <span>/ ${escapeCatalogHtml(product.unit)}</span>`;
  }
  const input = card.querySelector(".quantity-input");
  if (input) {
    input.min = String(Math.max(1, Number(product.min_quantity) || 1));
    const cartQuantity = typeof window.getProductCartQuantity === "function"
      ? window.getProductCartQuantity(product.id)
      : 0;
    input.value = String(Math.max(
      Number(input.min),
      cartQuantity || Number(input.value) || Number(input.min),
    ));
  }
  const addButton = card.querySelector(".add-to-cart");
  const inCart = typeof window.getProductCartQuantity === "function"
    ? window.getProductCartQuantity(product.id) > 0
    : false;
  card.classList.toggle("is-in-cart", inCart);
  if (addButton) {
    addButton.disabled = product.can_purchase === false;
    addButton.textContent = product.can_purchase === false
      ? "Нет в наличии"
      : inCart
        ? "В корзине"
        : "В корзину";
  }
  window.refreshProductCardGallery?.(card);
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

  if (event.target.closest(".product-gallery-controls, .gallery-thumbnails")) return;
  const minus = event.target.closest(".quantity-minus");
  const plus = event.target.closest(".quantity-plus");
  const addButton = event.target.closest(".add-to-cart");
  const variantLink = event.target.closest(".product-variant");
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

  if (variantLink) {
    event.preventDefault();
    event.stopPropagation();
    if (!variantLink.classList.contains("is-current")) {
      loadVariantProduct(variantLink);
    }
    return;
  }

  if (minus) {
    const control = minus.closest(".quantity-control");
    if (!control.classList.contains("cart-quantity")) {
      changeQuantity(control, -1);
    }
  }

  if (plus) {
    const control = plus.closest(".quantity-control");
    if (!control.classList.contains("cart-quantity")) {
      changeQuantity(control, 1);
    }
  }

  if (addButton && !addButton.closest(".cart-drawer")) {
    event.preventDefault();
    event.stopPropagation();
    const productId = addButton.closest(".modal-info")
      ? modal.dataset.productId
      : addButton.closest(".catalog-card").dataset.productId;
    const input = addButton.closest("article, .modal-info").querySelector(".quantity-input");
    const quantityValue = input ? input.value : "1";
    const quantity = Math.max(1, Number(quantityValue) || 1);
    window.addProductToCart(productId, quantity, addButton);
    return;
  }

  if (quantityInput) {
    event.stopPropagation();
  }

  if (openButton && !event.target.closest(".favorite-button")) {
    if (!event.target.closest("button, input, select, textarea, a")) {
      openProductModal(JSON.parse(openButton.closest(".catalog-card").dataset.product));
      return;
    }
  }

  if (card && !event.target.closest("button, input, select, textarea, a, [role='button'], .quantity-control")) {
    openProductModal(JSON.parse(card.dataset.product));
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

  quantityInput.value = String(Math.max(Number(quantityInput.min) || 1, Number(quantityInput.value) || 1));
  syncCardQuantity(quantityInput.closest(".quantity-control"));
});

document.addEventListener("keydown", (event) => {
  const openButton = event.target.closest(".open-product");

  if (openButton && !event.target.closest("button, input, a") && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    const card = openButton.closest(".catalog-card");
    const product = JSON.parse(card.dataset.product);
    openProductModal(product);
  }
});

document.addEventListener("keydown", (event) => {
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

function openImageLightbox(image, alt) {
  if (!imageLightbox || !imageLightboxImg || !image) {
    return;
  }

  imageLightboxImg.src = image;
  imageLightboxImg.alt = alt || "";
  imageLightbox.classList.add("is-open");
  imageLightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("lightbox-open");
}

function closeImageLightbox() {
  if (!imageLightbox) {
    return;
  }

  imageLightbox.classList.remove("is-open");
  imageLightbox.setAttribute("aria-hidden", "true");
  document.body.classList.remove("lightbox-open");
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
  modalInput.step = "1";

  modalInput.value = String(Math.max(Number(modalInput.min), cartQuantity || Number(cardInput ? cardInput.value : modalInput.min) || 1));
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
