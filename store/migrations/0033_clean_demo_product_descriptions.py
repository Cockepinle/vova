from django.db import migrations


DISCLAIMER = (
    " Демонстрационная позиция: стоимость и параметры необходимо подтвердить "
    "перед заказом."
)
OLD_ARCHIVE_DESCRIPTION = "Увеличенный демонстрационный формат для документов и папок."
NEW_ARCHIVE_DESCRIPTION = (
    "Архивный короб для документов и папок, защищающий содержимое от пыли и повреждений."
)


def clean_demo_descriptions(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    products = Product.objects.using(schema_editor.connection.alias).filter(sku__startswith="DEMO-")
    for product in products.iterator():
        description = product.description or ""
        if description.endswith(DISCLAIMER):
            description = description[:-len(DISCLAIMER)]
        if product.sku == "DEMO-ARCH-332535" and description == OLD_ARCHIVE_DESCRIPTION:
            description = NEW_ARCHIVE_DESCRIPTION
        if description != product.description:
            Product.objects.using(schema_editor.connection.alias).filter(pk=product.pk).update(
                description=description,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0032_adminloginthrottlebucket_adminloginattempt"),
    ]

    operations = [
        migrations.RunPython(clean_demo_descriptions, migrations.RunPython.noop),
    ]
