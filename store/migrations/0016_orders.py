from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0015_main_image_urls"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=32, unique=True, verbose_name="Номер заказа")),
                ("full_name", models.CharField(max_length=180, verbose_name="ФИО")),
                ("phone", models.CharField(max_length=80, verbose_name="Телефон")),
                ("email", models.EmailField(max_length=254, verbose_name="Email")),
                ("company", models.CharField(blank=True, max_length=180, verbose_name="Компания")),
                ("comment", models.TextField(blank=True, verbose_name="Комментарий")),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name="Итого")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "Новый"),
                            ("processing", "В обработке"),
                            ("invoiced", "Счёт выставлен"),
                            ("paid", "Оплачен"),
                            ("done", "Выполнен"),
                            ("canceled", "Отменён"),
                        ],
                        default="new",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь"),
                ),
            ],
            options={
                "verbose_name": "Заказ",
                "verbose_name_plural": "Заказы",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name", models.CharField(max_length=220, verbose_name="Название товара на момент заказа")),
                ("product_sku", models.CharField(blank=True, max_length=80, verbose_name="Артикул на момент заказа")),
                ("unit", models.CharField(blank=True, max_length=40, verbose_name="Единица измерения")),
                ("quantity", models.PositiveIntegerField(verbose_name="Количество")),
                ("price", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Цена на момент заказа")),
                ("line_total", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="Сумма позиции")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="store.order", verbose_name="Заказ")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="store.product", verbose_name="Товар")),
            ],
            options={
                "verbose_name": "Позиция заказа",
                "verbose_name_plural": "Позиции заказа",
            },
        ),
    ]
