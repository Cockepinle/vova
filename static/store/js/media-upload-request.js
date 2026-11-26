window.uploadManagementMedia = async (data, csrf) => {
  let response;
  try {
    response = await fetch(document.body.dataset.mediaUploadApi, {
      method: "POST", credentials: "same-origin", mode: "same-origin",
      headers: {"X-CSRFToken": csrf}, body: data,
    });
  } catch {
    throw new Error("Сервер не подтвердил загрузку. Проверьте соединение и медиатеку перед повтором.");
  }
  if (response.status === 413) throw new Error("Запрос слишком большой. Выберите файл меньшего размера.");
  if (response.redirected || response.status === 401) throw new Error("Сессия истекла. Войдите повторно.");
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.id) {
    throw new Error(result.error || (response.status === 403
      ? "Доступ запрещён. Обновите страницу после повторного входа."
      : `Сервер не подтвердил загрузку (HTTP ${response.status}).`));
  }
  return result;
};
