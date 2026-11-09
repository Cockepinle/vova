from django.db import migrations


def disable_unavailable_methods(apps, schema_editor):
    database = schema_editor.connection.alias
    PaymentMethod = apps.get_model("store", "PaymentMethod")
    DeliveryMethod = apps.get_model("store", "DeliveryMethod")

    PaymentMethod.objects.using(database).update(is_active=False)
    PaymentMethod.objects.using(database).filter(
        code="invoice",
        kind="invoice",
    ).update(is_active=True)

    DeliveryMethod.objects.using(database).update(is_active=False)
    DeliveryMethod.objects.using(database).filter(
        code="pickup",
        kind="pickup",
    ).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0035_sync_calculated_retail_prices"),
    ]

    operations = [
        migrations.RunPython(disable_unavailable_methods, migrations.RunPython.noop),
    ]
