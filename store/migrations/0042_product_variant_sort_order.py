from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("store", "0041_customerprofile_retail_coefficient_and_more")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="variant_sort_order",
            field=models.PositiveIntegerField(default=0, verbose_name="Порядок в группе модификаций"),
        ),
    ]
