from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AttributeDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, unique=True, verbose_name="Название критерия")),
                ("slug", models.SlugField(allow_unicode=True, blank=True, max_length=180, unique=True, verbose_name="Slug")),
                (
                    "value_type",
                    models.CharField(
                        choices=[
                            ("text", "Текст"),
                            ("integer", "Целое число"),
                            ("decimal", "Дробное число"),
                            ("boolean", "Да/Нет"),
                            ("date", "Дата"),
                            ("choice", "Выбор из списка"),
                        ],
                        default="text",
                        max_length=20,
                        verbose_name="Тип данных",
                    ),
                ),
                ("unit", models.CharField(blank=True, max_length=40, verbose_name="Единица измерения")),
                ("choices", models.JSONField(blank=True, default=list, verbose_name="Варианты выбора")),
                ("is_filterable", models.BooleanField(default=True, verbose_name="Использовать в фильтрах")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "Критерий товара",
                "verbose_name_plural": "Критерии товаров",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, unique=True, verbose_name="Название")),
                ("slug", models.SlugField(allow_unicode=True, blank=True, max_length=180, unique=True, verbose_name="Slug")),
                ("image", models.URLField(blank=True, verbose_name="Изображение")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
            ],
            options={
                "verbose_name": "Категория",
                "verbose_name_plural": "Категории",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=220, verbose_name="Название")),
                ("slug", models.SlugField(allow_unicode=True, blank=True, max_length=240, unique=True, verbose_name="Slug")),
                ("sku", models.CharField(max_length=80, unique=True, verbose_name="Артикул")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
                ("price", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Цена")),
                ("old_price", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Старая цена")),
                ("unit", models.CharField(default="шт", max_length=40, verbose_name="Единица измерения")),
                ("min_quantity", models.PositiveIntegerField(default=1, verbose_name="Минимальное количество")),
                ("image", models.URLField(blank=True, verbose_name="Главное изображение")),
                ("badge", models.CharField(blank=True, max_length=40, verbose_name="Бейдж")),
                ("is_hit", models.BooleanField(default=False, verbose_name="Хит продаж")),
                ("is_new", models.BooleanField(default=False, verbose_name="Новинка")),
                (
                    "availability",
                    models.CharField(
                        choices=[
                            ("in_stock", "В наличии"),
                            ("preorder", "Под заказ"),
                            ("out_of_stock", "Нет в наличии"),
                        ],
                        default="in_stock",
                        max_length=20,
                        verbose_name="Наличие",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлён")),
                (
                    "category",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="store.category", verbose_name="Категория"),
                ),
            ],
            options={
                "verbose_name": "Товар",
                "verbose_name_plural": "Товары",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.URLField(verbose_name="Изображение")),
                ("alt", models.CharField(blank=True, max_length=180, verbose_name="Alt-текст")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Порядок")),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="store.product", verbose_name="Товар"),
                ),
            ],
            options={
                "verbose_name": "Изображение товара",
                "verbose_name_plural": "Изображения товара",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ProductAttribute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value_text", models.TextField(blank=True, verbose_name="Текст")),
                ("value_integer", models.IntegerField(blank=True, null=True, verbose_name="Целое число")),
                ("value_decimal", models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True, verbose_name="Дробное число")),
                ("value_boolean", models.BooleanField(blank=True, null=True, verbose_name="Да/Нет")),
                ("value_date", models.DateField(blank=True, null=True, verbose_name="Дата")),
                ("value_choice", models.CharField(blank=True, max_length=160, verbose_name="Выбор")),
                (
                    "attribute",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="product_values", to="store.attributedefinition", verbose_name="Критерий"),
                ),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attributes", to="store.product", verbose_name="Товар"),
                ),
            ],
            options={
                "verbose_name": "Значение критерия",
                "verbose_name_plural": "Значения критериев",
                "ordering": ["attribute__sort_order", "attribute__name"],
                "unique_together": {("product", "attribute")},
            },
        ),
    ]
