from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0038_shop_checkout_settings_and_stock_tracking"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pagecontent",
            name="draft_structure",
            field=models.JSONField(blank=True, default=list, verbose_name="Черновик структуры"),
        ),
        migrations.AddField(
            model_name="pagecontent",
            name="published_structure",
            field=models.JSONField(blank=True, default=list, verbose_name="Опубликованная структура"),
        ),
        migrations.AddField(
            model_name="pagecontent",
            name="draft_design",
            field=models.JSONField(blank=True, default=dict, verbose_name="Черновик дизайна"),
        ),
        migrations.AddField(
            model_name="pagecontent",
            name="published_design",
            field=models.JSONField(blank=True, default=dict, verbose_name="Опубликованный дизайн"),
        ),
        migrations.CreateModel(
            name="BuilderRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("structure", models.JSONField(default=list, verbose_name="Структура")),
                ("design", models.JSONField(default=dict, verbose_name="Дизайн")),
                ("label", models.CharField(blank=True, max_length=180, verbose_name="Описание версии")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="builder_page_revisions", to=settings.AUTH_USER_MODEL, verbose_name="Автор")),
                ("page", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="builder_revisions", to="store.pagecontent", verbose_name="Страница")),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "Версия конструктора", "verbose_name_plural": "Версии конструктора"},
        ),
        migrations.CreateModel(
            name="GlobalBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180, verbose_name="Название")),
                ("location", models.CharField(choices=[("header", "Шапка"), ("footer", "Подвал")], max_length=20, verbose_name="Расположение")),
                ("structure", models.JSONField(default=list, verbose_name="Структура")),
                ("published_structure", models.JSONField(default=list, verbose_name="Опубликованная структура")),
                ("is_visible", models.BooleanField(default=True, verbose_name="Показывать")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={"ordering": ["location", "name"], "verbose_name": "Глобальный блок", "verbose_name_plural": "Глобальные блоки"},
        ),
        migrations.CreateModel(
            name="DesignSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("settings", models.JSONField(default=dict, verbose_name="Настройки дизайна")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
            ],
            options={"verbose_name": "Дизайн сайта", "verbose_name_plural": "Дизайн сайта"},
        ),
    ]
