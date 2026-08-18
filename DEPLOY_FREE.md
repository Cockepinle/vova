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
py manage.py migrate
py manage.py createsuperuser
```

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
