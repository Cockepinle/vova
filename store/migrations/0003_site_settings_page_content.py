from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0002_cms_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("site_name", models.CharField(default="PakLine", max_length=120, verbose_name="Название сайта")),
                ("logo_text", models.CharField(default="PL", max_length=20, verbose_name="Текст логотипа")),
                ("header_phone", models.CharField(blank=True, max_length=80, verbose_name="Телефон в шапке")),
                ("header_email", models.EmailField(blank=True, max_length=254, verbose_name="Email в шапке")),
                ("footer_company", models.CharField(default="ООО «ПакЛайн»", max_length=180, verbose_name="Компания в подвале")),
                ("footer_description", models.TextField(blank=True, verbose_name="Описание в подвале")),
                ("footer_phone", models.CharField(blank=True, max_length=80, verbose_name="Телефон в подвале")),
                ("footer_email", models.EmailField(blank=True, max_length=254, verbose_name="Email в подвале")),
                ("footer_address", models.CharField(blank=True, max_length=220, verbose_name="Адрес в подвале")),
                ("footer_work_time", models.CharField(blank=True, max_length=120, verbose_name="Время работы")),
                ("copyright_text", models.CharField(blank=True, max_length=220, verbose_name="Copyright")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={
                "verbose_name": "Настройки сайта",
                "verbose_name_plural": "Настройки сайта",
            },
        ),
        migrations.CreateModel(
            name="PageContent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "page",
                    models.CharField(
                        choices=[
                            ("home", "Главная"),
                            ("catalog", "Каталог"),
                            ("team", "Команда"),
                            ("contacts", "Контакты"),
                        ],
                        max_length=40,
                        unique=True,
                        verbose_name="Страница",
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=220, verbose_name="Заголовок")),
                ("subtitle", models.TextField(blank=True, verbose_name="Подзаголовок / текст")),
                ("hero_label", models.CharField(blank=True, max_length=160, verbose_name="Метка")),
                ("hero_button_text", models.CharField(blank=True, max_length=120, verbose_name="Текст кнопки")),
                ("is_visible", models.BooleanField(default=True, verbose_name="Показывать")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={
                "verbose_name": "Текст страницы",
                "verbose_name_plural": "Тексты страниц",
                "ordering": ["page"],
            },
        ),
    ]
