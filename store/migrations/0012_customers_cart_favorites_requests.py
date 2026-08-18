from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0011_site_settings_content_blocks"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company", models.CharField(blank=True, max_length=180, verbose_name="Компания")),
                ("phone", models.CharField(blank=True, max_length=80, verbose_name="Телефон")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="customer_profile", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={"verbose_name": "Профиль клиента", "verbose_name_plural": "Профили клиентов"},
        ),
        migrations.CreateModel(
            name="CustomerRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, verbose_name="Имя")),
                ("company", models.CharField(blank=True, max_length=180, verbose_name="Компания")),
                ("email", models.EmailField(max_length=254, verbose_name="Email")),
                ("phone", models.CharField(blank=True, max_length=80, verbose_name="Телефон")),
                ("text", models.TextField(verbose_name="Что нужно")),
                ("status", models.CharField(choices=[("new", "Новая"), ("processing", "В работе"), ("done", "Закрыта")], default="new", max_length=20, verbose_name="Статус")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создана")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="requests", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={"verbose_name": "Заявка", "verbose_name_plural": "Заявки", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FavoriteItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Добавлено")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorite_items", to="store.product", verbose_name="Товар")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="favorite_items", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={"verbose_name": "Избранный товар", "verbose_name_plural": "Избранное пользователей", "unique_together": {("user", "product")}},
        ),
        migrations.CreateModel(
            name="CartItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="Количество")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cart_items", to="store.product", verbose_name="Товар")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cart_items", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={"verbose_name": "Товар в корзине", "verbose_name_plural": "Корзины пользователей", "unique_together": {("user", "product")}},
        ),
    ]
