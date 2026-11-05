from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    seo_title = models.CharField("Заголовок в поиске", max_length=220, blank=True)
    meta_description = models.TextField("Описание в поиске", blank=True)
    h1 = models.CharField("Заголовок страницы", max_length=220, blank=True)
    canonical = models.URLField("Основной адрес страницы (canonical)", blank=True, help_text="Обычно оставьте пустым: адрес определяется автоматически.")
    og_title = models.CharField("Заголовок при отправке ссылки", max_length=220, blank=True)
    og_description = models.TextField("Описание при отправке ссылки", blank=True)
    og_media = models.ForeignKey("SiteMedia", verbose_name="Изображение при отправке ссылки", on_delete=models.PROTECT, null=True, blank=True, related_name="%(class)s_og_uses")

    parent = models.ForeignKey("self", verbose_name="Родительская категория", related_name="children", on_delete=models.PROTECT, null=True, blank=True)
    name = models.CharField("Название", max_length=160, unique=True)
    slug = models.SlugField("URL-адрес", max_length=180, unique=True, blank=True, allow_unicode=True)
    image = models.ImageField("Изображение", upload_to="categories/", blank=True)
    image_media = models.ForeignKey("SiteMedia", verbose_name="Изображение из медиатеки", on_delete=models.PROTECT, null=True, blank=True, related_name="category_image_uses")
    image_url = models.URLField("Ссылка на изображение", blank=True)
    description = models.TextField("Описание", blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)
    filter_attributes = models.ManyToManyField(
        "AttributeDefinition",
        verbose_name="Фильтры каталога",
        blank=True,
        related_name="filter_categories",
        help_text="Выберите до пяти характеристик, которые покупатель сможет фильтровать в этой категории.",
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        visited = {self.pk} if self.pk else set()
        parent_id = self.parent_id
        while parent_id:
            if parent_id in visited:
                raise ValidationError({"parent": "Категория не может быть вложена в себя или своего потомка."})
            visited.add(parent_id)
            parent_id = Category.objects.filter(pk=parent_id).values_list("parent_id", flat=True).first()

    @classmethod
    def tree_rows(cls, visible_only=False):
        """One query, arbitrary depth; a hidden ancestor hides its entire branch."""
        children = {}
        for category in cls.objects.all():
            children.setdefault(category.parent_id, []).append(category)
        stack = [(item, 0, "") for item in reversed(children.get(None, []))]
        result, seen = [], set()
        while stack:
            item, depth, path = stack.pop()
            if item.pk in seen or (visible_only and not item.is_active):
                continue
            seen.add(item.pk)
            item.tree_depth = depth
            item.tree_label = f"{path} / {item.name}" if path else item.name
            result.append(item)
            stack.extend((child, depth + 1, item.tree_label) for child in reversed(children.get(item.pk, [])))
        return result

    @classmethod
    def visible_ids(cls):
        return [item.pk for item in cls.tree_rows(visible_only=True)]

    def descendant_ids(self):
        children = {}
        for pk, parent_id in Category.objects.values_list("pk", "parent_id"):
            children.setdefault(parent_id, []).append(pk)
        found, stack = set(), [self.pk]
        while stack:
            pk = stack.pop()
            if pk in found:
                continue
            found.add(pk)
            stack.extend(children.get(pk, []))
        return found

    def save(self, *args, **kwargs):
        self.clean()
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    @property
    def display_image_url(self):
        if self.image_media_id:
            return self.image_media.file.url
        if self.image:
            return self.image.url

        return self.image_url

class VariantGroup(models.Model):
    name = models.CharField("Название группы", max_length=220, unique=True)
    attributes = models.ManyToManyField(
        "AttributeDefinition",
        verbose_name="Параметры модификаций",
        blank=True,
        related_name="variant_groups",
        help_text="Характеристики, по которым покупатель различает варианты: цвет, размер, упаковка и другие.",
    )

    class Meta:
        verbose_name = "Группа модификаций"
        verbose_name_plural = "Группы модификаций"
        ordering = ["name"]

    def __str__(self):
        return self.name

class Product(models.Model):
    seo_title = models.CharField("Заголовок в поиске", max_length=220, blank=True)
    meta_description = models.TextField("Описание в поиске", blank=True)
    h1 = models.CharField("Заголовок страницы", max_length=220, blank=True)
    canonical = models.URLField("Основной адрес страницы (canonical)", blank=True, help_text="Обычно оставьте пустым: адрес определяется автоматически.")
    og_title = models.CharField("Заголовок при отправке ссылки", max_length=220, blank=True)
    og_description = models.TextField("Описание при отправке ссылки", blank=True)
    og_media = models.ForeignKey("SiteMedia", verbose_name="Изображение при отправке ссылки", on_delete=models.PROTECT, null=True, blank=True, related_name="%(class)s_og_uses")

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
    keywords = models.TextField("Ключевые слова", blank=True, help_text="Скрытые поисковые слова через запятую. Покупатели их не видят.")
    variant_group = models.ForeignKey(
        VariantGroup,
        verbose_name="Группа модификаций",
        related_name="products",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    price = models.DecimalField("Цена", max_digits=12, decimal_places=2)
    cost_price = models.DecimalField("Себестоимость", max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    retail_coefficient = models.DecimalField("Коэффициент розничной цены", max_digits=10, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)], help_text="Если указан, розничная цена = себестоимость × коэффициент.")
    wholesale_coefficient = models.DecimalField("Коэффициент оптовой цены", max_digits=10, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)])
    special_coefficient = models.DecimalField("Коэффициент спеццены", max_digits=10, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0)])
    vat_rate = models.DecimalField("НДС, %", max_digits=5, decimal_places=2, default=Decimal("22.00"), validators=[MinValueValidator(0), MaxValueValidator(100)])
    length_mm = models.DecimalField("Длина, мм", max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    width_mm = models.DecimalField("Ширина, мм", max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    height_mm = models.DecimalField("Высота, мм", max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    weight_kg = models.DecimalField("Вес, кг", max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0)])
    media = models.ManyToManyField("SiteMedia", verbose_name="Видео и файлы из медиатеки", blank=True, related_name="products", help_text="Фотографии, видео MP4/WebM и документы PDF. Файлы загружаются в общей медиатеке.")
    old_price = models.DecimalField("Старая цена", max_digits=12, decimal_places=2, null=True, blank=True)
    unit = models.CharField("Единица измерения", max_length=40, default="шт")
    min_quantity = models.PositiveIntegerField("Минимальное количество", default=1)
    stock_quantity = models.PositiveIntegerField("Количество на складе", default=0)
    image = models.ImageField("Главное изображение", upload_to="products/", blank=True)
    image_url = models.URLField("Ссылка на главное изображение", blank=True)
    is_hit = models.BooleanField("Хит продаж", default=False)
    is_new = models.BooleanField("Новинка", default=False)
    is_special = models.BooleanField("Спецпредложение", default=False)
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
        constraints = [
            models.CheckConstraint(condition=models.Q(vat_rate__gte=0, vat_rate__lte=100), name="product_valid_vat"),
            *[models.CheckConstraint(condition=models.Q(**{f"{field}__gte": 0}) | models.Q(**{f"{field}__isnull": True}), name=f"product_{field}_nonnegative") for field in ["cost_price", "length_mm", "width_mm", "height_mm", "weight_kg", "retail_coefficient", "wholesale_coefficient", "special_coefficient"]],
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    @property
    def display_image_url(self):
        primary = self.images.select_related("media").filter(is_primary=True).first()
        if primary and primary.display_url:
            return primary.display_url
        if self.image:
            return self.image.url

        return self.image_url

    @property
    def volume_m3(self):
        dimensions = (self.length_mm, self.width_mm, self.height_mm)
        if any(value is None for value in dimensions):
            return None
        with localcontext() as context:
            context.prec = 40
            length_m, width_m, height_m = (Decimal(value) / Decimal("1000") for value in dimensions)
            return length_m * width_m * height_m

class CustomerPrice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Покупатель", on_delete=models.CASCADE, related_name="individual_prices")
    product = models.ForeignKey(Product, verbose_name="Товар", on_delete=models.CASCADE, related_name="individual_prices")
    price = models.DecimalField("Индивидуальная цена", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "Индивидуальная цена"
        verbose_name_plural = "Индивидуальные цены"
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_customer_product_price"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="customer_price_nonnegative"),
        ]

    def __str__(self):
        return f"{self.user}: {self.product} — {self.price}"

class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name="Товар",
        related_name="images",
        on_delete=models.CASCADE,
    )
    image = models.ImageField("Изображение", upload_to="product_gallery/", blank=True)
    image_url = models.URLField("Ссылка на изображение", blank=True)
    media = models.ForeignKey(
        "SiteMedia",
        verbose_name="Файл из медиатеки",
        related_name="product_links",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    alt = models.CharField("Описание изображения", max_length=180, blank=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_primary = models.BooleanField("Главное изображение", default=False)

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товара"
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product"], condition=models.Q(is_primary=True), name="one_primary_media_per_product"),
        ]

    def __str__(self):
        return self.alt or str(self.image) or self.image_url

    @property
    def display_url(self):
        if self.media_id and self.media.file:
            return self.media.file.url
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
