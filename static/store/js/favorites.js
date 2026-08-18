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

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
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

  container.innerHTML = items
    .map(
      (product) => `
        <article class="favorite-item" data-product-id="${escapeHtml(product.id)}" data-product='${escapeHtml(JSON.stringify(product))}'>
          <img src="${escapeHtml(product.image)}" alt="">
          <div>
            <span>${escapeHtml(product.sku)}</span>
            <h3>${escapeHtml(product.name)}</h3>
            <p>${product.price} ₽ / ${escapeHtml(product.unit)}</p>
            <div class="favorite-actions">
              <div class="quantity-control favorite-quantity" aria-label="Количество">
                <button class="quantity-minus" type="button" aria-label="Уменьшить количество">−</button>
                <input class="quantity-input" type="number" min="${escapeHtml(product.min_quantity || 1)}" step="${escapeHtml(product.min_quantity || 1)}" value="${escapeHtml(product.min_quantity || 1)}" aria-label="Количество товара">
                <button class="quantity-plus" type="button" aria-label="Увеличить количество">+</button>
              </div>
              <button class="favorite-add-cart" type="button">В корзину</button>
            </div>
          </div>
          <button class="favorite-button favorite-remove is-active" type="button" aria-label="Убрать из избранного">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 0 1 12 6a5 5 0 0 1 7.5 6.6Z"/></svg>
          </button>
        </article>
      `,
    )
    .join("");
}

function setFavoriteState(productId, isFavorite) {
  if (isFavorite) {
    favoriteProductIds.add(productId);
  } else {
    favoriteProductIds.delete(productId);
  }

  document.querySelectorAll(`[data-product-id="${productId}"] .favorite-button`).forEach((button) => {
    button.classList.toggle("is-active", isFavorite);
  });

  const modal = document.querySelector(".product-modal");
  const modalFavorite = document.querySelector(".modal-favorite");

  if (modal && modal.dataset.productId === productId && modalFavorite) {
    modalFavorite.classList.toggle("is-active", isFavorite);
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

async function toggleFavorite(productId, button) {
  if (!productId) {
    return;
  }

  if (!window.isAuthenticated && typeof window.openAccountDrawer === "function") {
    window.openAccountDrawer("Войдите или зарегистрируйтесь, чтобы добавить товар в избранное.");
    return;
  }

  button.disabled = true;

  const response = await fetch("/favorites/toggle/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({
      product_id: productId,
    }),
  });

  button.disabled = false;

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    if (error.auth_required && typeof window.openAccountDrawer === "function") {
      window.openAccountDrawer(error.error);
    }
    return;
  }

  const favorite = await response.json();
  setFavoriteState(favorite.product_id, favorite.is_favorite);
  updateFavoriteCounts(favorite.count);
  renderFavoriteDrawer(favorite.items);
}

window.isProductFavorite = (productId) => favoriteProductIds.has(String(productId));
window.toggleFavoriteProduct = toggleFavorite;

document.addEventListener("click", (event) => {
  const drawer = event.target.closest(".side-drawer");
  const closeButton = event.target.closest(".drawer-close");
  const favoriteRemove = event.target.closest(".favorite-remove");
  const favoriteAddCart = event.target.closest(".favorite-add-cart");
  const button = event.target.closest(".favorite-button, .modal-favorite");
  const quantityButton = event.target.closest(".favorite-quantity .quantity-minus, .favorite-quantity .quantity-plus");

  if (event.target.closest(".js-favorites-open")) {
    if (!window.isAuthenticated && typeof window.openAccountDrawer === "function") {
      window.openAccountDrawer("Войдите или зарегистрируйтесь, чтобы открыть избранное.");
      return;
    }

    document.querySelector(".favorites-drawer").classList.add("is-open");
    document.querySelector(".favorites-drawer").setAttribute("aria-hidden", "false");
    document.body.classList.add("drawer-open");
    return;
  }

  if (event.target.closest(".js-account-open")) {
    document.querySelector(".account-drawer").classList.add("is-open");
    document.querySelector(".account-drawer").setAttribute("aria-hidden", "false");
    document.body.classList.add("drawer-open");
    return;
  }

  if (closeButton || (drawer && event.target === drawer)) {
    document.querySelectorAll(".side-drawer").forEach((item) => {
      item.classList.remove("is-open");
      item.setAttribute("aria-hidden", "true");
    });
    document.body.classList.remove("drawer-open");
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
    const step = Math.max(1, Number(input.getAttribute("step") || minimum));
    const delta = quantityButton.classList.contains("quantity-plus") ? step : -step;
    input.value = String(Math.max(minimum, Number(input.value || minimum) + delta));
    return;
  }

  if (favoriteAddCart) {
    const item = favoriteAddCart.closest("[data-product-id]");
    const input = item.querySelector(".favorite-quantity .quantity-input");
    const minimum = Math.max(1, Number(input ? input.getAttribute("min") : 1));
    const quantity = Math.max(minimum, Number(input ? input.value : minimum) || minimum);

    if (typeof window.addProductToCart === "function") {
      window.addProductToCart(item.dataset.productId, quantity, favoriteAddCart);
    }

    return;
  }

  const favoriteItem = event.target.closest(".favorite-item");

  if (favoriteItem && !event.target.closest("button, input, .quantity-control")) {
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

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll(".side-drawer").forEach((item) => {
      item.classList.remove("is-open");
      item.setAttribute("aria-hidden", "true");
    });
    document.body.classList.remove("drawer-open");
  }
});

const favoriteCount = document.querySelector(".favorite-count");
updateFavoriteCounts(Number(favoriteCount ? favoriteCount.textContent : "0"));
