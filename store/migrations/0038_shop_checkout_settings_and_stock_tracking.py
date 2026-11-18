from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0037_alter_pagecontent_options_pagecontent_is_custom_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="stock_decremented",
            field=models.BooleanField(default=False, verbose_name="Остаток списан"),
        ),
        migrations.AddField(model_name="sitesettings", name="currency_code", field=models.CharField(default="RUB", max_length=3, verbose_name="Код валюты")),
        migrations.AddField(model_name="sitesettings", name="currency_symbol", field=models.CharField(default="₽", max_length=10, verbose_name="Символ валюты")),
        migrations.AddField(model_name="sitesettings", name="currency_decimals", field=models.PositiveSmallIntegerField(default=2, verbose_name="Знаков после запятой")),
        migrations.AddField(model_name="sitesettings", name="track_abandoned_carts", field=models.BooleanField(default=True, verbose_name="Отслеживать брошенные корзины")),
        migrations.AddField(model_name="sitesettings", name="mark_products_in_orders", field=models.BooleanField(default=False, verbose_name="Маркировать товары в заказах")),
        migrations.AddField(model_name="sitesettings", name="show_zero_price_note", field=models.BooleanField(default=True, verbose_name="Показывать примечание вместо нулевой цены")),
        migrations.AddField(model_name="sitesettings", name="zero_price_note_text", field=models.CharField(default="Цена по запросу", max_length=220, verbose_name="Текст примечания для нулевой цены")),
        migrations.AddField(model_name="sitesettings", name="hide_cart_login", field=models.BooleanField(default=False, verbose_name="Скрывать форму авторизации в корзине")),
        migrations.AddField(
            model_name="sitesettings",
            name="stock_change_mode",
            field=models.CharField(
                choices=[("creation", "При создании заказа"), ("confirmation", "При подтверждении заказа"), ("never", "Не списывать автоматически")],
                default="confirmation",
                max_length=20,
                verbose_name="Списание остатка",
            ),
        ),
        migrations.AddField(model_name="sitesettings", name="track_referrer", field=models.BooleanField(default=True, verbose_name="Отслеживать referrer и UTM")),
        migrations.AddField(model_name="sitesettings", name="manage_transactions", field=models.BooleanField(default=True, verbose_name="Управлять транзакциями платежей")),
        migrations.AddField(model_name="sitesettings", name="allow_repeat_orders", field=models.BooleanField(default=True, verbose_name="Разрешать повторные заказы")),
        migrations.AddField(model_name="sitesettings", name="checkout_steps", field=models.PositiveSmallIntegerField(default=1, verbose_name="Количество шагов оформления")),
    ]
