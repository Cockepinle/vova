# PostgreSQL для PakLine

Для реального сайта лучше использовать PostgreSQL, а SQLite оставить только для локальных быстрых тестов.

## 1. Установить зависимости

```bash
py -m pip install -r requirements.txt
```

## 2. Создать базу и пользователя

В PostgreSQL:

```sql
CREATE DATABASE pakline;
CREATE USER pakline_user WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE pakline TO pakline_user;
```

## 3. Создать `.env`

Скопировать `.env.example` в `.env` и поменять значения:

```env
DEBUG=1
SECRET_KEY=change-me-before-production
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=postgres://pakline_user:strong_password@127.0.0.1:5432/pakline
```

## 4. Применить миграции

```bash
py manage.py migrate
py manage.py seed_demo_catalog
py manage.py createsuperuser
py manage.py runserver
```

Команда `seed_demo_catalog` добавляет демонстрационные категории и товары коробок
с примерными ценами и внешними фотографиями. Она не удаляет заказы или аккаунты,
но переименовывает две старые категории `Картон` и `Картон — копия`, если они
есть. Запускайте ее только если хотите именно такой демонстрационный каталог.
Перед публикацией замените примерные цены, реквизиты и контактные данные на
актуальные.

После этого таблицы каталога будут созданы в PostgreSQL и доступны в `/admin/`.
