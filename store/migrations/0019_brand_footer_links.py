from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("store", "0018_page_content_blocks")]

    operations = [
        migrations.AddField(model_name="sitesettings", name="logo_alt", field=models.CharField(blank=True, max_length=180, verbose_name="Alt логотипа")),
        migrations.AddField(model_name="sitesettings", name="footer_privacy_label", field=models.CharField(default="Политика конфиденциальности", max_length=120, verbose_name="Подвал: название ссылки политики")),
        migrations.AddField(model_name="sitesettings", name="footer_privacy_url", field=models.CharField(default="/documents/privacy/", max_length=220, verbose_name="Подвал: ссылка политики")),
        migrations.AddField(model_name="sitesettings", name="footer_offer_label", field=models.CharField(default="Оферта", max_length=120, verbose_name="Подвал: название ссылки оферты")),
        migrations.AddField(model_name="sitesettings", name="footer_offer_url", field=models.CharField(default="/documents/offer/", max_length=220, verbose_name="Подвал: ссылка оферты")),
    ]
