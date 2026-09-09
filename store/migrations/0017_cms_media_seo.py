from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("store", "0016_orders")]

    operations = [
        migrations.AddField(model_name="sitesettings", name="logo_image", field=models.ImageField(blank=True, upload_to="site/", verbose_name="Изображение логотипа")),
        migrations.AddField(model_name="sitesettings", name="hero_image", field=models.ImageField(blank=True, upload_to="site/", verbose_name="Главное фото / баннер")),
        migrations.AddField(model_name="sitesettings", name="hero_image_alt", field=models.CharField(blank=True, max_length=180, verbose_name="Alt главного фото")),
        *[migrations.AddField(model_name="sitesettings", name=name, field=models.CharField(default=default, max_length=220 if name.endswith("_url") else 80, verbose_name=label)) for name, default, label in [
            ("nav_home_label", "Главная", "Пункт меню: главная"), ("nav_catalog_label", "Каталог", "Пункт меню: каталог"), ("nav_team_label", "Команда", "Пункт меню: команда"), ("nav_contacts_label", "Контакты", "Пункт меню: контакты"),
            ("nav_home_url", "/", "Ссылка меню: главная"), ("nav_catalog_url", "/catalog/", "Ссылка меню: каталог"), ("nav_team_url", "/team/", "Ссылка меню: команда"), ("nav_contacts_url", "/contacts/", "Ссылка меню: контакты")]],
        migrations.AddField(model_name="pagecontent", name="seo_title", field=models.CharField(blank=True, max_length=220, verbose_name="SEO-заголовок (title)")),
        migrations.AddField(model_name="pagecontent", name="meta_description", field=models.TextField(blank=True, verbose_name="Meta description")),
        migrations.AddField(model_name="pagecontent", name="h1", field=models.CharField(blank=True, max_length=220, verbose_name="Основной заголовок (H1)")),
        migrations.AddField(model_name="pagecontent", name="image_alt", field=models.CharField(blank=True, max_length=180, verbose_name="Alt изображений страницы")),
        migrations.CreateModel(name="SiteMedia", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("title", models.CharField(max_length=160, verbose_name="Название")), ("file", models.FileField(upload_to="site_media/", verbose_name="Файл")), ("alt", models.CharField(blank=True, max_length=180, verbose_name="Alt / описание")), ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Загружен"))], options={"verbose_name":"Медиафайл сайта", "verbose_name_plural":"Медиафайлы сайта", "ordering":["-created_at"]}),
    ]
