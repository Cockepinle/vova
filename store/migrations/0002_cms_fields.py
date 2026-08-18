from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="status",
            field=models.CharField(
                choices=[
                    ("published", "Опубликовано"),
                    ("draft", "Черновик"),
                    ("hidden", "Скрыто"),
                ],
                default="draft",
                max_length=20,
                verbose_name="Статус",
            ),
        ),
        migrations.AlterField(
            model_name="attributedefinition",
            name="value_type",
            field=models.CharField(
                choices=[
                    ("text", "Текст"),
                    ("integer", "Целое число"),
                    ("decimal", "Дробное число"),
                    ("price", "Цена"),
                    ("boolean", "Да/Нет"),
                    ("date", "Дата"),
                    ("choice", "Список"),
                    ("image", "Изображение"),
                    ("file", "Файл"),
                    ("url", "Ссылка"),
                ],
                default="text",
                max_length=20,
                verbose_name="Тип данных",
            ),
        ),
        migrations.AddField(
            model_name="attributedefinition",
            name="default_value",
            field=models.CharField(blank=True, max_length=255, verbose_name="Значение по умолчанию"),
        ),
        migrations.AddField(
            model_name="attributedefinition",
            name="is_required",
            field=models.BooleanField(default=False, verbose_name="Обязательное"),
        ),
        migrations.AddField(
            model_name="attributedefinition",
            name="is_visible",
            field=models.BooleanField(default=True, verbose_name="Видимое"),
        ),
        migrations.AddField(
            model_name="attributedefinition",
            name="show_in_table",
            field=models.BooleanField(default=False, verbose_name="Показывать в таблице"),
        ),
        migrations.AddField(
            model_name="productattribute",
            name="value_file",
            field=models.FileField(blank=True, upload_to="product_fields/", verbose_name="Файл"),
        ),
        migrations.AddField(
            model_name="productattribute",
            name="value_url",
            field=models.URLField(blank=True, verbose_name="Ссылка"),
        ),
    ]
