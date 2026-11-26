const modal = document.querySelector(".product-modal");
const modalMainImage = document.querySelector(".modal-main-image");
const modalBadge = document.querySelector(".modal-badge");
const modalMeta = document.querySelector(".modal-meta");
const modalTitle = document.querySelector("#modal-title");
const modalDescription = document.querySelector(".modal-description");
const modalSpecs = document.querySelector(".modal-specs");
const modalPrice = document.querySelector(".modal-price");
const modalThumbs = document.querySelector(".modal-thumbs");
const modalImageFrame = document.querySelector(".modal-image-frame");
const imageLightbox = document.querySelector(".image-lightbox");
const imageLightboxImg = document.querySelector(".image-lightbox-img");
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

function changeQuantity(control, delta, button) {
  const value = control.querySelector(".quantity-input");
  const minimum = Math.max(1, Number(value.getAttribute("min") || 1));
  const step = Math.max(1, Number(value.getAttribute("step") || 1));
  const current = normalizeQuantityValue(value.value, minimum, step);
  value.value = String(Math.max(minimum, current + (delta > 0 ? step : -step)));
  syncCardQuantity(control, button);
}

function getProductFromCard(card) {
  return JSON.parse(card.dataset.product);
}

function addToCart(productId, quantity, button) {
  if (typeof window.addProductToCart !== "function") {
    console.error("Cart script is not loaded");
    return;
  }

  window.addProductToCart(productId, quantity, button);
}

function syncCardQuantity(control, button = control.querySelector(".quantity-plus")) {
  const modalInfo = control.closest(".modal-info");
  const input = control.querySelector(".quantity-input");
  const minimum = Math.max(1, Number(input ? input.getAttribute("min") : 1));
  const value = normalizeQuantityValue(input?.value, minimum, input?.step);

  if (modalInfo && typeof window.getProductCartQuantity === "function" && window.getProductCartQuantity(modal.dataset.productId) > 0) {
    window.setProductCartQuantity(modal.dataset.productId, Math.max(minimum, value), button, input);
    return;
  }

  const card = control.closest(".product-card");

  if (!card || !card.classList.contains("is-in-cart")) {
    return;
  }

  window.setProductCartQuantity(card.dataset.productId, Math.max(minimum, value), button, input);
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
  modalDescription.textContent = product.description;
  modalPrice.innerHTML = `${product.price} ₽ <span>/ ${product.unit}</span>`;
  modalSpecs.innerHTML = product.specs
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
  const images = [...new Set([product.image, ...(product.thumbs || [])].filter(Boolean))];
  modalThumbs.innerHTML = images
    .map(
      (image, index) =>
        `<button class="modal-thumb ${index === 0 ? "active" : ""}" type="button" data-image="${image}" aria-label="Фото ${index + 1}"><img src="${image}" alt=""></button>`,
    )
    .join("");
  modal.querySelectorAll(".modal-image-arrow").forEach((arrow) => {
    arrow.hidden = images.length < 2;
  });

  modal.dataset.productId = product.id;
  const favoriteButton = document.querySelector(`[data-product-id="${product.id}"] .favorite-button`);
  const productCard = document.querySelector(`[data-product-id="${product.id}"].product-card`);
  const cardInput = productCard ? productCard.querySelector(".quantity-input") : null;
  const cartQuantity = typeof window.getProductCartQuantity === "function" ? window.getProductCartQuantity(product.id) : 0;
  const modalInput = modal.querySelector(".modal-controls .quantity-input");
  modalInput.min = String(Math.max(1, Number(product.min_quantity) || 1));
  modalInput.step = String(Math.max(1, Number(product.quantity_step) || 1));
  const minimum = Math.max(1, Number(modalInput ? modalInput.getAttribute("min") : product.min_quantity || 1));

  modalInput.value = String(Math.max(minimum, cartQuantity || Number(cardInput ? cardInput.value : minimum) || minimum));
  const modalFavorite = modal.querySelector(".modal-favorite");
  const isFavorite = window.isProductFavorite?.(product.id) ?? Boolean(favoriteButton?.classList.contains("is-active"));
  modalFavorite.classList.toggle("is-active", isFavorite);
  modalFavorite.setAttribute("aria-pressed", String(isFavorite));
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

window.openProductDetails = openProductModal;

document.addEventListener("click", (event) => {
  if (event.target.closest(".product-gallery-controls")) return;
  const minus = event.target.closest(".quantity-minus");
  const plus = event.target.closest(".quantity-plus");
  const addButton = event.target.closest(".add-to-cart");
  const favoriteButton = event.target.closest(".favorite-button, .modal-favorite");
  const quantityInput = event.target.closest(".quantity-input");
  const closeButton = event.target.closest(".modal-close, .modal-backdrop");
  const lightboxClose = event.target.closest(".image-lightbox-close");
  const thumb = event.target.closest(".modal-thumb");
  const modalImageStep = event.target.closest("[data-modal-image-step]");
  const productCard = event.target.closest(".product-card");

  if (lightboxClose || event.target === imageLightbox) {
    closeImageLightbox();
    return;
  }

  if (event.target === modalMainImage) {
    if (suppressModalImageClick) return;
    openImageLightbox(modalMainImage.src, modalMainImage.alt);
    return;
  }

  if (modalImageStep) {
    const activeIndex = [...modalThumbs.querySelectorAll(".modal-thumb")]
      .findIndex((item) => item.classList.contains("active"));
    setModalImage(activeIndex + Number(modalImageStep.dataset.modalImageStep));
    return;
  }

  if (minus && !minus.closest(".cart-drawer, .favorite-quantity")) {
    event.preventDefault();
    event.stopPropagation();
    changeQuantity(minus.closest(".quantity-control"), -1, minus);
    return;
  }

  if (plus && !plus.closest(".cart-drawer, .favorite-quantity")) {
    event.preventDefault();
    event.stopPropagation();
    changeQuantity(plus.closest(".quantity-control"), 1, plus);
    return;
  }

  if (addButton && !addButton.closest(".cart-drawer")) {
    event.preventDefault();
    event.stopPropagation();
    const modalInfo = addButton.closest(".modal-info");
    const card = addButton.closest(".product-card");
    const productId = modalInfo ? modal.dataset.productId : card.dataset.productId;
    const quantityInput = addButton.closest(".product-info, .modal-controls").querySelector(".quantity-input");
    const quantity = normalizeQuantityValue(quantityInput?.value, quantityInput?.min, quantityInput?.step);
    if (quantityInput) quantityInput.value = String(quantity);
    addToCart(productId, quantity, addButton);
    return;
  }

  if (quantityInput) {
    event.stopPropagation();
  }

  if (favoriteButton) {
    event.stopPropagation();
    return;
  }

  if (closeButton) {
    closeProductModal();
    return;
  }

  if (thumb) {
    const index = [...modalThumbs.querySelectorAll(".modal-thumb")].indexOf(thumb);
    setModalImage(index);
    return;
  }

  if (productCard) {
    openProductModal(getProductFromCard(productCard));
  }
});

document.addEventListener("change", (event) => {
  const quantityInput = event.target.closest ? event.target.closest(".quantity-input") : null;

  if (!quantityInput) {
    return;
  }

  quantityInput.value = String(normalizeQuantityValue(quantityInput.value, quantityInput.min, quantityInput.step));
  syncCardQuantity(quantityInput.closest(".quantity-control"));
});

document.addEventListener("keydown", (event) => {
  const productCard = event.target.closest ? event.target.closest(".product-card") : null;

  if (productCard && !event.target.closest("button, input, a") && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    openProductModal(getProductFromCard(productCard));
  }

  if (event.key === "Escape") {
    if (imageLightbox && imageLightbox.classList.contains("is-open")) {
      closeImageLightbox();
      return;
    }

    closeProductModal();
  }
});
