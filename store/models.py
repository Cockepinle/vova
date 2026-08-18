from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField("Название", max_length=160, unique=True)
    slug = models.SlugField("URL-адрес", max_length=180, unique=True, blank=True, allow_unicode=True)
    image = models.ImageField("Изображение", upload_to="categories/", blank=True)
    image_url = models.URLField("Ссылка на изображение", blank=True)
    description = models.TextField("Описание", blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    @property
    def display_image_url(self):
        if self.image:
            return self.image.url

        return self.image_url


class Product(models.Model):
    STATUS_PUBLISHED = "published"
    STATUS_DRAFT = "draft"
    STATUS_HIDDEN = "hidden"

    AVAILABILITY_IN_STOCK = "in_stock"
    AVAILABILITY_PREORDER = "preorder"
    AVAILABILITY_OUT_OF_STOCK = "out_of_stock"

    AVAILABILITY_CHOICES = [
        (AVAILABILITY_IN_STOCK, "В наличии"),
        (AVAILABILITY_PREORDER, "Под заказ"),
        (AVAILABILITY_OUT_OF_STOCK, "Нет в наличии"),
    ]

    STATUS_CHOICES = [
        (STATUS_PUBLISHED, "Опубликовано"),
        (STATUS_DRAFT, "Черновик"),
        (STATUS_HIDDEN, "Скрыто"),
    ]

    category = models.ForeignKey(
        Category,
        verbose_name="Категория",
        related_name="products",
        on_delete=models.PROTECT,
    )
    name = models.CharField("Название", max_length=220)
    slug = models.SlugField("URL-адрес", max_length=240, unique=True, blank=True, allow_unicode=True)
    sku = models.CharField("Артикул", max_length=80, unique=True, blank=True, null=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена", max_digits=12, decimal_places=2)
    old_price = models.DecimalField("Старая цена", max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField("Единица измерения", max_length=40, default="шт")
    min_quantity = models.PositiveIntegerField("Минимальное количество", default=1)
    stock_quantity = models.PositiveIntegerField("Количество на складе", default=0)
    image = models.ImageField("Главное изображение", upload_to="products/", blank=True)
    image_url = models.URLField("Ссылка на главное изображение", blank=True)
    is_hit = models.BooleanField("Хит продаж", default=False)
    is_new = models.BooleanField("Новинка", default=False)
    availability = models.CharField(
        "Наличие",
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default=AVAILABILITY_IN_STOCK,
    )
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    @property
    def display_image_url(self):
        if self.image:
            return self.image.url

        return self.image_url


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name="Товар",
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField("Изображение", upload_to="product_gallery/", blank=True)
    image_url = models.URLField("Ссылка на изображение", blank=True)
    alt = models.CharField("Описание изображения", max_length=180, blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товара"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.alt or str(self.image) or self.image_url

    @property
    def display_url(self):
        if self.image:
            return self.image.url

        return self.image_url


class AttributeDefinition(models.Model):
    TYPE_TEXT = "text"
    TYPE_INTEGER = "integer"
    TYPE_DECIMAL = "decimal"
    TYPE_BOOLEAN = "boolean"
    TYPE_DATE = "date"
    TYPE_CHOICE = "choice"
    TYPE_PRICE = "price"
    TYPE_IMAGE = "image"
    TYPE_FILE = "file"
    TYPE_URL = "url"

    TYPE_CHOICES = [
        (TYPE_TEXT, "Текст"),
        (TYPE_INTEGER, "Целое число"),
        (TYPE_DECIMAL, "Дробное число"),
        (TYPE_PRICE, "Цена"),
        (TYPE_BOOLEAN, "Да/Нет"),
        (TYPE_DATE, "Дата"),
        (TYPE_CHOICE, "Список"),
        (TYPE_IMAGE, "Изображение"),
        (TYPE_FILE, "Файл"),
        (TYPE_URL, "Ссылка"),
    ]

    name = models.CharField("Название критерия", max_length=160, unique=True)
    slug = models.SlugField("URL-адрес", max_length=180, unique=True, blank=True, allow_unicode=True)
    value_type = models.CharField("Тип данных", max_length=20, choices=TYPE_CHOICES, default=TYPE_TEXT)
    unit = models.CharField("Единица измерения", max_length=40, blank=True)
    choices = models.JSONField("Варианты выбора", default=list, blank=True)
    is_required = models.BooleanField("Обязательное", default=False)
    default_value = models.CharField("Значение по умолчанию", max_length=255, blank=True)
    is_visible = models.BooleanField("Видимое", default=True)
    show_in_table = models.BooleanField("Показывать в таблице", default=True)
    is_filterable = models.BooleanField("Использовать в фильтрах", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Критерий товара"
        verbose_name_plural = "Критерии товаров"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class ProductAttribute(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name="Товар",
        related_name="attributes",
        on_delete=models.CASCADE,
    )
    attribute = models.ForeignKey(
        AttributeDefinition,
        verbose_name="Критерий",
        related_name="product_values",
        on_delete=models.PROTECT,
    )
    value_text = models.TextField("Текст", blank=True)
    value_integer = models.IntegerField("Целое число", null=True, blank=True)
    value_decimal = models.DecimalField("Дробное число", max_digits=14, decimal_places=3, null=True, blank=True)
    value_boolean = models.BooleanField("Да/Нет", null=True, blank=True)
    value_date = models.DateField("Дата", null=True, blank=True)
    value_choice = models.CharField("Выбор", max_length=160, blank=True)
    value_file = models.FileField("Файл", upload_to="product_fields/", blank=True)
    value_url = models.URLField("Ссылка", blank=True)

    class Meta:
        verbose_name = "Значение критерия"
        verbose_name_plural = "Значения критериев"
        unique_together = ["product", "attribute"]
        ordering = ["attribute__sort_order", "attribute__name"]

    def __str__(self):
        return f"{self.product}: {self.attribute}"

    def display_value(self):
        value_type = self.attribute.value_type

        if value_type == AttributeDefinition.TYPE_INTEGER:
            return self.value_integer
        if value_type in [AttributeDefinition.TYPE_DECIMAL, AttributeDefinition.TYPE_PRICE]:
            return self.value_decimal
        if value_type == AttributeDefinition.TYPE_BOOLEAN:
            return "Да" if self.value_boolean else "Нет"
        if value_type == AttributeDefinition.TYPE_DATE:
            return self.value_date
        if value_type == AttributeDefinition.TYPE_CHOICE:
            return self.value_choice
        if value_type in [AttributeDefinition.TYPE_IMAGE, AttributeDefinition.TYPE_FILE]:
            return self.value_file
        if value_type == AttributeDefinition.TYPE_URL:
            return self.value_url

        return self.value_text


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="customer_profile", on_delete=models.CASCADE)
    company = models.CharField("Компания", max_length=180, blank=True)
    phone = models.CharField("Телефон", max_length=80, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль клиента"
        verbose_name_plural = "Профили клиентов"

    def __str__(self):
        return self.user.email or self.user.username


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="cart_items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Товар", related_name="cart_items", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField("Количество", default=1)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Товар в корзине"
        verbose_name_plural = "Корзины пользователей"
        unique_together = ["user", "product"]

    def __str__(self):
        return f"{self.user}: {self.product} × {self.quantity}"


class FavoriteItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="favorite_items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Товар", related_name="favorite_items", on_delete=models.CASCADE)
    created_at = models.DateTimeField("Добавлено", auto_now_add=True)

    class Meta:
        verbose_name = "Избранный товар"
        verbose_name_plural = "Избранное пользователей"
        unique_together = ["user", "product"]

    def __str__(self):
        return f"{self.user}: {self.product}"


class Order(models.Model):
    STATUS_NEW = "new"
    STATUS_PROCESSING = "processing"
    STATUS_INVOICED = "invoiced"
    STATUS_PAID = "paid"
    STATUS_DONE = "done"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = [
        (STATUS_NEW, "Новый"),
        (STATUS_PROCESSING, "В обработке"),
        (STATUS_INVOICED, "Счёт выставлен"),
        (STATUS_PAID, "Оплачен"),
        (STATUS_DONE, "Выполнен"),
        (STATUS_CANCELED, "Отменён"),
    ]

    number = models.CharField("Номер заказа", max_length=32, unique=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="orders", on_delete=models.PROTECT)
    full_name = models.CharField("ФИО", max_length=180)
    phone = models.CharField("Телефон", max_length=80)
    email = models.EmailField("Email")
    company = models.CharField("Компания", max_length=180, blank=True)
    comment = models.TextField("Комментарий", blank=True)
    total = models.DecimalField("Итого", max_digits=14, decimal_places=2, default=0)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Заказ #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.number:
            self.number = f"PL-{self.created_at:%Y%m%d}-{self.pk:05d}"
            super().save(update_fields=["number"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name="Заказ", related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, verbose_name="Товар", related_name="order_items", on_delete=models.PROTECT)
    product_name = models.CharField("Название товара на момент заказа", max_length=220)
    product_sku = models.CharField("Артикул на момент заказа", max_length=80, blank=True)
    unit = models.CharField("Единица измерения", max_length=40, blank=True)
    quantity = models.PositiveIntegerField("Количество")
    price = models.DecimalField("Цена на момент заказа", max_digits=12, decimal_places=2)
    line_total = models.DecimalField("Сумма позиции", max_digits=14, decimal_places=2)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"


class CustomerRequest(models.Model):
    STATUS_NEW = "new"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"

    STATUS_CHOICES = [
        (STATUS_NEW, "Новая"),
        (STATUS_PROCESSING, "В работе"),
        (STATUS_DONE, "Закрыта"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Пользователь", related_name="requests", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField("Имя", max_length=160)
    company = models.CharField("Компания", max_length=180, blank=True)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=80, blank=True)
    text = models.TextField("Что нужно")
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} · {self.email}"


class EmailVerificationCode(models.Model):
    email = models.EmailField("Email")
    code = models.CharField("Код", max_length=6)
    payload = models.JSONField("Данные регистрации", default=dict)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    is_used = models.BooleanField("Использован", default=False)

    class Meta:
        verbose_name = "Код подтверждения email"
        verbose_name_plural = "Коды подтверждения email"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} · {self.code}"


class Employee(models.Model):
    STATUS_PUBLISHED = "published"
    STATUS_DRAFT = "draft"
    STATUS_HIDDEN = "hidden"

    STATUS_CHOICES = [
        (STATUS_PUBLISHED, "Опубликовано"),
        (STATUS_DRAFT, "Черновик"),
        (STATUS_HIDDEN, "Скрыто"),
    ]

    name = models.CharField("Имя", max_length=160)
    role = models.CharField("Должность", max_length=160)
    text = models.TextField("Описание", blank=True)
    image = models.ImageField("Фото", upload_to="employees/", blank=True)
    image_url = models.URLField("Ссылка на фото", blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Телефон", max_length=80, blank=True)
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def display_image_url(self):
        if self.image:
            return self.image.url

        return self.image_url


class SiteSettings(models.Model):
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
    PAGE_HOME = "home"
    PAGE_CATALOG = "catalog"
    PAGE_TEAM = "team"
    PAGE_CONTACTS = "contacts"

    PAGE_CHOICES = [
        (PAGE_HOME, "Главная"),
        (PAGE_CATALOG, "Каталог"),
        (PAGE_TEAM, "Команда"),
        (PAGE_CONTACTS, "Контакты"),
    ]

    page = models.CharField("Страница", max_length=40, choices=PAGE_CHOICES, unique=True)
    title = models.CharField("Заголовок", max_length=220, blank=True)
    subtitle = models.TextField("Подзаголовок / текст", blank=True)
    hero_label = models.CharField("Метка", max_length=160, blank=True)
    hero_button_text = models.CharField("Текст кнопки", max_length=120, blank=True)
    is_visible = models.BooleanField("Показывать", default=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Текст страницы"
        verbose_name_plural = "Тексты страниц"
        ordering = ["page"]

    def __str__(self):
        return self.get_page_display()
