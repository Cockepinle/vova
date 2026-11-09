from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


def sync_retail_prices(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    database = schema_editor.connection.alias
    products = Product.objects.using(database).exclude(
        cost_price__isnull=True,
    ).exclude(retail_coefficient__isnull=True)
    batch = []
    for product in products.iterator():
        product.price = (product.cost_price * product.retail_coefficient).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        batch.append(product)
        if len(batch) == 500:
            Product.objects.using(database).bulk_update(batch, ["price"])
            batch.clear()
    if batch:
        Product.objects.using(database).bulk_update(batch, ["price"])


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0034_attributedefinition_filter_type_and_more"),
    ]

    operations = [
        migrations.RunPython(sync_retail_prices, migrations.RunPython.noop),
    ]
