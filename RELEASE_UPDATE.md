# Безопасное обновление опубликованного PakLine CMS

В репозитории точка входа Vercel — `vova/wsgi.py`, production использует Django и PostgreSQL. Локальная ветка и ветка по умолчанию на GitHub называются `main`. Перед выпуском сверьте в существующем проекте Vercel подключённый репозиторий, Production Branch, домены, текущий коммит и Build Command. Сохраните идентификатор текущего стабильного деплоя и проверьте, что он доступен для отката.

## Перед выпуском

1. Сделайте резервную копию PostgreSQL средствами провайдера либо через `pg_dump` к прямому соединению. Проверьте восстановление в отдельной базе. Сохраните копию файлов постоянного тома и проверьте резервное копирование или версионирование файлов Cloudinary. Зафиксируйте дату и точку восстановления, храните копии вне GitHub.
2. Проверьте настройки Preview. Используйте отдельную базу или ветку PostgreSQL, отдельное тестовое медиахранилище и тестовую почту. Формы, импорт, удаление и оформление заказов в Preview должны работать с тестовыми данными.
3. Проверьте настройки Production в панели хостинга. Сохраните действующий `SECRET_KEY`, чтобы не обрывать сессии. Нужны `DATABASE_URL`, `CLOUDINARY_URL` и фактические домены через `ALLOWED_HOSTS` без схемы и пути. `DEBUG=0`. В `CSRF_TRUSTED_ORIGINS` указывайте только доверенные HTTPS-источники, если приложение реально принимает запросы с другого origin. Vercel передаёт собственные адреса через `VERCEL_URL`, `VERCEL_BRANCH_URL` и `VERCEL_PROJECT_PRODUCTION_URL`. При отключённых системных переменных добавьте нужный адрес явно.
4. Для почты сверьте `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL` и `MANAGER_EMAIL`. Ключи и пароли хранятся в панели хостинга или менеджере секретов.
5. Убедитесь, что HTTPS и заголовок прокси `X-Forwarded-Proto` работают на каждом домене. В production Django перенаправляет HTTP на HTTPS. Если включаете HSTS, начните с `SECURE_HSTS_SECONDS=3600` после проверки HTTPS. Настройки поддоменов и preload требуют отдельной проверки.

## Ветка и Preview

Команды выполняются в существующем репозитории. Если `origin/main` продвинулся, сначала согласуйте изменения и разрешите конфликты на релизной ветке.

```powershell
git fetch origin
git status --short
git log --oneline --left-right HEAD...origin/main
git switch -c release/pakline-audit
git add -- .env.example DEPLOY_FREE.md RELEASE_UPDATE.md build_files.sh requirements.txt static/store store templates tests vova
git diff --cached --check
git diff --cached --name-only
git commit -m "Prepare PakLine CMS release"
git push -u origin release/pakline-audit
```

Проверьте staged diff перед коммитом. `.env`, база SQLite, резервные копии, файлы из `media/` и результаты `collectstatic` остаются вне коммита. Откройте PR в подтверждённую production-ветку и дождитесь успешного Preview. Слияние в production-ветку обычно запускает публикацию на Vercel. Сливайте PR только после явного согласования выпуска.

## Сборка, схема и медиа

На изолированной среде проверяйте следующую последовательность. Для `collectstatic` используйте рабочую папку Preview или отдельный `STATIC_ROOT`. Скрипт `build_files.sh` устанавливает зависимости и собирает статику при вызове из настроенного Build Command.

```text
python -m pip install -r requirements.txt
python -m pip check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py collectstatic --noinput
```

Это обновление не добавляет миграций. Если проверка production-схемы показывает старые неприменённые миграции, сверяйте их с рабочим деплоем и отдельно согласуйте план после резервной копии. Команда `migrate --plan` показывает план. Команду `migrate` в задачу автоматической сборки не добавляйте.

Новые файлы на Vercel записываются в Cloudinary. Для старых файлов с относительными путями скопируйте публичные оригиналы на постоянный HTTPS-источник с сохранением путей. Укажите базовый URL источника в `MEDIA_URL`, например `https://media.example.ru/`. Тогда старые адреса `/media/…` будут перенаправлены. Сверьте список ссылок и копируйте только предназначенные для публикации файлы. Рабочие пути в базе и имеющиеся экземпляры файлов сохраните. При размещении на сервере с постоянным диском следуйте настройке тома и выдачи `MEDIA_URL` в [DEPLOY_FREE.md](DEPLOY_FREE.md).

## Публикация и контроль

1. В Preview на телефоне и компьютере проверьте вход и выход, доступ обычного пользователя к закрытым страницам, списки и карточки CMS, поиск, фильтры, галерею, корзину и оформление заказа. Проверьте PNG, JPEG и WebP, отказ для SVG, сохранение формы, замену медиафайла и открытие оригинала по HTTPS. Проверьте, что контрольный файл остаётся доступен после нового деплоя Preview.
2. После согласования опубликуйте через PR. На Vercel переключение деплоя заменяет приложение. Для отдельного управляемого сервера используйте существующий процесс выкладки и перезапуска после настройки окружения и сборки статики.
3. На настоящем домене проверьте HTTPS, статику, вход сотрудника, закрытые маршруты, прежние миниатюры и их оригиналы, карточки сотрудника и запроса, навигацию каталога и отсутствие всплеска HTTP 403/500. Проверки записи выполняйте по согласованным тестовым данным.

## Откат

Если новый деплой выдаёт 500, блокирует вход или ломает оформление заказа, верните стабильный deployment через Vercel Instant Rollback. Он возвращает сборку и её окружение. Сверьте доступность прежнего источника медиафайлов. В GitHub подготовьте обратный PR к релизному коммиту через Revert. Проверьте состояние назначения production-доменов перед следующей публикацией. Используйте обычный push релизной ветки.

Откат приложения сохраняет текущую PostgreSQL и медиа. Для этого релиза обратных миграций нет. Восстановление базы затрагивает записи после точки восстановления и требует отдельного решения. Не возвращайте старую версию к обработке незавершённых регистраций, начатых на новой сборке: старый код не понимает новый формат подтверждения. На время возврата отключите завершение регистрации или согласованно аннулируйте только неиспользованные коды нового формата и предложите запросить новые. Аккаунты, которые успели зарегистрироваться, хранят стандартные хеши Django.

## Состав обновления

Список рабочего дерева включает накопленные этапы и финальное усиление безопасности. Проверяйте его перед сохранением коммита через `git diff --cached --name-only`.

- **Корень** · `.env.example`, `DEPLOY_FREE.md`, `build_files.sh`, `requirements.txt`, `RELEASE_UPDATE.md`
- **static/store** · `static/store/css/management.css`, `static/store/css/responsive.css`, `static/store/js/account.js`, `static/store/js/cart.js`, `static/store/js/management.js`, `static/store/js/media-picker.js`, `static/store/js/responsive.js`, `static/store/js/variant-groups.js`, `static/store/css/django-admin-responsive.css`, `static/store/js/field-editor.js`, `static/store/js/image-upload.js`
- **store/cms** · `store/cms/__init__.py`, `store/cms/categories.py`, `store/cms/common.py`, `store/cms/content.py`, `store/cms/customers.py`, `store/cms/management.py`, `store/cms/products.py`, `store/cms/variant_groups.py`
- **store/cms_forms.py** · `store/cms_forms.py`
- **store/cms_views.py** · `store/cms_views.py`
- **store/media_storage.py** · `store/media_storage.py`
- **store/models** · `store/models/content.py`
- **store/services** · `store/services/accounts.py`
- **store/templatetags** · `store/templatetags/store_extras.py`
- **store/test_audit.py** · `store/test_audit.py`
- **store/urls.py** · `store/urls.py`
- **store/views** · `store/views/account.py`, `store/views/cart.py`
- **templates/store** · `templates/store/catalog.html`, `templates/store/contacts.html`, `templates/store/custom_page.html`, `templates/store/document.html`, `templates/store/home.html`, `templates/store/promotions.html`, `templates/store/team.html`
- **templates/store/management** · `templates/store/management/base.html`, `templates/store/management/category_list.html`, `templates/store/management/content_image_field.html`, `templates/store/management/employee_form.html`, `templates/store/management/employee_list.html`, `templates/store/management/field_form.html`, `templates/store/management/field_list.html`, `templates/store/management/login.html`, `templates/store/management/media_library.html`, `templates/store/management/product_list.html`, `templates/store/management/request_detail.html`, `templates/store/management/request_list.html`, `templates/store/management/variant_group_form.html`, `templates/store/management/variant_group_list.html`, `templates/store/management/employee_detail.html`, `templates/store/management/field_editor_input.html`, `templates/store/management/field_editor_toggle.html`
- **templates/store/partials** · `templates/store/partials/cart_drawer.html`, `templates/store/partials/cookie_modal.html`, `templates/store/partials/header.html`, `templates/store/partials/user_drawers.html`
- **vova/settings.py** · `vova/settings.py`
- **vova/urls.py** · `vova/urls.py`
- **store/test_catalog_configuration.py** · `store/test_catalog_configuration.py`
- **store/test_management_records.py** · `store/test_management_records.py`
- **store/test_media_uploads.py** · `store/test_media_uploads.py`
- **store/test_release_security.py** · `store/test_release_security.py`
- **store/uploads.py** · `store/uploads.py`
- **templates/admin** · `templates/admin/base_site.html`
- **tests/responsive_routes.py** · `tests/responsive_routes.py`
