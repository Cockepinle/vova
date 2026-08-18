from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0004_russian_admin_labels"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="image",
            field=models.ImageField(blank=True, upload_to="categories/", verbose_name="Изображение"),
        ),
        migrations.AlterField(
            model_name="product",
            name="image",
            field=models.ImageField(blank=True, upload_to="products/", verbose_name="Главное изображение"),
        ),
        migrations.AlterField(
            model_name="productimage",
            name="image",
            field=models.ImageField(upload_to="product_gallery/", verbose_name="Изображение"),
        ),
    ]
