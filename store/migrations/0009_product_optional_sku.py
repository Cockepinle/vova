from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0008_product_stock_quantity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="sku",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True, verbose_name="Артикул"),
        ),
    ]
