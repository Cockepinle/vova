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
