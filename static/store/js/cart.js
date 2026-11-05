const drawer = document.querySelector(".cart-drawer");
const cartItems = drawer.querySelector(".cart-items");
const cartTitleCount = drawer.querySelector(".cart-panel-header span");
const cartTotal = drawer.querySelector(".cart-total strong");
const cartWeight = drawer.querySelector("[data-cart-weight]");
const cartVolume = drawer.querySelector("[data-cart-volume]");
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
  document.querySelectorAll("#cart-count, [data-cart-count]").forEach((badge) => {
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

async function saveCheckoutDraft() {
  if (!checkoutDrawer) return;
  const form = checkoutDrawer.querySelector(".checkout-panel");
  storeCheckoutFormDraft(form);
  if (!window.isAuthenticated) return;
  const method = form?.querySelector('input[name="payment_method"]:checked')?.value || "invoice";
  const deliveryMethod = form?.querySelector('input[name="delivery_method"]:checked')?.value || "delivery";
  const deliveryAddress = form?.querySelector('[name="delivery_address"]')?.value || "";
  const storedId = sessionStorage.getItem("paklineCheckoutOrderId") || form?.querySelector('[name="checkout_order_id"]')?.value || "";
  const response = await fetch("/cart/checkout/start/", {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
    body: JSON.stringify({payment_method: method, delivery_method: deliveryMethod, delivery_address: deliveryAddress, checkout_order_id: storedId}),
  });
  const payload = await response.json().catch(() => ({}));
  if (response.ok && payload.checkout_order_id) {
    sessionStorage.setItem("paklineCheckoutOrderId", String(payload.checkout_order_id));
    const input = form?.querySelector('[name="checkout_order_id"]');
    if (input) input.value = String(payload.checkout_order_id);
  } else if (checkoutDrawer.classList.contains("is-open")) {
    const message = form?.querySelector(".checkout-message");
    if (message) {
      message.hidden = false;
      message.classList.add("is-error");
      message.textContent = payload.error || "Не удалось обновить параметры заказа";
    }
  }
}

function storeCheckoutFormDraft(form) {
  if (!form) return;
  const draft = Object.fromEntries(
    [...new FormData(form).entries()].filter(([name]) => name !== "checkout_order_id"),
  );
  try {
    sessionStorage.setItem("paklineCheckoutFormDraft", JSON.stringify(draft));
  } catch (_) {
    // Keep the checkout functional if the browser blocks session storage.
  }
}

function restoreCheckoutFormDraft(form) {
  if (!form) return;
  let draft;
  try {
    draft = JSON.parse(sessionStorage.getItem("paklineCheckoutFormDraft") || "null");
  } catch (_) {
    sessionStorage.removeItem("paklineCheckoutFormDraft");
    return;
  }
  if (!draft || typeof draft !== "object") return;
  Object.entries(draft).forEach(([name, value]) => {
    form.querySelectorAll(`[name="${CSS.escape(name)}"]`).forEach((field) => {
      if (field.type === "radio") {
        field.checked = field.value === value;
      } else {
        field.value = value;
      }
    });
  });
}

function openCheckoutDrawer(paymentMethod = "") {
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
  checkoutDrawer.querySelector(".checkout-delivery-link").hidden = true;
  checkoutDrawer.querySelector(".checkout-delivery-data").hidden = true;

  if (submitButton) {
    submitButton.disabled = false;
    submitButton.textContent = "Отправить заказ";
  }

  if (checkoutForm) {
    restoreCheckoutFormDraft(checkoutForm);
    if (paymentMethod) {
      const option = checkoutForm.querySelector(`input[name="payment_method"][value="${paymentMethod}"]`);
      if (option) option.checked = true;
    }
    const storedId = sessionStorage.getItem("paklineCheckoutOrderId");
    if (storedId) checkoutForm.querySelector('[name="checkout_order_id"]').value = storedId;
  }

  checkoutDrawer.classList.add("is-open");
  checkoutDrawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("cart-open");
  saveCheckoutDraft();
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
  const checkoutTotal = checkoutDrawer?.querySelector("[data-checkout-total]");
  if (checkoutTotal) checkoutTotal.textContent = `${cart.total} ₽`;
  if (cartWeight) cartWeight.textContent = `${cart.total_weight_kg || "0"} кг`;
  if (cartVolume) cartVolume.textContent = `${cart.total_volume_m3 || "0"} м³`;
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
                <button class="quantity-minus" type="button" aria-label="Уменьшить количество" ${Number(item.quantity) <= Math.max(1, Number(item.min_quantity) || 1) ? "disabled" : ""}>−</button>
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
  if (checkoutDrawer?.classList.contains("is-open") && window.isAuthenticated) {
    saveCheckoutDraft();
  }
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

  const cartItem = drawer.querySelector(`.cart-item[data-product-id="${productId}"]`);
  const cartProduct = cartItem ? JSON.parse(cartItem.dataset.product) : null;
  const minimum = Math.max(1, Number(
    cartProduct?.min_quantity || document.querySelector(`[data-product-id="${productId}"] .quantity-input`)?.getAttribute("min") || 1,
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
window.applyRepeatedOrder = (cart) => {
  renderCart(cart);
  openCartDrawer();
};
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
      window.openCheckoutDrawer(event.target.closest(".cart-invoice") ? "invoice" : "");
    }

    return;
  }

  if (cartItem && event.target.closest(".cart-remove")) {
    updateProductInCart(cartItem.dataset.productId, 0);
  }

  if (cartItem && event.target.closest(".cart-drawer .quantity-minus")) {
    const value = cartItem.querySelector(".cart-quantity span");
    const product = JSON.parse(cartItem.dataset.product);
    const minimum = Math.max(1, Number(product.min_quantity) || 1);
    updateProductInCart(cartItem.dataset.productId, Math.max(minimum, Number(value.textContent) - 1));
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
  const deliveryLink = checkoutForm.querySelector(".checkout-delivery-link");
  const deliveryData = checkoutForm.querySelector(".checkout-delivery-data");

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
    if (deliveryLink) {
      deliveryLink.hidden = !payload.delivery_url;
      if (payload.delivery_url) deliveryLink.href = payload.delivery_url;
    }
    if (deliveryData) {
      const requestData = payload.delivery_data?.request;
      deliveryData.hidden = !requestData;
      deliveryData.querySelector("pre").textContent = requestData ? JSON.stringify(requestData, null, 2) : "";
    }
    renderCart(payload.cart);
    sessionStorage.removeItem("paklineCheckoutOrderId");
    sessionStorage.removeItem("paklineCheckoutFormDraft");
    checkoutForm.reset();
    if (submitButton) {
      submitButton.textContent = "Заказ принят";
      submitButton.disabled = true;
    }
    if (payload.payment_url) window.location.assign(payload.payment_url);
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

document.addEventListener("change", (event) => {
  if (event.target.matches('.checkout-panel input[name="payment_method"], .checkout-panel input[name="delivery_method"], .checkout-panel input[name="delivery_address"]')) saveCheckoutDraft();
});

document.addEventListener("input", (event) => {
  const form = event.target.closest(".checkout-panel");
  if (form) storeCheckoutFormDraft(form);
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
