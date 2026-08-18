from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0012_customers_cart_favorites_requests"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailVerificationCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, verbose_name="Email")),
                ("code", models.CharField(max_length=6, verbose_name="Код")),
                ("payload", models.JSONField(default=dict, verbose_name="Данные регистрации")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создан")),
                ("is_used", models.BooleanField(default=False, verbose_name="Использован")),
            ],
            options={
                "verbose_name": "Код подтверждения email",
                "verbose_name_plural": "Коды подтверждения email",
                "ordering": ["-created_at"],
            },
        ),
    ]
