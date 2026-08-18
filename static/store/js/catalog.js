const modal = document.querySelector(".product-modal");
const modalMainImage = document.querySelector(".modal-main-image");
const modalBadge = document.querySelector(".modal-badge");
const modalMeta = document.querySelector(".modal-meta");
const modalTitle = document.querySelector("#modal-title");
const modalDescription = document.querySelector(".modal-description");
const modalSpecs = document.querySelector(".modal-specs");
const modalPrice = document.querySelector(".modal-price");
const modalThumbs = document.querySelector(".modal-thumbs");
const imageLightbox = document.querySelector(".image-lightbox");
const imageLightboxImg = document.querySelector(".image-lightbox-img");
const catalogGrid = document.querySelector(".catalog-grid");
const catalogTopline = document.querySelector(".catalog-topline");
const catalogSearch = document.querySelector(".catalog-search");
const catalogSidebar = document.querySelector(".catalog-sidebar");

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
  const badge = product.badge ? `<span class="hit-badge">${escapeCatalogHtml(product.badge)}</span>` : "";

  return `
    <article class="catalog-card ${isInCart ? "is-in-cart" : ""}" data-product-id="${escapeCatalogHtml(product.id)}" data-product='${escapeCatalogHtml(JSON.stringify(product))}'>
      <div class="open-product" role="button" tabindex="0" aria-label="Открыть карточку ${escapeCatalogHtml(product.name)}">
        <div class="catalog-card-image">
          ${badge}
          <button class="favorite-button ${isFavorite ? "is-active" : ""}" type="button" aria-label="Добавить в избранное">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 0 1 12 6a5 5 0 0 1 7.5 6.6Z"/></svg>
          </button>
          <img src="${escapeCatalogHtml(product.image)}" alt="${escapeCatalogHtml(product.name)}">
        </div>
        <div class="catalog-card-info">
          <span class="product-sku">${escapeCatalogHtml(product.sku)}</span>
          <h3>${escapeCatalogHtml(product.name)}</h3>
        </div>
      </div>
      <div class="catalog-card-buy">
        <div class="product-buy-row">
          <p class="price">${escapeCatalogHtml(product.price)} ₽ <span>/ ${escapeCatalogHtml(product.unit)}</span></p>
          <div class="quantity-control" aria-label="Количество">
            <button class="quantity-minus" type="button" aria-label="Уменьшить количество">−</button>
            <input class="quantity-input" type="number" min="1" value="${isInCart ? quantity : 1}" aria-label="Количество товара">
            <button class="quantity-plus" type="button" aria-label="Увеличить количество">+</button>
          </div>
        </div>
        <button class="add-to-cart" type="button">${isInCart ? "В корзине" : "В корзину"}</button>
      </div>
    </article>
  `;
}

function catalogApiUrl(url) {
  const target = new URL(url, window.location.origin);
  const apiUrl = new URL("/api/products/", window.location.origin);

  ["category", "hits", "q"].forEach((name) => {
    const value = target.searchParams.get(name);

    if (value) {
      apiUrl.searchParams.set(name, value);
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

function setHiddenSearchField(name, value) {
  if (!catalogSearch) {
    return;
  }

  let input = catalogSearch.querySelector(`input[type="hidden"][name="${name}"]`);

  if (!value) {
    input?.remove();
    return;
  }

  if (!input) {
    input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    catalogSearch.prepend(input);
  }

  input.value = value;
}

function updateCatalogSearchState(url) {
  const target = new URL(url, window.location.origin);

  setHiddenSearchField("category", target.searchParams.get("category") || "");
  setHiddenSearchField("hits", target.searchParams.get("hits") || "");
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
    updateCatalogActiveLinks(url);
    updateCatalogSearchState(url);

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
  value.value = String(Math.max(1, Number(value.value) + delta));
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

document.addEventListener("click", (event) => {
  const minus = event.target.closest(".quantity-minus");
  const plus = event.target.closest(".quantity-plus");
  const addButton = event.target.closest(".add-to-cart");
  const openButton = event.target.closest(".open-product");
  const closeButton = event.target.closest(".modal-close, .modal-backdrop");
  const lightboxClose = event.target.closest(".image-lightbox-close");
  const thumb = event.target.closest(".modal-thumb");
  const quantityInput = event.target.closest(".quantity-input");

  if (lightboxClose || event.target === imageLightbox) {
    closeImageLightbox();
    return;
  }

  if (event.target === modalMainImage) {
    openImageLightbox(modalMainImage.src, modalMainImage.alt);
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
    const card = openButton.closest(".catalog-card");
    const product = JSON.parse(card.dataset.product);
    openProductModal(product);
  }

  if (closeButton) {
    closeProductModal();
  }

  if (thumb) {
    modalMainImage.src = thumb.dataset.image;
    document.querySelectorAll(".modal-thumb").forEach((item) => item.classList.remove("active"));
    thumb.classList.add("active");
  }
});

if (catalogSearch) {
  catalogSearch.addEventListener("submit", (event) => {
    event.preventDefault();
    const params = new URLSearchParams(new FormData(catalogSearch));
    const url = `${catalogSearch.action}?${params.toString()}`;
    loadCatalogFromApi(url);
  });
}

if (catalogSidebar) {
  catalogSidebar.addEventListener("click", (event) => {
    const link = event.target.closest("a");

    if (!link) {
      return;
    }

    event.preventDefault();
    loadCatalogFromApi(link.href);
  });
}

window.addEventListener("popstate", () => {
  loadCatalogFromApi(window.location.href, false);
});

window.refreshCatalogProducts = () => loadCatalogFromApi(window.location.href, false);

document.addEventListener("change", (event) => {
  const quantityInput = event.target.closest ? event.target.closest(".quantity-input") : null;

  if (!quantityInput) {
    return;
  }

  quantityInput.value = String(Math.max(1, Number(quantityInput.value) || 1));
  syncCardQuantity(quantityInput.closest(".quantity-control"));
});

document.addEventListener("keydown", (event) => {
  const openButton = event.target.closest(".open-product");

  if (openButton && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    const card = openButton.closest(".catalog-card");
    const product = JSON.parse(card.dataset.product);
    openProductModal(product);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
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

function openProductModal(product) {
  modalMainImage.src = product.image;
  modalMainImage.alt = product.name;
  modalBadge.textContent = product.badge || "";
  modalBadge.style.display = product.badge ? "inline-block" : "none";
  modalMeta.textContent = `${product.sku} · ${product.category}`;
  modalTitle.textContent = product.name;
  modalDescription.textContent = product.description;
  modalPrice.innerHTML = `${product.price} ₽ <span>/ ${product.unit}</span>`;
  modalSpecs.innerHTML = product.specs
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
  modalThumbs.innerHTML = product.thumbs
    .map(
      (image, index) =>
        `<button class="modal-thumb ${index === 0 ? "active" : ""}" type="button" data-image="${image}" aria-label="Фото ${index + 1}"><img src="${image}" alt=""></button>`,
    )
    .join("");

  modal.dataset.productId = product.id;
  const favoriteButton = document.querySelector(`[data-product-id="${product.id}"] .favorite-button`);
  const productCard = document.querySelector(`[data-product-id="${product.id}"].catalog-card`);
  const cardInput = productCard ? productCard.querySelector(".quantity-input") : null;
  const cartQuantity = typeof window.getProductCartQuantity === "function" ? window.getProductCartQuantity(product.id) : 0;
  const modalInput = modal.querySelector(".modal-controls .quantity-input");

  modalInput.value = String(Math.max(1, cartQuantity || Number(cardInput ? cardInput.value : 1) || 1));
  modal.querySelector(".modal-favorite").classList.toggle("is-active", favoriteButton ? favoriteButton.classList.contains("is-active") : false);
  modal.querySelector(".modal-add").textContent = cartQuantity > 0 || (productCard && productCard.classList.contains("is-in-cart")) ? "В корзине" : "В корзину";
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
