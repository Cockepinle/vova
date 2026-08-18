from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0010_employee"),
    ]

    operations = [
        migrations.AddField("sitesettings", "home_hero_label", models.CharField(default="Оптовые поставки · Москва и Россия", max_length=160, verbose_name="Надпись-метка")),
        migrations.AddField("sitesettings", "home_hero_title", models.CharField(default="Упаковка для вашего бизнеса", max_length=220, verbose_name="Заголовок")),
        migrations.AddField("sitesettings", "home_hero_subtitle", models.TextField(default="Гофрокартон, стрейч-плёнка, скотч, пузырчатая плёнка и 300+ SKU на складе в Москве. Отгрузка в день заказа.", verbose_name="Подзаголовок")),
        migrations.AddField("sitesettings", "catalog_title", models.CharField(default="Все товары", max_length=220, verbose_name="Заголовок каталога")),
        migrations.AddField("sitesettings", "catalog_subtitle", models.CharField(default="Каталог упаковочных материалов", max_length=220, verbose_name="Подзаголовок каталога")),
        migrations.AddField("sitesettings", "team_hero_label", models.CharField(default="Наша команда", max_length=160, verbose_name="Метка команды")),
        migrations.AddField("sitesettings", "team_hero_title", models.CharField(default="Люди, которые делают это", max_length=220, verbose_name="Заголовок команды")),
        migrations.AddField("sitesettings", "team_hero_subtitle", models.TextField(default="Логисты, технологи, менеджеры — все с профильным опытом. Мы не агрегатор, мы оператор.", verbose_name="Текст команды")),
        migrations.AddField("sitesettings", "contacts_hero_label", models.CharField(default="Связаться с нами", max_length=160, verbose_name="Метка контактов")),
        migrations.AddField("sitesettings", "contacts_hero_title", models.CharField(default="Контакты", max_length=220, verbose_name="Заголовок контактов")),
        migrations.AddField("sitesettings", "contacts_form_title", models.CharField(default="Запросить коммерческое предложение", max_length=220, verbose_name="Заголовок формы")),
        migrations.AddField("sitesettings", "contacts_b2b_title", models.CharField(default="Для корпоративных клиентов", max_length=220, verbose_name="Заголовок B2B")),
        migrations.AddField("sitesettings", "contacts_b2b_subtitle", models.CharField(default="Персональный менеджер и индивидуальные условия", max_length=220, verbose_name="Подзаголовок B2B")),
        migrations.AddField("sitesettings", "contacts_b2b_text", models.TextField(default="Постоплата 30/60 дней, скидки от объёма, брендированная упаковка, SLA на поставки.", verbose_name="Текст B2B")),
        migrations.AddField("sitesettings", "stat_1_value", models.CharField(default="300+", max_length=80, verbose_name="Значение 1")),
        migrations.AddField("sitesettings", "stat_1_label", models.CharField(default="SKU на складе", max_length=120, verbose_name="Подпись 1")),
        migrations.AddField("sitesettings", "stat_2_value", models.CharField(default="12 лет", max_length=80, verbose_name="Значение 2")),
        migrations.AddField("sitesettings", "stat_2_label", models.CharField(default="на рынке", max_length=120, verbose_name="Подпись 2")),
        migrations.AddField("sitesettings", "stat_3_value", models.CharField(default="2400+", max_length=80, verbose_name="Значение 3")),
        migrations.AddField("sitesettings", "stat_3_label", models.CharField(default="клиентов", max_length=120, verbose_name="Подпись 3")),
        migrations.AddField("sitesettings", "stat_4_value", models.CharField(default="День в день", max_length=80, verbose_name="Значение 4")),
        migrations.AddField("sitesettings", "stat_4_label", models.CharField(default="отгрузка", max_length=120, verbose_name="Подпись 4")),
        migrations.AddField("sitesettings", "contact_phone", models.CharField(default="+7 (800) 555-38-22", max_length=80, verbose_name="Телефон")),
        migrations.AddField("sitesettings", "contact_email", models.EmailField(default="info@pakline.ru", max_length=254, verbose_name="Email")),
        migrations.AddField("sitesettings", "contact_email_b2b", models.EmailField(default="b2b@pakline.ru", max_length=254, verbose_name="Email B2B")),
        migrations.AddField("sitesettings", "contact_address", models.CharField(default="г. Москва, ул. Складская, д. 14", max_length=220, verbose_name="Адрес")),
        migrations.AddField("sitesettings", "contact_work_hours", models.CharField(default="ПН–ПТ 9:00–18:00", max_length=120, verbose_name="Часы работы")),
        migrations.AddField("sitesettings", "company_name", models.CharField(default="ООО «ПакЛайн»", max_length=180, verbose_name="Компания")),
        migrations.AddField("sitesettings", "company_inn", models.CharField(default="7701234567", max_length=30, verbose_name="ИНН")),
        migrations.AddField("sitesettings", "company_kpp", models.CharField(default="770101001", max_length=30, verbose_name="КПП")),
    ]
