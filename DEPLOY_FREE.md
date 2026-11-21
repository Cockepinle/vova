# Бесплатный деплой PakLine

## Схема

- Django-сайт: Vercel.
- База данных: Neon PostgreSQL или Supabase PostgreSQL.
- Фото и файлы: Cloudinary.
- Почта: SMTP через переменные окружения.

## 1. База данных

1. Зарегистрируйтесь на https://neon.tech или https://supabase.com.
2. Создайте PostgreSQL database.
3. Скопируйте connection string в формате `postgres://...`.
4. На Vercel добавьте его как `DATABASE_URL`.

## 2. Фото товаров

1. Зарегистрируйтесь на https://cloudinary.com.
2. Скопируйте `CLOUDINARY_URL`.
3. На Vercel добавьте переменную `CLOUDINARY_URL`.

Без Cloudinary загруженные через админку фото на Vercel будут пропадать после пересборок.

Настройка Cloudinary применяется к новым загрузкам через Django `STORAGES`.
Существующие локальные записи сохраняют адреса через `MEDIA_URL`. При переходе
на Vercel отдельно перенесите локальные файлы, если для этих адресов нет
публичного файлового сервера.

На сервере с постоянным диском можно оставить файловое хранилище, задать
`MEDIA_ROOT` для каталога на постоянном томе и `MEDIA_URL` для его публичного
адреса. При `DEBUG=0` этот адрес обслуживает веб-сервер или CDN. Django
раздаёт локальные файлы по `MEDIA_URL` в режиме разработки.

## 3. Vercel

1. Загрузите проект в GitHub.
2. На https://vercel.com нажмите `Add New Project`.
3. Выберите репозиторий сайта.
4. В `Environment Variables` добавьте:
   - `DEBUG=False`
   - `SECRET_KEY`
   - `ALLOWED_HOSTS=ваш-домен.vercel.app`
   - `CSRF_TRUSTED_ORIGINS=https://ваш-домен.vercel.app`
   - `DATABASE_URL`
   - `CLOUDINARY_URL`
   - `EMAIL_HOST=smtp.gmail.com`
   - `EMAIL_PORT=587`
   - `EMAIL_USE_TLS=1`
   - `EMAIL_HOST_USER`
   - `EMAIL_HOST_PASSWORD`
   - `DEFAULT_FROM_EMAIL`
   - `MANAGER_EMAIL`
5. Нажмите `Deploy`.

## 4. Миграции

После первого деплоя нужно выполнить миграции для новой PostgreSQL базы.

Локально можно временно прописать production `DATABASE_URL` в `.env`, затем выполнить:

```bash
py -3.13 manage.py migrate
py manage.py createsuperuser
```

Последние миграции синхронизируют рассчитанные розничные цены и отключают
онлайн-оплату и способы доставки, кроме самовывоза. Миграции сохраняют товары,
заказы, аккаунты и данные корзин; перед запуском сделайте резервную копию базы.

После этого панель управления будет работать с серверной базой.

## 5. API

Для живых данных из базы добавлены endpoints:

- `/api/categories/` — категории.
- `/api/products/` — товары.
- `/api/products/?category=slug` — товары категории.
- `/api/products/?hits=1` — хиты продаж.
- `/api/products/?q=поиск` — поиск.
- `/api/cart/` — текущая корзина пользователя или гостя.
- `/api/management/orders/` — список заказов для сотрудника.
- `/api/management/orders/<id>/` — заказ с составом для сотрудника/CRM.

API заказов доступно только авторизованным сотрудникам.
