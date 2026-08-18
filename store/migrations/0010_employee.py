from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0009_product_optional_sku"),
    ]

    operations = [
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, verbose_name="Имя")),
                ("role", models.CharField(max_length=160, verbose_name="Должность")),
                ("text", models.TextField(blank=True, verbose_name="Описание")),
                ("image", models.ImageField(blank=True, upload_to="employees/", verbose_name="Фото")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Email")),
                ("phone", models.CharField(blank=True, max_length=80, verbose_name="Телефон")),
                (
                    "status",
                    models.CharField(
                        choices=[("published", "Опубликовано"), ("draft", "Черновик"), ("hidden", "Скрыто")],
                        default="draft",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
            ],
            options={
                "verbose_name": "Сотрудник",
                "verbose_name_plural": "Сотрудники",
                "ordering": ["sort_order", "name"],
            },
        ),
    ]
