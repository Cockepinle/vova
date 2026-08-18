const drawer = document.querySelector(".cart-drawer");
const cartItems = drawer.querySelector(".cart-items");
const cartTitleCount = drawer.querySelector(".cart-panel-header span");
const cartTotal = drawer.querySelector(".cart-total strong");
const cartBulkActions = drawer.querySelector(".cart-bulk-actions");
const cartSelectAll = drawer.querySelector(".cart-select-all");
const cartRemoveSelected = drawer.querySelector(".cart-remove-selected");
const checkoutDrawer = document.querySelector(".checkout-drawer");
let cartProductQuantities = {};

drawer.querySelectorAll(".cart-item").forEach((item) => {
  cartProductQuantities[item.dataset.productId] = Number(item.querySelector(".cart-quantity span").textContent);
});

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function updateCartBadges(count) {
  document.querySelectorAll("#cart-count").forEach((badge) => {
    badge.textContent = String(count);
  });
}

function getMinimumQuantityFromElement(element) {
  const input = element ? element.querySelector(".quantity-input") : null;
  const minimum = Number(input ? input.getAttribute("min") : 1);

  return Math.max(1, Number.isFinite(minimum) ? minimum : 1);
}

function openCartDrawer() {
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("cart-open");
}

function openCheckoutDrawer() {
  if (!checkoutDrawer) {
    return;
  }

  const checkoutForm = checkoutDrawer.querySelector(".checkout-panel");
  const message = checkoutDrawer.querySelector(".checkout-message");
  const submitButton = checkoutDrawer.querySelector(".checkout-submit");

  if (message) {
    message.hidden = true;
    message.textContent = "";
    message.classList.remove("is-error");
  }

  if (submitButton) {
    submitButton.disabled = false;
    submitButton.textContent = "Отправить заказ";
  }

  if (checkoutForm) {
    checkoutForm.querySelector('[name="comment"]')?.focus();
    checkoutForm.querySelector('[name="full_name"]')?.focus();
  }

  checkoutDrawer.classList.add("is-open");
  checkoutDrawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("cart-open");
}

function closeCheckoutDrawer() {
  if (!checkoutDrawer) {
    return;
  }

  checkoutDrawer.classList.remove("is-open");
  checkoutDrawer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("cart-open");
}

window.openCheckoutDrawer = openCheckoutDrawer;

function updateCartBulkState() {
  const checkboxes = Array.from(drawer.querySelectorAll(".cart-select-item"));
  const selected = checkboxes.filter((checkbox) => checkbox.checked);

  if (cartBulkActions) {
    cartBulkActions.hidden = checkboxes.length === 0;
  }

  if (cartSelectAll) {
    cartSelectAll.checked = checkboxes.length > 0 && selected.length === checkboxes.length;
    cartSelectAll.indeterminate = selected.length > 0 && selected.length < checkboxes.length;
  }

  if (cartRemoveSelected) {
    cartRemoveSelected.disabled = selected.length === 0;
    cartRemoveSelected.textContent = selected.length > 0 ? `Удалить выбранные (${selected.length})` : "Удалить выбранные";
  }
}

function setCardCartState(productId, quantity) {
  document.querySelectorAll(`[data-product-id="${productId}"]`).forEach((card) => {
    const input = card.querySelector(".quantity-input");
    const button = card.querySelector(".add-to-cart");
    const isInCart = quantity > 0;
    const minimum = getMinimumQuantityFromElement(card);

    card.classList.toggle("is-in-cart", isInCart);

    if (input) {
      input.value = String(Math.max(minimum, quantity || Number(input.value) || minimum));
    }

    if (button) {
      button.textContent = isInCart ? "В корзине" : "В корзину";
      button.disabled = false;
    }
  });

  const modal = document.querySelector(".product-modal");

  if (modal && modal.dataset.productId === productId) {
    const modalButton = modal.querySelector(".modal-add");
    const modalInput = modal.querySelector(".modal-controls .quantity-input");
    const minimum = getMinimumQuantityFromElement(modal);

    if (modalButton) {
      modalButton.textContent = quantity > 0 ? "В корзине" : "В корзину";
      modalButton.disabled = false;
    }

    if (modalInput) {
      modalInput.value = String(Math.max(minimum, quantity || Number(modalInput.value) || minimum));
    }
  }
}

function syncProductCards(cart) {
  const quantities = {};

  cart.items.forEach((item) => {
    quantities[item.id] = item.quantity;
  });

  cartProductQuantities = quantities;

  document.querySelectorAll("[data-product-id]").forEach((card) => {
    const productId = card.dataset.productId;
    const isProductCard = card.classList.contains("product-card") || card.classList.contains("catalog-card");

    if (isProductCard) {
      setCardCartState(productId, quantities[productId] || 0);
    }
  });
}

function isProductFavorite(productId) {
  if (typeof window.isProductFavorite === "function") {
    return window.isProductFavorite(productId);
  }

  return Boolean(document.querySelector(`[data-product-id="${productId}"] .favorite-button.is-active`));
}

function renderCart(cart) {
  cartTitleCount.textContent = `(${cart.count})`;
  cartTotal.textContent = `${cart.total} ₽`;
  updateCartBadges(cart.count);
  syncProductCards(cart);

  if (!cart.items.length) {
    cartItems.innerHTML = '<p class="cart-empty">Корзина пуста</p>';
    updateCartBulkState();
    return;
  }

  cartItems.innerHTML = cart.items
    .map(
      (item) => `
        <article class="cart-item" data-product-id="${escapeHtml(item.id)}" data-product='${escapeHtml(JSON.stringify(item.product))}'>
          <label class="cart-select">
            <input class="cart-select-item" type="checkbox" aria-label="Выбрать товар">
          </label>
          <img src="${escapeHtml(item.image)}" alt="">
          <div class="cart-item-info">
            <div class="cart-item-title">
              <h3>${escapeHtml(item.name)}</h3>
              <p>${escapeHtml(item.sku)}</p>
            </div>
            <button class="favorite-button cart-favorite ${isProductFavorite(item.id) ? "is-active" : ""}" type="button" aria-label="Добавить в избранное">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 12.6 12 20l-7.5-7.4A5 5 0 0 1 12 6a5 5 0 0 1 7.5 6.6Z"/></svg>
            </button>
            <div class="cart-item-row">
              <div class="quantity-control cart-quantity" aria-label="Количество">
                <button class="quantity-minus" type="button" aria-label="Уменьшить количество">−</button>
                <span>${item.quantity}</span>
                <button class="quantity-plus" type="button" aria-label="Увеличить количество">+</button>
              </div>
              <strong data-price="${item.price}">${item.line_total} ₽</strong>
            </div>
          </div>
          <button class="cart-remove" type="button" aria-label="Удалить">×</button>
        </article>
      `,
    )
    .join("");
  updateCartBulkState();
}

async function refreshCartFromApi() {
  const response = await fetch("/api/cart/", {
    headers: {
      "X-Requested-With": "XMLHttpRequest",
    },
  });

  if (!response.ok) {
    return;
  }

  renderCart(await response.json());
}

async function addProductToCart(productId, quantity, button) {
  if ((button && button.closest(".is-in-cart")) || cartProductQuantities[productId] > 0) {
    openCartDrawer();
    return;
  }

  const previousText = button ? button.textContent : "";

  if (button) {
    button.disabled = true;
    button.textContent = "Добавляем";
  }

  const response = await fetch("/cart/add/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({
      product_id: productId,
      quantity,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    if (error.auth_required && typeof window.openAccountDrawer === "function") {
      window.openAccountDrawer(error.error);
    }
    if (button) {
      button.disabled = false;
      button.textContent = previousText || "В корзину";
    }
    return;
  }

  const cart = await response.json();
  renderCart(cart);
  openCartDrawer();

  if (button) {
    button.disabled = false;
    button.textContent = "В корзине";
  }
}

window.addProductToCart = addProductToCart;

async function updateProductInCart(productId, quantity) {
  if (quantity <= 0) {
    const response = await fetch("/cart/update/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({
        product_id: productId,
        quantity: 0,
      }),
    });

    if (response.ok) {
      renderCart(await response.json());
    }

    return;
  }

  const minimum = Math.max(1, Number(
    document.querySelector(`[data-product-id="${productId}"] .quantity-input`)?.getAttribute("min") || 1,
  ));
  const normalizedQuantity = Math.max(minimum, Number(quantity) || minimum);

  const response = await fetch("/cart/update/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({
      product_id: productId,
      quantity: normalizedQuantity,
    }),
  });

  if (response.ok) {
    renderCart(await response.json());
  } else {
    const error = await response.json().catch(() => ({}));
    if (error.auth_required && typeof window.openAccountDrawer === "function") {
      window.openAccountDrawer(error.error);
    }
  }
}

window.setProductCartQuantity = updateProductInCart;
window.openCartDrawer = openCartDrawer;
window.getProductCartQuantity = (productId) => cartProductQuantities[productId] || 0;
window.refreshCartFromApi = refreshCartFromApi;

async function removeSelectedCartItems() {
  const selectedIds = Array.from(drawer.querySelectorAll(".cart-select-item:checked"))
    .map((checkbox) => checkbox.closest(".cart-item"))
    .filter(Boolean)
    .map((item) => item.dataset.productId);

  if (!selectedIds.length) {
    return;
  }

  for (const productId of selectedIds) {
    await updateProductInCart(productId, 0);
  }

  updateCartBulkState();
}

document.addEventListener("click", (event) => {
  if (event.target.closest(".js-cart-open")) {
    openCartDrawer();
  }

  if (event.target.closest(".cart-close") || event.target === drawer) {
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    document.body.classList.remove("cart-open");
  }

  const cartItem = event.target.closest(".cart-item");

  if (event.target.closest(".cart-select-all")) {
    drawer.querySelectorAll(".cart-select-item").forEach((checkbox) => {
      checkbox.checked = event.target.checked;
    });
    updateCartBulkState();
    return;
  }

  if (event.target.closest(".cart-select-item")) {
    updateCartBulkState();
    return;
  }

  if (event.target.closest(".cart-remove-selected")) {
    removeSelectedCartItems();
    return;
  }

  if (event.target.closest(".cart-clear")) {
    fetch("/cart/clear/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: "{}",
    }).then(async (response) => {
      if (response.ok) {
        renderCart(await response.json());
      }
    });
    return;
  }

  if (event.target.closest(".cart-checkout, .cart-invoice")) {
    if (!cartItems.querySelector(".cart-item")) {
      return;
    }

    if (!window.isAuthenticated && typeof window.openAccountDrawer === "function") {
      sessionStorage.setItem("paklinePendingCheckout", "1");
      window.openAccountDrawer("Войдите или зарегистрируйтесь, чтобы оформить заказ. Корзина сохранится.");
      return;
    }

    if (typeof window.openCheckoutDrawer === "function") {
      window.openCheckoutDrawer();
    }

    return;
  }

  if (cartItem && event.target.closest(".cart-remove")) {
    updateProductInCart(cartItem.dataset.productId, 0);
  }

  if (cartItem && event.target.closest(".cart-drawer .quantity-minus")) {
    const value = cartItem.querySelector(".cart-quantity span");
    updateProductInCart(cartItem.dataset.productId, Math.max(1, Number(value.textContent) - 1));
  }

  if (cartItem && event.target.closest(".cart-drawer .quantity-plus")) {
    const value = cartItem.querySelector(".cart-quantity span");
    updateProductInCart(cartItem.dataset.productId, Number(value.textContent) + 1);
  }

  if (cartItem && !event.target.closest("button, input, label, .quantity-control")) {
    const product = JSON.parse(cartItem.dataset.product);

    if (typeof window.openProductDetails === "function") {
      openProductDetails(product);
    } else {
      window.location.href = `/catalog/?product=${encodeURIComponent(product.id)}`;
    }
  }
});

document.addEventListener("submit", async (event) => {
  const checkoutForm = event.target.closest(".checkout-panel");

  if (!checkoutForm) {
    return;
  }

  event.preventDefault();
  const message = checkoutForm.querySelector(".checkout-message");
  const submitButton = checkoutForm.querySelector(".checkout-submit");

  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Отправляем";
  }

  const response = await fetch("/cart/checkout/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify(Object.fromEntries(new FormData(checkoutForm).entries())),
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok && payload.auth_required && typeof window.openAccountDrawer === "function") {
    sessionStorage.setItem("paklinePendingCheckout", "1");
    closeCheckoutDrawer();
    window.openAccountDrawer(payload.error);
  }

  if (message) {
    message.hidden = false;
    message.classList.toggle("is-error", !response.ok);
    message.textContent = payload.message || payload.error || "Не удалось оформить заказ";
  }

  if (response.ok) {
    renderCart(payload.cart);
    checkoutForm.reset();
    if (submitButton) {
      submitButton.textContent = "Заказ принят";
      submitButton.disabled = true;
    }
    return;
  }

  if (submitButton) {
    submitButton.disabled = false;
    submitButton.textContent = "Отправить заказ";
  }
});

document.addEventListener("click", (event) => {
  if (event.target.closest(".checkout-close, .checkout-drawer .drawer-backdrop")) {
    closeCheckoutDrawer();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    document.body.classList.remove("cart-open");
  }
});

window.addEventListener("focus", refreshCartFromApi);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    refreshCartFromApi();
  }
});

setInterval(() => {
  if (!document.hidden) {
    refreshCartFromApi();
  }
}, 30000);

updateCartBulkState();

if (window.isAuthenticated && sessionStorage.getItem("paklinePendingCheckout") === "1") {
  sessionStorage.removeItem("paklinePendingCheckout");
  openCartDrawer();
  openCheckoutDrawer();
}
