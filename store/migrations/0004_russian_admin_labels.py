from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0003_site_settings_page_content"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="slug",
            field=models.SlugField(allow_unicode=True, blank=True, max_length=180, unique=True, verbose_name="URL-адрес"),
        ),
        migrations.AlterField(
            model_name="category",
            name="image",
            field=models.URLField(blank=True, verbose_name="Ссылка на изображение"),
        ),
        migrations.AlterField(
            model_name="product",
            name="slug",
            field=models.SlugField(allow_unicode=True, blank=True, max_length=240, unique=True, verbose_name="URL-адрес"),
        ),
        migrations.AlterField(
            model_name="product",
            name="image",
            field=models.URLField(blank=True, verbose_name="Ссылка на главное изображение"),
        ),
        migrations.AlterField(
            model_name="productimage",
            name="image",
            field=models.URLField(verbose_name="Ссылка на изображение"),
        ),
        migrations.AlterField(
            model_name="productimage",
            name="alt",
            field=models.CharField(blank=True, max_length=180, verbose_name="Описание изображения"),
        ),
        migrations.AlterField(
            model_name="attributedefinition",
            name="slug",
            field=models.SlugField(allow_unicode=True, blank=True, max_length=180, unique=True, verbose_name="URL-адрес"),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="header_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="Почта в шапке"),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="footer_email",
            field=models.EmailField(blank=True, max_length=254, verbose_name="Почта в подвале"),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="copyright_text",
            field=models.CharField(blank=True, max_length=220, verbose_name="Текст авторских прав"),
        ),
    ]
