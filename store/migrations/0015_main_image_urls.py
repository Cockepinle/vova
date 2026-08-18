from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0014_productimage_image_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="image_url",
            field=models.URLField(blank=True, verbose_name="Ссылка на изображение"),
        ),
        migrations.AddField(
            model_name="product",
            name="image_url",
            field=models.URLField(blank=True, verbose_name="Ссылка на главное изображение"),
        ),
        migrations.AddField(
            model_name="employee",
            name="image_url",
            field=models.URLField(blank=True, verbose_name="Ссылка на фото"),
        ),
    ]
