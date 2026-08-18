from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0013_email_verification_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productimage",
            name="image",
            field=models.ImageField(blank=True, upload_to="product_gallery/", verbose_name="Изображение"),
        ),
        migrations.AddField(
            model_name="productimage",
            name="image_url",
            field=models.URLField(blank=True, verbose_name="Ссылка на изображение"),
        ),
    ]
