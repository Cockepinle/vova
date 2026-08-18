from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0007_dynamic_field_table_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="stock_quantity",
            field=models.PositiveIntegerField(default=0, verbose_name="Количество на складе"),
        ),
    ]
