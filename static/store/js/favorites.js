const favoriteProductIds = new Set(
  Array.from(document.querySelectorAll(".favorite-button.is-active")).map((button) => {
    const item = button.closest("[data-product-id]");
    return item ? item.dataset.productId : "";
  }).filter(Boolean),
);

function updateFavoriteCounts(count) {
  document.querySelectorAll(".favorite-count").forEach((item) => {
    item.textContent = String(count);
    item.hidden = count === 0;
  });
}

function renderFavoriteDrawer(items) {
  const container = document.querySelector(".favorite-items");

  if (!container) {
    return;
  }

  if (!items.length) {
    container.innerHTML = `
      <div class="drawer-empty">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 0 1 12 6a5 5 0 0 1 7.5 6.6Z"/></svg>
        <p>Нет избранных товаров</p>
      </div>
    `;
    return;
  }

  const template = document.querySelector("[data-favorite-card]");
  container.replaceChildren(...items.map(product => {
    const card = template.content.firstElementChild.cloneNode(true);
    card.dataset.productId = product.id;
    card.dataset.product = JSON.stringify(product);
    card.querySelector(".favorite-photo").src = product.image;
    const link = card.querySelector(".favorite-product-link");
    link.href = product.url;
    link.textContent = product.name;
    const sku = card.querySelector(".favorite-sku");
    sku.textContent = product.sku;
    sku.hidden = !product.sku;
    const attributes = card.querySelector(".favorite-attributes");
    const hiddenSpecs = new Set(["Артикул", "Категория", "Наличие", "На складе", "Минимальный заказ", "НДС"]);
    attributes.replaceChildren(...(Array.isArray(product.specs) ? product.specs : [])
      .filter(([label]) => label && !hiddenSpecs.has(label))
      .map(([label, value]) => {
        const detail = document.createElement("span");
        const name = document.createElement("strong");
        name.textContent = label + ": ";
        detail.append(name, document.createTextNode(value));
        return detail;
      }));
    card.querySelector(".favorite-price").textContent = product.price + " ₽";
    card.querySelector(".favorite-unit").textContent = "/ " + product.unit;
    const input = card.querySelector(".quantity-input");
    input.min = product.min_quantity || 1;
    input.step = product.quantity_step || 1;
    input.value = input.min;
    const add = card.querySelector(".favorite-add-cart");
    add.toggleAttribute("data-purchase-disabled", !product.can_purchase);
    card.querySelectorAll(".favorite-quantity input, .favorite-quantity button").forEach(control => {
      control.disabled = !product.can_purchase;
    });
    return card;
  }));
  syncFavoriteCart();
}

function syncFavoriteCart() {
  document.querySelectorAll(".favorite-item").forEach(card => {
    const quantity = window.getProductCartQuantity(card.dataset.productId);
    const remove = card.querySelector(".favorite-remove-cart");
    const add = card.querySelector(".favorite-add-cart");
    const input = card.querySelector(".quantity-input");
    if (quantity || !remove.hidden) input.value = String(quantity || input.min);
    remove.hidden = !quantity;
    const unavailable = add.hasAttribute("data-purchase-disabled");
    const text = quantity ? "В корзине" : unavailable ? "Нет в наличии" : "В корзину";
    if (!add.hasAttribute("aria-busy")) add.textContent = text;
    add.disabled = unavailable || Boolean(quantity);
  });
}

window.syncFavoriteCart = syncFavoriteCart;
syncFavoriteCart();

function setFavoriteState(productId, isFavorite) {
  if (isFavorite) {
    favoriteProductIds.add(productId);
  } else {
    favoriteProductIds.delete(productId);
  }

  document.querySelectorAll(`[data-product-id="${productId}"] .favorite-button`).forEach((button) => {
    if (button.closest("[data-product-id]").dataset.productId !== String(productId)) return;
    button.classList.toggle("is-active", isFavorite);
    if (button.hasAttribute("aria-pressed")) button.setAttribute("aria-pressed", String(isFavorite));
    if (button.classList.contains("cart-favorite")) {
      const label = isFavorite ? "Убрать из избранного" : "Добавить в избранное";
      button.setAttribute("aria-label", label);
      button.title = label;
    }
  });

  const modal = document.querySelector(".product-modal");
  const modalFavorite = document.querySelector(".modal-favorite");

  if (modal && modal.dataset.productId === productId && modalFavorite) {
    modalFavorite.classList.toggle("is-active", isFavorite);
    modalFavorite.setAttribute("aria-pressed", String(isFavorite));
  }
}

function getFavoriteProductId(button) {
  const modal = button.closest(".product-modal");

  if (modal) {
    return modal.dataset.productId;
  }

  const card = button.closest("[data-product-id]");

  return card ? card.dataset.productId : "";
}

let favoriteActionPending = false;

async function toggleFavorite(productId, button) {
  if (!productId || favoriteActionPending) return;

  if (!window.isAuthenticated && typeof window.openAccountDrawer === "function") {
    window.openAccountDrawer("Войдите или зарегистрируйтесь, чтобы добавить товар в избранное.");
    return;
  }

  const wasFavorite = favoriteProductIds.has(String(productId));
  const updateFavorite = async () => {
    const favorite = await postStoreAction("/favorites/toggle/", {
      product_id: productId,
      is_favorite: !wasFavorite,
    });
    setFavoriteState(favorite.product_id, favorite.is_favorite);
    updateFavoriteCounts(favorite.count);
    renderFavoriteDrawer(favorite.items);
    const message = favorite.is_favorite ? "Товар добавлен в избранное" : "Товар удалён из избранного";
    notifyStore(message);
  };

  favoriteActionPending = true;
  const restore = setStoreButtonPending(button);
  setFavoriteState(String(productId), !wasFavorite);
  try {
    await updateFavorite();
  } catch (error) {
    setFavoriteState(String(productId), wasFavorite);
    notifyStore(error.message, true);
  } finally {
    restore();
    favoriteActionPending = false;
  }
}

window.isProductFavorite = (productId) => favoriteProductIds.has(String(productId));
window.toggleFavoriteProduct = toggleFavorite;

document.addEventListener("click", (event) => {
  const drawer = event.target.closest(".side-drawer");
  const closeButton = event.target.closest(".drawer-close");
  const favoriteRemove = event.target.closest(".favorite-remove");
  const favoriteAddCart = event.target.closest(".favorite-add-cart");
  const favoriteRemoveCart = event.target.closest(".favorite-remove-cart");
  const button = event.target.closest(".favorite-button, .modal-favorite");
  const quantityButton = event.target.closest(".favorite-quantity .quantity-minus, .favorite-quantity .quantity-plus");

  if (event.target.closest(".js-favorites-open")) {
    if (!window.isAuthenticated && typeof window.openAccountDrawer === "function") {
      window.openAccountDrawer("Войдите или зарегистрируйтесь, чтобы открыть избранное.");
      return;
    }

    openStoreSideDrawer(document.querySelector(".favorites-drawer"));
    return;
  }

  if (event.target.closest(".js-account-open")) {
    openAccountDrawer();
    return;
  }

  if (closeButton || (drawer && event.target === drawer && !matchMedia("(min-width: 721px)").matches)) {
    closeStoreSideDrawers();
    return;
  }

  if (favoriteRemove) {
    const item = favoriteRemove.closest("[data-product-id]");
    toggleFavorite(item.dataset.productId, favoriteRemove);
    return;
  }

  if (quantityButton) {
    const control = quantityButton.closest(".favorite-quantity");
    const input = control.querySelector(".quantity-input");
    const minimum = Math.max(1, Number(input.getAttribute("min") || 1));
    const step = Math.max(1, Number(input.getAttribute("step") || 1));
    const current = normalizeQuantityValue(input.value, minimum, step);
    const next = quantityButton.classList.contains("quantity-plus")
      ? current + step
      : Math.max(minimum, current - step);
    input.value = String(next);
    const productId = control.closest("[data-product-id]").dataset.productId;
    if (window.getProductCartQuantity(productId)) window.setProductCartQuantity(productId, next, quantityButton, input);
    return;
  }

  if (favoriteRemoveCart) {
    const card = favoriteRemoveCart.closest("[data-product-id]");
    window.setProductCartQuantity(card.dataset.productId, 0, favoriteRemoveCart).then(() => {
      if (favoriteRemoveCart.hidden && document.activeElement === document.body && card.getClientRects().length) {
        card.querySelector(".favorite-add-cart:not(:disabled), .favorite-product-link")?.focus();
      }
    });
    return;
  }

  if (favoriteAddCart) {
    const item = favoriteAddCart.closest("[data-product-id]");
    const input = item.querySelector(".favorite-quantity .quantity-input");
    const quantity = normalizeQuantityValue(input?.value, input?.min, input?.step);
    if (input) input.value = String(quantity);

    if (typeof window.addProductToCart === "function") {
      window.addProductToCart(item.dataset.productId, quantity, favoriteAddCart).finally(syncFavoriteCart);
    }

    return;
  }

  const favoriteItem = event.target.closest(".favorite-item");

  if (favoriteItem && !event.target.closest("a, button, input, .quantity-control")) {
    const product = JSON.parse(favoriteItem.dataset.product);

    if (typeof window.openProductDetails === "function") {
      openProductDetails(product);
    } else {
      window.location.href = `/catalog/?product=${encodeURIComponent(product.id)}`;
    }

    return;
  }

  if (!button) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  toggleFavorite(getFavoriteProductId(button), button);
});

document.addEventListener("click", (event) => {
  const tab = event.target.closest(".account-tab");

  if (!tab) {
    return;
  }

  document.querySelectorAll(".account-tab").forEach((item) => item.classList.remove("is-active"));
  document.querySelectorAll(".account-form").forEach((item) => item.classList.remove("is-active"));
  tab.classList.add("is-active");
  document.querySelector(`.account-form-${tab.dataset.tab}`).classList.add("is-active");
});

document.addEventListener("change", event => {
  const input = event.target.closest(".favorite-quantity .quantity-input");
  if (!input) return;
  const productId = input.closest("[data-product-id]").dataset.productId;
  const quantity = normalizeQuantityValue(input.value, input.min, input.step);
  input.value = String(quantity);
  if (window.getProductCartQuantity(productId)) window.setProductCartQuantity(productId, quantity, null, input);
});

const favoriteCount = document.querySelector(".favorite-count");
updateFavoriteCounts(Number(favoriteCount ? favoriteCount.textContent : "0"));
