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

function changeQuantity(control, delta) {
  const value = control.querySelector(".quantity-input");
  const minimum = Math.max(1, Number(value.getAttribute("min") || 1));
  const step = Math.max(1, Number(value.getAttribute("step") || minimum));
  const current = Number(value.value) || minimum;
  value.value = String(Math.max(minimum, current + (delta * step)));
  syncCardQuantity(control);
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

function syncCardQuantity(control) {
  const modalInfo = control.closest(".modal-info");
  const input = control.querySelector(".quantity-input");
  const minimum = Math.max(1, Number(input ? input.getAttribute("min") : 1));
  const value = Number(input ? input.value : minimum) || minimum;

  if (modalInfo && typeof window.getProductCartQuantity === "function" && window.getProductCartQuantity(modal.dataset.productId) > 0) {
    window.setProductCartQuantity(modal.dataset.productId, Math.max(minimum, value));
    return;
  }

  const card = control.closest(".product-card");

  if (!card || !card.classList.contains("is-in-cart")) {
    return;
  }

  window.setProductCartQuantity(card.dataset.productId, Math.max(minimum, value));
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
  const productCard = document.querySelector(`[data-product-id="${product.id}"].product-card`);
  const cardInput = productCard ? productCard.querySelector(".quantity-input") : null;
  const cartQuantity = typeof window.getProductCartQuantity === "function" ? window.getProductCartQuantity(product.id) : 0;
  const modalInput = modal.querySelector(".modal-controls .quantity-input");
  const minimum = Math.max(1, Number(modalInput ? modalInput.getAttribute("min") : product.min_quantity || 1));

  modalInput.value = String(Math.max(minimum, cartQuantity || Number(cardInput ? cardInput.value : minimum) || minimum));
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
  const minus = event.target.closest(".quantity-minus");
  const plus = event.target.closest(".quantity-plus");
  const addButton = event.target.closest(".add-to-cart");
  const favoriteButton = event.target.closest(".favorite-button, .modal-favorite");
  const quantityInput = event.target.closest(".quantity-input");
  const closeButton = event.target.closest(".modal-close, .modal-backdrop");
  const lightboxClose = event.target.closest(".image-lightbox-close");
  const thumb = event.target.closest(".modal-thumb");
  const productCard = event.target.closest(".product-card");

  if (lightboxClose || event.target === imageLightbox) {
    closeImageLightbox();
    return;
  }

  if (event.target === modalMainImage) {
    openImageLightbox(modalMainImage.src, modalMainImage.alt);
    return;
  }

  if (minus && !minus.closest(".cart-drawer")) {
    event.preventDefault();
    event.stopPropagation();
    changeQuantity(minus.closest(".quantity-control"), -1);
    return;
  }

  if (plus && !plus.closest(".cart-drawer")) {
    event.preventDefault();
    event.stopPropagation();
    changeQuantity(plus.closest(".quantity-control"), 1);
    return;
  }

  if (addButton && !addButton.closest(".cart-drawer")) {
    event.preventDefault();
    event.stopPropagation();
    const modalInfo = addButton.closest(".modal-info");
    const card = addButton.closest(".product-card");
    const productId = modalInfo ? modal.dataset.productId : card.dataset.productId;
    const quantityInput = addButton.closest(".product-info, .modal-controls").querySelector(".quantity-input");
    const quantityValue = quantityInput ? quantityInput.value : "1";
    const minimum = Math.max(1, Number(quantityInput ? quantityInput.getAttribute("min") : 1));
    const quantity = Math.max(minimum, Number(quantityValue) || minimum);
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
    modalMainImage.src = thumb.dataset.image;
    document.querySelectorAll(".modal-thumb").forEach((item) => item.classList.remove("active"));
    thumb.classList.add("active");
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

  const minimum = Math.max(1, Number(quantityInput.getAttribute("min") || 1));
  quantityInput.value = String(Math.max(minimum, Number(quantityInput.value) || minimum));
  syncCardQuantity(quantityInput.closest(".quantity-control"));
});

document.addEventListener("keydown", (event) => {
  const productCard = event.target.closest ? event.target.closest(".product-card") : null;

  if (productCard && (event.key === "Enter" || event.key === " ")) {
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
