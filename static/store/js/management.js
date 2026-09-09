function formatRussianPhone(value) {
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

document.addEventListener("input", (event) => {
  const phoneInput = event.target.closest(".js-phone-mask");
  const fileInput = event.target.closest(".fancy-file input[type='file']");
  const gallerySelectAll = event.target.closest(".js-select-gallery");

  if (phoneInput) {
    phoneInput.value = formatRussianPhone(phoneInput.value);
  }

  if (fileInput) {
    const fileName = fileInput.closest(".fancy-file").querySelector(".file-name");
    const count = fileInput.files.length;

    if (fileName) {
      fileName.textContent = count ? `Выбрано файлов: ${count}` : "Файлы не выбраны";
    }
  }

  if (gallerySelectAll) {
    document.querySelectorAll('[name="delete_images"]').forEach((checkbox) => {
      checkbox.checked = gallerySelectAll.checked;
    });
  }
});

// Preserve column context when tables stack into mobile records.
document.querySelectorAll('.mgmt-table').forEach(table => {
  const labels = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim());
  table.querySelectorAll('tbody tr').forEach(row => {
    [...row.cells].forEach((cell, index) => {
      if (cell.colSpan === 1 && labels[index]) cell.dataset.label = labels[index];
    });
  });
  table.querySelectorAll('input[type="checkbox"]').forEach(input => {
    if (!input.hasAttribute('aria-label')) input.setAttribute('aria-label', input.closest('thead') ? 'Выбрать все записи' : 'Выбрать запись');
  });
});
document.querySelectorAll('.toolbar input, .toolbar select, .bulk-bar select').forEach(input => {
  if (!input.hasAttribute('aria-label')) input.setAttribute('aria-label', input.placeholder || input.options?.[0]?.text || 'Фильтр');
});

document.querySelector('[data-add-link]')?.addEventListener('click', () => {
  const total = document.querySelector('#id_links-TOTAL_FORMS');
  const template = document.querySelector('#link-empty-form');
  document.querySelector('[data-link-forms]').insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__prefix__', total.value));
  total.value = String(Number(total.value) + 1);
});
document.querySelectorAll('[data-copy-url]').forEach(button => button.addEventListener('click', async () => {
  const url = new URL(button.dataset.copyUrl, location.origin).href;
  try { await navigator.clipboard.writeText(url); button.textContent = 'Ссылка скопирована'; }
  catch { window.prompt('Скопируйте ссылку', url); }
}));
