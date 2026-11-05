# Generated for delivery provider configuration and order delivery snapshots.
from django.db import migrations, models


def seed_delivery_options(apps, schema_editor):
    DeliveryMethod = apps.get_model("store", "DeliveryMethod")
    Order = apps.get_model("store", "Order")
    DeliveryMethod.objects.filter(code="delivery").update(
        name="Транспортная компания",
        kind="carrier",
        description="Стоимость доставки рассчитывает выбранная транспортная компания.",
    )
    DeliveryMethod.objects.filter(code="pickup").update(
        name="Самовывоз",
        kind="pickup",
        description="Адрес самовывоза указан ниже.",
    )
    DeliveryMethod.objects.get_or_create(
        code="own-delivery",
        defaults={
            "name": "Собственная доставка",
            "kind": "own",
            "description": "по согласованию с менеджером",
            "sort_order": 15,
        },
    )
    for order in Order.objects.filter(delivery_method__isnull=False).select_related("delivery_method"):
        order.delivery_method_kind = order.delivery_method.kind
        order.delivery_provider_code = order.delivery_method.provider_code
        order.save(update_fields=["delivery_method_kind", "delivery_provider_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0030_deliverymethod_order_delivery_method_name_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliverymethod",
            name="kind",
            field=models.CharField(
                choices=[
                    ("carrier", "Транспортная компания"),
                    ("own", "Собственная доставка"),
                    ("pickup", "Самовывоз"),
                    ("custom", "Другой способ"),
                ],
                default="carrier",
                max_length=20,
                verbose_name="Тип доставки",
            ),
        ),
        migrations.AddField(
            model_name="deliverymethod",
            name="provider_code",
            field=models.SlugField(blank=True, max_length=80, verbose_name="Код delivery provider"),
        ),
        migrations.AddField(
            model_name="deliverymethod",
            name="handoff_url",
            field=models.URLField(blank=True, verbose_name="Ссылка на сервис перевозчика"),
        ),
        migrations.AddField(
            model_name="deliverymethod",
            name="provider_config",
            field=models.JSONField(blank=True, default=dict, verbose_name="Параметры delivery provider"),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_method_kind",
            field=models.CharField(blank=True, max_length=20, verbose_name="Тип доставки на момент заказа"),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_provider_code",
            field=models.CharField(blank=True, max_length=80, verbose_name="Delivery provider на момент заказа"),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_origin_address",
            field=models.CharField(blank=True, max_length=500, verbose_name="Адрес отправления на момент заказа"),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.CharField(blank=True, max_length=500, verbose_name="Адрес получения"),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_handoff_url",
            field=models.URLField(blank=True, verbose_name="Ссылка на сервис перевозчика"),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_provider_data",
            field=models.JSONField(blank=True, default=dict, verbose_name="Данные для delivery provider"),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="length_mm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Длина единицы на момент заказа, мм"),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="width_mm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Ширина единицы на момент заказа, мм"),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="height_mm",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Высота единицы на момент заказа, мм"),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="pickup_address",
            field=models.CharField(blank=True, help_text="Если не заполнен, используется основной адрес магазина.", max_length=500, verbose_name="Адрес самовывоза"),
        ),
        migrations.RunPython(seed_delivery_options, migrations.RunPython.noop),
    ]
