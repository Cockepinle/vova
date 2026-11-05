from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class SiteSettings(models.Model):
    public_url = models.URLField("Основной адрес сайта", blank=True, help_text="Например, https://example.ru. Используется для canonical и карты сайта.")
    logo_media = models.ForeignKey("SiteMedia", verbose_name="Логотип из медиатеки", on_delete=models.PROTECT, null=True, blank=True, related_name="logo_uses")
    favicon_media = models.ForeignKey("SiteMedia", verbose_name="Иконка вкладки из медиатеки", on_delete=models.PROTECT, null=True, blank=True, related_name="favicon_uses")
    og_media = models.ForeignKey("SiteMedia", verbose_name="Изображение для отправки ссылок по умолчанию", on_delete=models.PROTECT, null=True, blank=True, related_name="site_og_uses")
    seo_description = models.TextField("Описание компании для поисковых систем", blank=True)
    cta_label = models.CharField("Основная кнопка: текст", max_length=28, default="Консультация")
    cta_url = models.CharField("Основная кнопка: ссылка", max_length=220, default="/contacts/#request-form")
    show_header_contacts = models.BooleanField("Показывать контакты в шапке", default=True)
    show_header_account = models.BooleanField("Показывать профиль в шапке", default=True)
    show_header_favorites = models.BooleanField("Показывать избранное в шапке", default=True)
    show_header_cta = models.BooleanField("Показывать основную кнопку в шапке", default=False)
    footer_extra_text = models.TextField("Дополнительный текст подвала", blank=True)
    footer_legal_text = models.TextField("Юридическая информация в подвале", blank=True)
    allow_indexing = models.BooleanField("Разрешить индексацию сайта", default=True)

    @property
    def logo_url(self):
        file_field = self.logo_media.file if self.logo_media_id else self.logo_image
        if not file_field or not file_field.name:
            return ""
        try:
            if not file_field.storage.exists(file_field.name):
                return ""
            return file_field.url
        except (OSError, ValueError):
            return ""


    site_name = models.CharField("Название сайта", max_length=120, default="PakLine")
    logo_text = models.CharField("Текст логотипа", max_length=20, default="PL")
    home_hero_label = models.CharField("Надпись-метка", max_length=160, default="Оптовые поставки · Москва и Россия")
    home_hero_title = models.CharField("Заголовок", max_length=220, default="Упаковка для вашего бизнеса")
    home_hero_subtitle = models.TextField(
        "Подзаголовок",
        default="Гофрокартон, стрейч-плёнка, скотч, пузырчатая плёнка и 300+ SKU на складе в Москве. Отгрузка в день заказа.",
    )
    catalog_title = models.CharField("Заголовок каталога", max_length=220, default="Все товары")
    catalog_subtitle = models.CharField("Подзаголовок каталога", max_length=220, default="Каталог упаковочных материалов")
    team_hero_label = models.CharField("Метка команды", max_length=160, default="Наша команда")
    team_hero_title = models.CharField("Заголовок команды", max_length=220, default="Люди, которые делают это")
    team_hero_subtitle = models.TextField(
        "Текст команды",
        default="Логисты, технологи, менеджеры — все с профильным опытом. Мы не агрегатор, мы оператор.",
    )
    contacts_hero_label = models.CharField("Метка контактов", max_length=160, default="Связаться с нами")
    contacts_hero_title = models.CharField("Заголовок контактов", max_length=220, default="Контакты")
    contacts_form_title = models.CharField("Заголовок формы", max_length=220, default="Запросить коммерческое предложение")
    contacts_b2b_title = models.CharField("Заголовок B2B", max_length=220, default="Для корпоративных клиентов")
    contacts_b2b_subtitle = models.CharField("Подзаголовок B2B", max_length=220, default="Персональный менеджер и индивидуальные условия")
    contacts_b2b_text = models.TextField(
        "Текст B2B",
        default="Постоплата 30/60 дней, скидки от объёма, брендированная упаковка, SLA на поставки.",
    )
    stat_1_value = models.CharField("Значение 1", max_length=80, default="300+")
    stat_1_label = models.CharField("Подпись 1", max_length=120, default="SKU на складе")
    stat_2_value = models.CharField("Значение 2", max_length=80, default="12 лет")
    stat_2_label = models.CharField("Подпись 2", max_length=120, default="на рынке")
    stat_3_value = models.CharField("Значение 3", max_length=80, default="2400+")
    stat_3_label = models.CharField("Подпись 3", max_length=120, default="клиентов")
    stat_4_value = models.CharField("Значение 4", max_length=80, default="День в день")
    stat_4_label = models.CharField("Подпись 4", max_length=120, default="отгрузка")
    contact_phone = models.CharField("Телефон", max_length=80, default="+7 (800) 555-38-22")
    contact_email = models.EmailField("Email", default="info@pakline.ru")
    contact_email_b2b = models.EmailField("Email B2B", default="b2b@pakline.ru")
    contact_address = models.CharField("Адрес", max_length=220, default="г. Москва, ул. Складская, д. 14")
    pickup_address = models.CharField("Адрес самовывоза", max_length=500, blank=True, help_text="Если не заполнен, используется основной адрес магазина.")
    contact_work_hours = models.CharField("Часы работы", max_length=120, default="ПН–ПТ 9:00–18:00")
    company_name = models.CharField("Компания", max_length=180, default="ООО «ПакЛайн»")
    company_inn = models.CharField("ИНН", max_length=30, default="7701234567")
    company_kpp = models.CharField("КПП", max_length=30, default="770101001")
    header_phone = models.CharField("Телефон в шапке", max_length=80, blank=True)
    header_email = models.EmailField("Почта в шапке", blank=True)
    footer_company = models.CharField("Компания в подвале", max_length=180, default="ООО «ПакЛайн»")
    footer_description = models.TextField("Описание в подвале", blank=True)
    footer_phone = models.CharField("Телефон в подвале", max_length=80, blank=True)
    footer_email = models.EmailField("Почта в подвале", blank=True)
    footer_address = models.CharField("Адрес в подвале", max_length=220, blank=True)
    footer_work_time = models.CharField("Время работы", max_length=120, blank=True)
    copyright_text = models.CharField("Текст авторских прав", max_length=220, blank=True)
    logo_image = models.ImageField("Изображение логотипа", upload_to="site/", blank=True)
    logo_alt = models.CharField("Alt логотипа", max_length=180, blank=True)
    nav_home_label = models.CharField("Пункт меню: главная", max_length=80, default="Главная")
    nav_catalog_label = models.CharField("Пункт меню: каталог", max_length=80, default="Каталог")
    nav_team_label = models.CharField("Пункт меню: команда", max_length=80, default="Команда")
    nav_contacts_label = models.CharField("Пункт меню: контакты", max_length=80, default="Контакты")
    nav_home_url = models.CharField("Ссылка меню: главная", max_length=220, default="/")
    nav_catalog_url = models.CharField("Ссылка меню: каталог", max_length=220, default="/catalog/")
    nav_team_url = models.CharField("Ссылка меню: команда", max_length=220, default="/team/")
    nav_contacts_url = models.CharField("Ссылка меню: контакты", max_length=220, default="/contacts/")
    footer_privacy_label = models.CharField("Подвал: название ссылки политики", max_length=120, default="Политика конфиденциальности")
    footer_privacy_url = models.CharField("Подвал: ссылка политики", max_length=220, default="/documents/privacy/")
    footer_offer_label = models.CharField("Подвал: название ссылки оферты", max_length=120, default="Оферта")
    footer_offer_url = models.CharField("Подвал: ссылка оферты", max_length=220, default="/documents/offer/")
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return self.site_name

    @classmethod
    def get_solo(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

class PageContent(models.Model):
    canonical = models.URLField("Основной адрес страницы (canonical)", blank=True, help_text="Оставьте пустым для автоматического адреса.")
    og_title = models.CharField("Заголовок при отправке ссылки", max_length=220, blank=True)
    og_description = models.TextField("Описание при отправке ссылки", blank=True)
    og_media = models.ForeignKey("SiteMedia", verbose_name="Изображение при отправке ссылки", on_delete=models.PROTECT, null=True, blank=True, related_name="page_og_uses")
    hero_media = models.ForeignKey("SiteMedia", verbose_name="Главное изображение из медиатеки", on_delete=models.PROTECT, null=True, blank=True, related_name="hero_uses")
    mobile_hero_media = models.ForeignKey("SiteMedia", verbose_name="Мобильное изображение из медиатеки", on_delete=models.PROTECT, null=True, blank=True, related_name="mobile_hero_uses")
    hero_button_url = models.CharField("Ссылка главной кнопки", max_length=220, blank=True)
    noindex = models.BooleanField("Не показывать страницу в поиске", default=False)

    @property
    def hero_url(self):
        return self.hero_media.file.url if self.hero_media_id else (self.hero_image.url if self.hero_image else "")

    @property
    def hero_alt(self):
        return self.hero_image_alt or (self.hero_media.alt if self.hero_media_id else "")


    PAGE_HOME = "home"
    PAGE_CATALOG = "catalog"
    PAGE_TEAM = "team"
    PAGE_CONTACTS = "contacts"
    PAGE_PROMOTIONS = "promotions"

    PAGE_CHOICES = [
        (PAGE_HOME, "Главная"),
        (PAGE_CATALOG, "Каталог"),
        (PAGE_TEAM, "Команда"),
        (PAGE_CONTACTS, "Контакты"),
        (PAGE_PROMOTIONS, "Акции"),
        ("privacy", "Политика конфиденциальности"),
        ("offer", "Оферта"),
    ]

    page = models.CharField("Страница", max_length=40, choices=PAGE_CHOICES, unique=True)
    title = models.CharField("Заголовок", max_length=220, blank=True)
    subtitle = models.TextField("Подзаголовок / текст", blank=True)
    hero_label = models.CharField("Метка", max_length=160, blank=True)
    hero_button_text = models.CharField("Текст кнопки", max_length=120, blank=True)
    hero_image = models.ImageField("Изображение главного блока", upload_to="pages/", blank=True)
    hero_image_alt = models.CharField("Alt изображения главного блока", max_length=180, blank=True)
    content_title = models.CharField("Заголовок дополнительного блока", max_length=220, blank=True)
    content_subtitle = models.CharField("Подзаголовок дополнительного блока", max_length=220, blank=True)
    content_text = models.TextField("Текст дополнительного блока", blank=True)
    b2b_title = models.CharField("Заголовок B2B-блока", max_length=220, blank=True)
    seo_title = models.CharField("SEO-заголовок (title)", max_length=220, blank=True)
    meta_description = models.TextField("Meta description", blank=True)
    h1 = models.CharField("Основной заголовок (H1)", max_length=220, blank=True)
    is_visible = models.BooleanField("Показывать", default=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Текст страницы"
        verbose_name_plural = "Тексты страниц"
        ordering = ["page"]

    def __str__(self):
        return self.get_page_display()

class SiteMedia(models.Model):
    TYPE_IMAGE = "image"
    TYPE_VIDEO = "video"
    TYPE_DOCUMENT = "document"
    TYPE_OTHER = "other"
    TYPE_CHOICES = [
        (TYPE_IMAGE, "Изображение"),
        (TYPE_VIDEO, "Видео"),
        (TYPE_DOCUMENT, "Документ"),
        (TYPE_OTHER, "Другой файл"),
    ]

    @property
    def is_video(self):
        from pathlib import PurePosixPath
        return PurePosixPath(self.file.name).suffix.lower() in {".mp4", ".webm"}

    @property
    def is_image(self):
        from pathlib import PurePosixPath
        return PurePosixPath(self.file.name).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico"}

    title = models.CharField("Название", max_length=160)
    file = models.FileField("Файл", upload_to="site_media/")
    alt = models.CharField("Alt / описание", max_length=180, blank=True)
    description = models.TextField("Описание", blank=True)
    media_type = models.CharField("Тип", max_length=20, choices=TYPE_CHOICES, default=TYPE_OTHER)
    created_at = models.DateTimeField("Загружен", auto_now_add=True)

    class Meta:
        verbose_name = "Медиафайл сайта"
        verbose_name_plural = "Медиафайлы сайта"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        from pathlib import PurePosixPath
        extension = PurePosixPath(self.file.name).suffix.lower() if self.file else ""
        if extension in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico", ".svg"}:
            self.media_type = self.TYPE_IMAGE
        elif extension in {".mp4", ".webm", ".mov"}:
            self.media_type = self.TYPE_VIDEO
        elif extension in {".pdf", ".doc", ".docx", ".xls", ".xlsx"}:
            self.media_type = self.TYPE_DOCUMENT
        elif not self.media_type:
            self.media_type = self.TYPE_OTHER
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class Promotion(models.Model):
    title = models.CharField("Название", max_length=220)
    description = models.TextField("Описание", blank=True)
    starts_at = models.DateTimeField("Начало действия", null=True, blank=True)
    ends_at = models.DateTimeField("Окончание действия", null=True, blank=True)
    is_active = models.BooleanField("Показывать на сайте", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    media = models.ManyToManyField(SiteMedia, verbose_name="Материалы из медиатеки", blank=True, related_name="promotions")
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ["sort_order", "-starts_at", "-created_at"]

    def __str__(self):
        return self.title

    @classmethod
    def visible(cls):
        now = timezone.now()
        return cls.objects.filter(is_active=True).filter(
            models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now),
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now),
        )

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "Дата окончания не может быть раньше даты начала."})

class SiteLink(models.Model):
    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="links")
    location = models.CharField("Где показывать", max_length=20, choices=[("header", "Шапка"), ("footer", "Подвал"), ("social", "Социальные сети")], default="header")
    label = models.CharField("Название ссылки", max_length=80)
    url = models.CharField("Адрес ссылки", max_length=500)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_visible = models.BooleanField("Показывать", default=True)

    class Meta:
        ordering = ["location", "sort_order", "pk"]
        verbose_name = "Ссылка сайта"
        verbose_name_plural = "Ссылки сайта"

    def __str__(self):
        return self.label
