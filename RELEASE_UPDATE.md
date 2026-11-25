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
git add -- .env.example DEPLOY_FREE.md RELEASE_UPDATE.md build_files.sh requirements.txt static/store store templates tests vercel.json vova
git diff --cached --check
git diff --cached --name-only
git commit -m "Prepare PakLine CMS release"
git push -u origin release/pakline-audit
```

Проверьте staged diff перед коммитом. `.env`, база SQLite, резервные копии, файлы из `media/` и результаты `collectstatic` остаются вне коммита. Откройте PR в подтверждённую production-ветку и дождитесь успешного Preview. Слияние в production-ветку обычно запускает публикацию на Vercel. Сливайте PR только после явного согласования выпуска.

## Сборка, схема и медиа

В существующем проекте Vercel проверьте Root Directory (папка с `manage.py`), ветку `main`, домены и переменные Production. Снимите переопределения Build Command, Install Command и Output Directory, если они заданы для прежней сборки. Нативная сборка Django находит `vova/wsgi.py` через `WSGI_APPLICATION`, устанавливает `requirements.txt`, запускает `collectstatic` и публикует `/static/` через CDN. `build_files.sh` оставлен для ручной сборки в других окружениях. [Документация Vercel о Django](https://vercel.com/docs/frameworks/full-stack/django#serving-static-assets)

На изолированной PostgreSQL проверьте следующую последовательность.

```text
python -m pip install -r requirements.txt
python -m pip check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py collectstatic --noinput
```

Миграция `0042` добавляет `store_product.variant_sort_order` со значением 0 для существующих товаров. `0043` восстанавливает отсутствующий столбец, если `0042` уже записана в истории, и устанавливает постоянный SQL DEFAULT 0. Для уже заполненного столбца сохраняются текущие значения.

### Этап миграции Production

1. В Production → Branch Tracking отключите Auto-assign Custom Production Domains до отправки изменений в `main`. Проверьте, какой deployment обслуживает `vova-xi.vercel.app`, и после сборки убедитесь, что новый deployment имеет статус Staged, а публичный домен по-прежнему ведёт на прежний. Если автоматическое назначение нельзя отключить в панели, используйте привязанный к существующему проекту CLI и `vercel deploy --prod --skip-domain`, сохраняя блокировку автоматического выпуска из Git на время операции. [Документация Vercel о staged deployment](https://vercel.com/docs/deployments/promoting-a-deployment)
2. Сверьте список проектов и окружений Vercel, подключённых к репозиторию, и назначения их `DATABASE_URL`. Назначьте одного исполнителя релиза для общей PostgreSQL. Все изменения схемы этого приложения должны проходить через `release_migrate --apply`. Команда удерживает advisory lock на соединении PostgreSQL и завершает попытку, если блокировка уже занята. Блокировка общая для прямых подключений к одной базе и действует для исполнителей, запускающих эту команду. Для операции нужен прямой endpoint без transaction pooling. Для Neon возьмите строку подключения с выключенным Connection pooling.
3. Убедитесь, что у вас есть проверенная резервная копия именно этой PostgreSQL. Снимите свежий snapshot у провайдера либо выполните `pg_dump` с прямым подключением и проверьте восстановление в отдельной базе. Для команды ниже задайте параметры прямого подключения через `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGSSLMODE`, а пароль передайте через защищённый `PGPASSFILE`. Архив сохраните вне репозитория. Выполняйте команду `release_migrate` из того же коммита, который собран в Staged. Передайте ему прямой URI через переменную окружения `DATABASE_URL` из менеджера секретов. Сверьте базу и схему с настройками Production до применения.

   ```text
   pg_dump --format=custom --file=vova-before-release.dump
   pg_restore --list vova-before-release.dump
   python manage.py showmigrations
   python manage.py release_migrate
   ```

4. При отсутствии столбца ожидается либо `0042` и `0043` (если `0042` не записана), либо только `0043` (если `0042` записана). Если обнаружилась другая комбинация, например `0042` не записана при уже существующем столбце или в плане есть неожиданные старые миграции, разберите расхождение до запуска. Для этого аварийного релиза проведите этап в окне обслуживания, если версию до `0042` по-прежнему используют для записи товаров: между двумя миграциями старый код может столкнуться с ограничением NOT NULL.

   ```text
   python manage.py release_migrate --apply
   python manage.py release_migrate
   ```

5. Продолжайте после сообщений о наличии таблиц и столбцов и пустом плане. На URL staged deployment проверьте главную, каталог, вход сотрудника и `/management/`, CSS, JavaScript, `/favicon.ico` и доступность прежних файлов. Затем выберите **Promote to Production** для этого deployment и повторите проверки на публичном домене. При ошибке миграции или smoke-проверки оставьте релиз в Staged до выяснения причины. Выполняйте тот же порядок при последующих изменениях схемы. Для миграций, несовместимых с работающим приложением, требуется совместимое обновление в несколько релизов либо окно обслуживания.

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
