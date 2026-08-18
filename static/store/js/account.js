function openAccountDrawer(message) {
  const drawer = document.querySelector(".account-drawer");
  const messageBox = document.querySelector(".account-message");

  if (!drawer) {
    return;
  }

  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("drawer-open");

  if (messageBox && message) {
    messageBox.textContent = message;
    messageBox.hidden = false;
  }
}

window.openAccountDrawer = openAccountDrawer;

function resetRegisterVerification() {
  const registerForm = document.querySelector(".account-form-register");

  if (!registerForm) {
    return;
  }

  const codeField = registerForm.querySelector(".account-code-field");
  const codeInput = codeField ? codeField.querySelector("input") : null;
  const submitButton = registerForm.querySelector(".account-submit");

  registerForm.dataset.verification = "";
  registerForm.dataset.email = "";

  if (codeField) {
    codeField.hidden = true;
  }

  if (codeInput) {
    codeInput.value = "";
  }

  if (submitButton) {
    submitButton.textContent = "Зарегистрироваться";
  }
}

function setActiveAccountForm(name) {
  document.querySelectorAll(".account-tab").forEach((item) => item.classList.toggle("is-active", item.dataset.tab === name));
  document.querySelectorAll(".account-form").forEach((item) => item.classList.remove("is-active"));
  document.querySelector(`.account-form-${name}`)?.classList.add("is-active");
}

function showPasswordResetStep(form, email, message) {
  form.dataset.verification = "1";
  form.dataset.email = email;
  form.querySelector(".reset-code-field").hidden = false;
  form.querySelector(".reset-password-field").hidden = false;
  form.querySelector(".account-submit").textContent = "Сменить пароль";
  form.querySelector('[name="code"]').focus();
  showAccountMessage(message || "Введите код из письма и новый пароль.");
}

function openCookieModal() {
  const modal = document.querySelector(".cookie-modal");

  if (!modal) {
    return;
  }

  const savedSettings = JSON.parse(localStorage.getItem("paklineCookieSettings") || "{}");
  const analyticsInput = modal.querySelector('input[name="analytics"]');
  const marketingInput = modal.querySelector('input[name="marketing"]');

  if (analyticsInput) {
    analyticsInput.checked = Boolean(savedSettings.analytics);
  }

  if (marketingInput) {
    marketingInput.checked = Boolean(savedSettings.marketing);
  }

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("drawer-open");
}

function closeCookieModal() {
  const modal = document.querySelector(".cookie-modal");

  if (!modal) {
    return;
  }

  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("drawer-open");
}

async function postJson(url, data) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify(data),
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.error || "Не удалось выполнить действие");
  }

  return payload;
}

function formDataToObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function showAccountMessage(text, isError = false) {
  const messageBox = document.querySelector(".account-message");

  if (!messageBox) {
    return;
  }

  messageBox.textContent = text;
  messageBox.hidden = false;
  messageBox.classList.toggle("is-error", isError);
}

function formatPhone(value) {
  let digits = value.replace(/\D/g, "");

  if (digits.startsWith("8")) {
    digits = `7${digits.slice(1)}`;
  }

  if (!digits.startsWith("7")) {
    digits = `7${digits}`;
  }

  digits = digits.slice(0, 11);
  const phone = digits.slice(1);
  let result = "+7";

  if (phone.length > 0) {
    result += ` (${phone.slice(0, 3)}`;
  }

  if (phone.length >= 3) {
    result += ")";
  }

  if (phone.length > 3) {
    result += ` ${phone.slice(3, 6)}`;
  }

  if (phone.length > 6) {
    result += `-${phone.slice(6, 8)}`;
  }

  if (phone.length > 8) {
    result += `-${phone.slice(8, 10)}`;
  }

  return result;
}

function showVerificationStep(form, email, message) {
  const codeField = form.querySelector(".account-code-field");
  const submitButton = form.querySelector(".account-submit");

  form.dataset.verification = "1";
  form.dataset.email = email;

  if (codeField) {
    codeField.hidden = false;
    codeField.querySelector("input")?.focus();
  }

  if (submitButton) {
    submitButton.textContent = "Подтвердить email";
  }

  showAccountMessage(message || "Введите код из письма.");
}

document.addEventListener("input", (event) => {
  const phoneInput = event.target.closest('input[name="phone"]');

  if (!phoneInput) {
    return;
  }

  phoneInput.value = formatPhone(phoneInput.value);
});

document.addEventListener("submit", async (event) => {
  const loginForm = event.target.closest(".account-form-login");
  const registerForm = event.target.closest(".account-form-register");
  const resetForm = event.target.closest(".account-form-reset");
  const requestForm = event.target.closest(".request-form");

  if (loginForm || registerForm) {
    event.preventDefault();
    const form = loginForm || registerForm;
    const data = formDataToObject(form);
    const isVerification = registerForm && registerForm.dataset.verification === "1";
    const url = loginForm ? "/account/login/" : isVerification ? "/account/verify/" : "/account/register/";
    const payload = isVerification ? { email: registerForm.dataset.email || data.email, code: data.code } : data;

    try {
      const response = await postJson(url, payload);

      if (response.verification_required && registerForm) {
        showVerificationStep(registerForm, data.email, response.message);
        return;
      }

      showAccountMessage(isVerification ? "Email подтверждён. Сейчас обновим страницу." : "Готово. Сейчас обновим страницу.");
      window.location.reload();
    } catch (error) {
      showAccountMessage(error.message, true);
    }
  }

  if (requestForm) {
    event.preventDefault();
    const message = requestForm.querySelector(".request-message");

    try {
      const payload = await postJson("/requests/create/", formDataToObject(requestForm));
      requestForm.reset();
      if (message) {
        message.textContent = payload.message || "Заявка сохранена.";
        message.hidden = false;
        message.classList.remove("is-error");
      }
    } catch (error) {
      if (message) {
        message.textContent = error.message;
        message.hidden = false;
        message.classList.add("is-error");
      }
    }
  }

  if (resetForm) {
    event.preventDefault();
    const data = formDataToObject(resetForm);
    const isVerification = resetForm.dataset.verification === "1";
    const url = isVerification ? "/account/password-reset/confirm/" : "/account/password-reset/";
    const payload = isVerification ? { email: resetForm.dataset.email || data.email, code: data.code, password: data.password } : { email: data.email };

    try {
      const response = await postJson(url, payload);

      if (response.verification_required) {
        showPasswordResetStep(resetForm, data.email, response.message);
        return;
      }

      showAccountMessage(response.message || "Пароль изменён. Сейчас обновим страницу.");
      window.location.reload();
    } catch (error) {
      showAccountMessage(error.message, true);
    }
  }

  const cookieForm = event.target.closest(".cookie-form");

  if (cookieForm) {
    event.preventDefault();
    localStorage.setItem(
      "paklineCookieSettings",
      JSON.stringify({
        necessary: true,
        analytics: cookieForm.elements.analytics.checked,
        marketing: cookieForm.elements.marketing.checked,
        updatedAt: new Date().toISOString(),
      })
    );
    closeCookieModal();
  }
});

document.addEventListener("click", async (event) => {
  const cookieButton = event.target.closest(".js-cookie-settings");
  const cookieClose = event.target.closest(".cookie-close, .cookie-backdrop");
  const cookieSaveAll = event.target.closest(".cookie-save-all");
  const logoutButton = event.target.closest(".account-logout");
  const resetOpen = event.target.closest(".account-reset-open");
  const backLogin = event.target.closest(".account-back-login");

  if (cookieButton) {
    openCookieModal();
    return;
  }

  if (cookieClose) {
    closeCookieModal();
    return;
  }

  if (cookieSaveAll) {
    const form = cookieSaveAll.closest(".cookie-form");

    if (form) {
      form.elements.analytics.checked = true;
      form.elements.marketing.checked = true;
      form.requestSubmit();
    }

    return;
  }

  const accountTab = event.target.closest(".account-tab");

  if (accountTab && accountTab.dataset.tab !== "register") {
    resetRegisterVerification();
  }

  if (resetOpen) {
    setActiveAccountForm("reset");
    showAccountMessage("Введите email аккаунта — отправим код для смены пароля.");
    return;
  }

  if (backLogin) {
    setActiveAccountForm("login");
    return;
  }

  if (!logoutButton) {
    return;
  }

  await postJson("/account/logout/", {});
  window.location.reload();
});
