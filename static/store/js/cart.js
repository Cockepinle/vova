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
let cartActionPending = false;
let cartRevision = 0;
let cartRefreshRequest = null;
let cartLastSync = Date.now();
let cartSnapshot = null;
let storeFeedbackTimer;

function notifyStore(message, error = false) {
  const feedback = document.querySelector("[data-store-feedback]");
  if (!feedback) return;
  clearTimeout(storeFeedbackTimer);
  feedback.dataset.error = String(error);
  feedback.replaceChildren(message);
  feedback.classList.add("is-visible");
  storeFeedbackTimer = setTimeout(() => {
    feedback.classList.remove("is-visible");
    feedback.replaceChildren();
  }, error ? 5500 : 3500);
}

function setStoreButtonPending(button) {
  if (!button) return () => {};
  const disabled = button.disabled;
  const spinner = document.createElement("i");
  spinner.className = "store-action-spinner";
  spinner.setAttribute("aria-hidden", "true");
  button.append(spinner);
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  return () => {
    spinner.remove();
    button.disabled = disabled;
    button.removeAttribute("aria-busy");
  };
}

async function postStoreAction(url, payload) {
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": checkoutDrawer.querySelector('[name="csrfmiddlewaretoken"]').value,
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Проверьте соединение и повторите попытку");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok || !data) {
    if (data?.auth_required) window.openAccountDrawer?.(data.error);
    throw new Error(data?.error || "Не удалось выполнить действие");
  }
  return data;
}

async function runCartAction(button, action) {
  if (cartActionPending) return;
  cartActionPending = true;
  cartRevision += 1;
  const restore = setStoreButtonPending(button);
  const controls = [...drawer.querySelectorAll(".cart-remove, .cart-clear, .cart-remove-selected, .cart-favorite, .cart-checkout, .cart-invoice, .cart-quantity button")]
    .filter(control => control !== button && !control.disabled);
  controls.forEach(control => { control.disabled = true; });
  try {
    await action();
    return true;
  } catch (error) {
    notifyStore(error.message, true);
    return false;
  } finally {
    restore();
    controls.forEach(control => { control.disabled = false; });
    updateCartBulkState();
    cartActionPending = false;
  }
}

function applyCartMutation(cart, options) {
  renderCart(cart, options);
  try {
    localStorage.setItem("paklineCartChange", String(Date.now()));
  } catch {
    // Cart state is still available in the active tab.
  }
}


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

function normalizeQuantityValue(value, minimum = 1, step = 1) {
  minimum = Math.max(1, Math.floor(Number(minimum) || 1));
  step = Math.max(1, Math.floor(Number(step) || 1));
  const requested = Number(value);
  const quantity = Math.max(minimum, Number.isFinite(requested) ? Math.floor(requested) : minimum);
  return minimum + Math.ceil((quantity - minimum) / step) * step;
}

function updateCartBadges(count) {
  document.querySelectorAll("#cart-count, [data-cart-count]").forEach((badge) => {
    badge.textContent = String(count);
  });
}

function openCartDrawer() {
  const favorites = document.querySelector(".favorites-drawer.is-open");
  if (favorites) {
    favorites.classList.remove("is-open");
    favorites.setAttribute("aria-hidden", "true");
    if (!document.querySelector(".side-drawer.is-open")) document.body.classList.remove("drawer-open");
  }
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("cart-open");
  refreshStaleCart();
}

async function saveCheckoutDraft() {
  if (!checkoutDrawer) return;
  const form = checkoutDrawer.querySelector(".checkout-panel");
  storeCheckoutFormDraft(form);
  if (!window.isAuthenticated) return;
  const method = form?.querySelector('input[name="payment_method"]:checked')?.value || "invoice";
  const deliveryMethod = form?.querySelector('input[name="delivery_method"]:checked')?.value || "pickup";
  const deliveryAddress = form?.querySelector('[name="delivery_address"]')?.value || "";
  const storedId = sessionStorage.getItem("paklineCheckoutOrderId") || form?.querySelector('[name="checkout_order_id"]')?.value || "";
  const csrfToken = form?.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
  let response;
  let payload;
  try {
    response = await fetch("/cart/checkout/start/", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken},
      body: JSON.stringify({payment_method: method, delivery_method: deliveryMethod, delivery_address: deliveryAddress, checkout_order_id: storedId}),
    });
    payload = await response.json().catch(() => ({}));
  } catch (error) {
    payload = {error: "Не удалось связаться с сервером. Введённые данные сохранены; проверьте соединение и повторите попытку."};
  }
  if (response?.ok && payload.checkout_order_id) {
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

function syncProductCards(cart) {
  const previous = cartProductQuantities;
  const quantities = Object.fromEntries(cart.items.map(item => [item.id, item.quantity]));
  cartProductQuantities = quantities;

  document.querySelectorAll(".product-card[data-product-id], .catalog-card[data-product-id], .product-modal[data-product-id]").forEach(card => {
    const productId = card.dataset.productId;
    const quantity = quantities[productId] || 0;
    if (quantity === (previous[productId] || 0)) return;
    const input = card.querySelector(".quantity-input");
    const button = card.querySelector(".add-to-cart");
    card.classList.toggle("is-in-cart", quantity > 0);
    if (input && !input.disabled && quantity) input.value = String(quantity);
    if (button && !button.hasAttribute("data-purchase-disabled") && (!button.disabled || button.hasAttribute("aria-busy"))) {
      button.textContent = quantity ? "В корзине" : "В корзину";
    }
  });

  document.querySelectorAll("[data-add-detail-product]:not([data-purchase-disabled])").forEach(button => {
    const productId = button.dataset.addDetailProduct;
    const quantity = quantities[productId] || 0;
    if (quantity === (previous[productId] || 0)) return;
    button.textContent = quantity ? "В корзине" : "В корзину";
    const input = button.closest(".product-detail-purchase")?.querySelector(".quantity-input");
    if (input && quantity) input.value = String(quantity);
  });
}

function isProductFavorite(productId) {
  if (typeof window.isProductFavorite === "function") {
    return window.isProductFavorite(productId);
  }

  return Boolean(document.querySelector(`[data-product-id="${productId}"] .favorite-button.is-active`));
}

function renderCart(cart, {saveDraft = true} = {}) {
  cartLastSync = Date.now();
  const snapshot = JSON.stringify(cart);
  if (snapshot === cartSnapshot) return;
  cartSnapshot = snapshot;
  const selected = new Set([...cartItems.querySelectorAll(".cart-select-item:checked")]
    .map(input => input.closest(".cart-item").dataset.productId));
  cartTitleCount.textContent = `(${cart.count})`;
  cartTotal.textContent = `${cart.total} ₽`;
  const checkoutTotal = checkoutDrawer?.querySelector("[data-checkout-total]");
  if (checkoutTotal) checkoutTotal.textContent = `${cart.total} ₽`;
  if (cartWeight) cartWeight.textContent = cart.total_weight_kg == null ? "Недостаточно данных" : `${cart.total_weight_kg} кг`;
  if (cartVolume) cartVolume.textContent = cart.total_volume_m3 == null ? "Недостаточно данных" : `${cart.total_volume_m3} м³`;
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
            <input class="cart-select-item" type="checkbox" aria-label="Выбрать товар" ${selected.has(item.id) ? "checked" : ""}>
          </label>
          <img src="${escapeHtml(item.image)}" alt="">
          <div class="cart-item-info">
            <div class="cart-item-title">
              <h3>${escapeHtml(item.name)}</h3>
              <p>${escapeHtml(item.sku)}</p>
            </div>
            <button class="favorite-button cart-favorite ${isProductFavorite(item.id) ? "is-active" : ""}" type="button" aria-pressed="${isProductFavorite(item.id)}" aria-label="${isProductFavorite(item.id) ? "Убрать из избранного" : "Добавить в избранное"}">
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
            <small class="cart-min-quantity">Мин. заказ: ${item.min_quantity} ${escapeHtml(item.unit)} · шаг ${item.product.quantity_step}</small>
          </div>
          <button class="cart-remove" type="button" aria-label="Удалить">×</button>
        </article>
      `,
    )
    .join("");
  updateCartBulkState();
  if (saveDraft && checkoutDrawer?.classList.contains("is-open") && window.isAuthenticated) {
    saveCheckoutDraft();
  }
}

function refreshCartFromApi() {
  if (cartActionPending) return;
  if (cartRefreshRequest) return cartRefreshRequest;
  const revision = cartRevision;
  cartRefreshRequest = (async () => {
    try {
      const response = await fetch("/api/cart/", {headers: {"X-Requested-With": "XMLHttpRequest"}});
      if (!response.ok) return;
      const cart = await response.json();
      if (revision === cartRevision && !cartActionPending) renderCart(cart, {saveDraft: false});
    } catch {
      // Keep the last known cart if the refresh fails.
    }
  })().finally(() => { cartRefreshRequest = null; });
  return cartRefreshRequest;
}

function refreshStaleCart() {
  if (Date.now() - cartLastSync >= 30000) refreshCartFromApi();
}

async function addProductToCart(productId, quantity, button, {replaceQuantity = false} = {}) {
  if (cartActionPending) return;
  const currentQuantity = cartProductQuantities[productId] || 0;
  if (currentQuantity && (!replaceQuantity || currentQuantity === quantity)) {
    openCartDrawer();
    return;
  }

  return runCartAction(button, async () => {
    const endpoint = currentQuantity ? "/cart/update/" : "/cart/add/";
    const {already_in_cart: alreadyInCart, ...cart} = await postStoreAction(endpoint, {product_id: productId, quantity, if_absent: true});
    applyCartMutation(cart);
    if (button) button.textContent = "В корзине";
    if (currentQuantity) {
      notifyStore("Количество обновлено");
    } else {
      notifyStore(alreadyInCart ? "Товар уже в корзине" : "Товар добавлен в корзину");
    }
    openCartDrawer();
  });
}

async function updateProductInCart(productId, quantity, button, input) {
  if (quantity > 0 && quantity === cartProductQuantities[productId]) return;
  const updated = await runCartAction(button, async () => {
    const cart = await postStoreAction("/cart/update/", {product_id: productId, quantity});
    applyCartMutation(cart);
    notifyStore(quantity ? "Количество обновлено" : "Товар удалён из корзины");
  });
  if (!updated && input) input.value = String(cartProductQuantities[productId] || input.min);
}

window.addProductToCart = addProductToCart;
window.setProductCartQuantity = updateProductInCart;
window.openCartDrawer = openCartDrawer;
window.applyRepeatedOrder = (cart) => {
  applyCartMutation(cart);
  openCartDrawer();
};
window.getProductCartQuantity = (productId) => cartProductQuantities[productId] || 0;
window.refreshCartFromApi = refreshCartFromApi;

function removeSelectedCartItems(button) {
  const productIds = [...drawer.querySelectorAll(".cart-select-item:checked")]
    .map(checkbox => checkbox.closest(".cart-item").dataset.productId);

  if (!productIds.length) return;
  return runCartAction(button, async () => {
    const cart = await postStoreAction("/cart/update/", {product_ids: productIds, quantity: 0});
    applyCartMutation(cart);
    notifyStore("Выбранные товары удалены из корзины");
  });
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
    removeSelectedCartItems(event.target.closest(".cart-remove-selected"));
    return;
  }

  const clearButton = event.target.closest(".cart-clear");
  if (clearButton) {
    runCartAction(clearButton, async () => {
      const cart = await postStoreAction("/cart/clear/", {});
      applyCartMutation(cart);
      notifyStore("Корзина очищена");
    });
    return;
  }

  if (event.target.closest(".cart-checkout, .cart-invoice")) {
    if (cartActionPending || !cartItems.querySelector(".cart-item")) {
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
    updateProductInCart(cartItem.dataset.productId, 0, event.target.closest(".cart-remove"));
  }

  if (cartItem && event.target.closest(".cart-drawer .quantity-minus")) {
    const value = cartItem.querySelector(".cart-quantity span");
    const product = JSON.parse(cartItem.dataset.product);
    const minimum = Math.max(1, Number(product.min_quantity) || 1);
    const step = Math.max(1, Number(product.quantity_step) || 1);
    updateProductInCart(cartItem.dataset.productId, Math.max(minimum, Number(value.textContent) - step), event.target.closest(".quantity-minus"));
  }

  if (cartItem && event.target.closest(".cart-drawer .quantity-plus")) {
    const value = cartItem.querySelector(".cart-quantity span");
    const product = JSON.parse(cartItem.dataset.product);
    const step = Math.max(1, Number(product.quantity_step) || 1);
    updateProductInCart(cartItem.dataset.productId, Number(value.textContent) + step, event.target.closest(".quantity-plus"));
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
  if (submitButton?.disabled) return;

  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "Отправляем";
  }

  let response;
  let payload;
  try {
    response = await fetch("/cart/checkout/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": checkoutForm.querySelector('[name="csrfmiddlewaretoken"]')?.value || "",
      },
      body: JSON.stringify(Object.fromEntries(new FormData(checkoutForm).entries())),
    });
    payload = await response.json().catch(() => ({}));
  } catch (error) {
    payload = {error: "Не удалось связаться с сервером. Введённые данные сохранены; проверьте соединение и повторите попытку."};
  }
  const requestSucceeded = Boolean(response?.ok);

  if (!requestSucceeded && payload.auth_required && typeof window.openAccountDrawer === "function") {
    sessionStorage.setItem("paklinePendingCheckout", "1");
    closeCheckoutDrawer();
    window.openAccountDrawer(payload.error);
  }

  if (message) {
    message.hidden = false;
    message.classList.toggle("is-error", !requestSucceeded);
    message.textContent = payload.message || payload.error || "Не удалось оформить заказ";
  }

  if (requestSucceeded) {
    if (deliveryLink) {
      deliveryLink.hidden = !payload.delivery_url;
      if (payload.delivery_url) deliveryLink.href = payload.delivery_url;
    }
    if (deliveryData) {
      const requestData = payload.delivery_data?.request;
      deliveryData.hidden = !requestData;
      deliveryData.querySelector("pre").textContent = requestData ? JSON.stringify(requestData, null, 2) : "";
    }
    applyCartMutation(payload.cart, {saveDraft: false});
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

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && drawer.classList.contains("is-open")) refreshStaleCart();
});
window.addEventListener("storage", (event) => {
  if (event.key !== "paklineCartChange") return;
  cartLastSync = 0;
  if (!document.hidden && drawer.classList.contains("is-open")) refreshCartFromApi();
});

updateCartBulkState();

if (window.isAuthenticated && sessionStorage.getItem("paklinePendingCheckout") === "1") {
  sessionStorage.removeItem("paklinePendingCheckout");
  openCartDrawer();
  openCheckoutDrawer();
}
