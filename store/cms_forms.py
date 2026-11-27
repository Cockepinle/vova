import re

from django import forms
from django.forms import formset_factory
from django.db.models import Q
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from uuid import uuid4

from .models import CustomerPrice, CustomerProfile, AttributeDefinition, Category, DeliveryMethod, Employee, PageContent, PaymentMethod, Product, ProductAttribute, Promotion, SiteMedia, SiteSettings, SiteLink, VariantGroup
from .models import CustomerRequest
from .uploads import configure_image_uploads, upload_policy, validate_upload



SEO_FIELDS = ["seo_title", "meta_description", "h1", "canonical", "og_title", "og_description", "og_media"]

COEFFICIENT_FIELDS = ("retail_coefficient", "wholesale_coefficient", "special_coefficient")
COEFFICIENT_HELP = "Например, 1,20 (или 1.20) увеличивает базовую цену на 20%. Допустимо до четырёх знаков после разделителя."


class PricingDecimalField(forms.DecimalField):
    widget = forms.TextInput(attrs={"inputmode": "decimal"})

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if value and not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
                raise forms.ValidationError("Введите число с запятой или точкой.")
        return super().to_python(value)


def parse_individual_price(raw):
    from .pricing import as_money

    field = PricingDecimalField(max_digits=12, decimal_places=2, min_value=0)
    return as_money(field.clean(raw))


class CustomerPricingForm(forms.ModelForm):
    retail_coefficient = PricingDecimalField(max_digits=10, decimal_places=4, min_value=0, required=False, label="Коэффициент розницы")
    wholesale_coefficient = PricingDecimalField(max_digits=10, decimal_places=4, min_value=0, required=False, label="Коэффициент опта")
    special_coefficient = PricingDecimalField(max_digits=10, decimal_places=4, min_value=0, required=False, label="Коэффициент спеццены")

    class Meta:
        model = CustomerProfile
        fields = ("price_level", *COEFFICIENT_FIELDS)

    def clean(self):
        from django.db.models import Max
        from .pricing import MAX_UNIT_PRICE, calculate_unit_price

        data = super().clean()
        level = data.get("price_level")
        field = f"{level}_coefficient"
        coefficient = data.get(field)
        if coefficient is not None and ("price_level" in self.changed_data or field in self.changed_data):
            max_cost = Product.objects.aggregate(value=Max("cost_price"))["value"]
            if max_cost is not None and calculate_unit_price(max_cost, coefficient) > MAX_UNIT_PRICE:
                self.add_error(field, "Этот коэффициент даёт цену выше допустимого предела для одного из товаров.")
        return data


class CustomerIdentityForm(forms.Form):
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    email = forms.EmailField(label="Email", max_length=254, required=False)

    def __init__(self, *args, customer, **kwargs):
        self.customer = customer
        super().__init__(*args, initial={name: getattr(customer, name) for name in self.base_fields}, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        old_email = self.customer.email.lower()
        self.uses_email_login = self.customer.username.lower() == old_email or self.customer.username.lower() == email
        if not email and self.uses_email_login:
            raise forms.ValidationError("Укажите email для входа покупателя.")
        if self.uses_email_login and len(email) > self.customer._meta.get_field("username").max_length:
            raise forms.ValidationError("Этот email слишком длинный для входа в аккаунт.")
        if email and email != old_email:
            users = type(self.customer).objects.exclude(pk=self.customer.pk)
            if users.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
                raise forms.ValidationError("Этот email уже используется другим аккаунтом.")
        return email

    def save(self):
        fields = ["first_name", "last_name", "email"]
        for name in fields:
            setattr(self.customer, name, self.cleaned_data[name])
        if self.uses_email_login:
            self.customer.username = self.cleaned_data["email"]
            fields.append("username")
        self.customer.save(update_fields=fields)


class CustomerDetailsForm(forms.ModelForm):
    delivery_addresses = forms.CharField(
        label="Адреса доставки", required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Один адрес на строку"}),
    )

    class Meta:
        model = CustomerProfile
        fields = ("company", "contact_person", "phone", "inn", "kpp", "status", "delivery_addresses", "comment")
        widgets = {"comment": forms.Textarea(attrs={"rows": 3}), "phone": forms.TextInput(attrs={"type": "tel"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["delivery_addresses"] = "\n".join(str(value) for value in (self.instance.delivery_addresses or []))
        self.fields["status"].widget.attrs["list"] = "customer-statuses"

    def clean_delivery_addresses(self):
        return [line.strip() for line in self.cleaned_data["delivery_addresses"].splitlines() if line.strip()]


def validate_content_link(value):
    from urllib.parse import urlsplit
    if not value:
        return
    parsed = urlsplit(value)
    if "\\" in value or any(ord(char) < 32 for char in value) or value.startswith("//"):
        raise forms.ValidationError("Укажите адрес страницы от / или полную ссылку https://.")
    if not (value.startswith("/") or value.startswith("#") or (parsed.scheme in {"http", "https"} and parsed.netloc) or (parsed.scheme in {"mailto", "tel"} and parsed.path)):
        raise forms.ValidationError("Допустимы ссылки /catalog/, https://example.ru, mailto: и tel:.")


class MediaPickerOption:
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        media = getattr(value, "instance", None)
        if selected and media and media.file:
            option["attrs"].update({
                "data-url": media.file.url, "data-alt": media.alt,
                "data-type": SiteMedia.TYPE_IMAGE if media.is_image else media.media_type,
            })
        return option


class MediaPickerSelect(MediaPickerOption, forms.Select):
    pass


class MediaPickerSelectMultiple(MediaPickerOption, forms.SelectMultiple):
    pass


def configure_media_fields(fields):
    for field in fields.values():
        if getattr(getattr(field, "queryset", None), "model", None) is not SiteMedia:
            continue
        multiple = isinstance(field, forms.ModelMultipleChoiceField)
        widget_class = MediaPickerSelectMultiple if multiple else MediaPickerSelect
        field.widget = widget_class({**field.widget.attrs, "data-media-field": "all" if multiple else "image"})
        field.widget.choices = field.choices


class ImageUploadMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure_image_uploads(self)


class ContentValidationMixin(ImageUploadMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure_media_fields(self.fields)

    def clean(self):
        data = super().clean()
        for name, value in list(data.items()):
            if (name.endswith("_url") or name == "url") and isinstance(value, str) and value:
                try:
                    validate_content_link(value)
                except forms.ValidationError as error:
                    self.add_error(name, error)
            if name.endswith("_media") and value:
                if not value.is_image:
                    self.add_error(name, "Выберите изображение, а не документ или видео.")
        from urllib.parse import urlsplit
        for name in ["public_url", "canonical"]:
            value = data.get(name)
            if value and urlsplit(value).scheme not in {"http", "https"}:
                self.add_error(name, "Укажите полный адрес http:// или https://.")
        value = data.get("public_url")
        if value and (urlsplit(value).path not in {"", "/"} or urlsplit(value).query or urlsplit(value).fragment):
            self.add_error("public_url", "Укажите только домен без пути, параметров и якоря.")
        return data


class ManagementLoginForm(AuthenticationForm):
    username = forms.CharField(label="Логин", max_length=254, widget=forms.TextInput(attrs={"placeholder": "Введите логин"}))
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"placeholder": "Введите пароль"}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError("Неверный логин или пароль.", code="invalid_login")


class ProductExcelImportForm(forms.Form):
    file = forms.FileField(label="Файл Excel", widget=forms.FileInput(attrs={"accept": ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}))

    def clean_file(self):
        value = self.cleaned_data["file"]
        if not value.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Загрузите файл в формате .xlsx.")
        if value.size > 15 * 1024 * 1024:
            raise forms.ValidationError("Размер Excel-файла не должен превышать 15 МБ.")
        return value


def category_choices(field, excluded=()):
    rows = [row for row in Category.tree_rows() if row.pk not in excluded]
    field.queryset = Category.objects.filter(pk__in=[row.pk for row in rows])
    field.choices = [("", "---------")] + [(row.pk, row.tree_label) for row in rows]


class ProductForm(ContentValidationMixin, forms.ModelForm):
    promotions = forms.ModelMultipleChoiceField(
        label="Акции", queryset=Promotion.objects.all(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    sku = forms.CharField(label="Артикул", required=False, empty_value=None)
    volume_m3 = forms.DecimalField(label="Объём, м³ (автоматически)", required=False, disabled=True, max_digits=36, decimal_places=15)
    new_variant_group = forms.CharField(max_length=VariantGroup._meta.get_field("name").max_length, label="Новая группа модификаций", required=False, help_text="Заполните, чтобы создать группу и сразу добавить в неё товар.")
    cost_price = PricingDecimalField(label="Базовая цена (себестоимость)", required=False, max_digits=12, decimal_places=2, min_value=0)
    price = PricingDecimalField(label="Ручная розничная цена", required=False, max_digits=12, decimal_places=2, min_value=0)
    retail_coefficient = PricingDecimalField(label="Коэффициент розницы", required=False, max_digits=10, decimal_places=4, min_value=0)
    wholesale_coefficient = PricingDecimalField(label="Коэффициент опта", required=False, max_digits=10, decimal_places=4, min_value=0)
    special_coefficient = PricingDecimalField(label="Коэффициент спеццены", required=False, max_digits=10, decimal_places=4, min_value=0)
    old_price = PricingDecimalField(label="Старая цена", required=False, max_digits=12, decimal_places=2, min_value=0)

    def __init__(self, *args, gallery_editor=False, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial.setdefault("promotions", list(self.instance.promotions.values_list("pk", flat=True)))
        category_choices(self.fields["category"])
        self.fields["variant_group"].empty_label = "Без группы модификаций"
        if gallery_editor:
            media = self.fields["media"]
            media.queryset = media.queryset.exclude(Q(media_type=SiteMedia.TYPE_IMAGE) & ~Q(file__iendswith=".svg"))
            media.label = "Видео и документы"
            media.help_text = ""
            media.widget.attrs["data-media-field"] = "attachment"
        self.fields["volume_m3"].initial = self.instance.volume_m3
        for name in ("min_quantity", "quantity_step"):
            self.fields[name].widget.attrs["min"] = 1
        if self.is_bound:
            missing_fields = [name for name in ("vat_rate", "quantity_step", "image_url", "variant_sort_order") if name not in self.data]
            if missing_fields:
                self.data = self.data.copy()
                for name in missing_fields:
                    self.data[name] = getattr(self.instance, name)

        help_texts = {
            "slug": "Часть адреса страницы товара. Например: korobka-330x330-belaya.",
            "h1": "Главный видимый заголовок страницы. Если оставить пустым, используется название товара.",
            "seo_title": "Заголовок вкладки браузера и результата поиска. Если пусто, используется название товара.",
            "meta_description": "Краткое описание для поисковых систем. Если пусто, используется описание товара.",
            "canonical": "Полный основной адрес страницы. Обычно оставьте пустым: адрес сформируется автоматически.",
            "og_title": "Заголовок при публикации ссылки в соцсетях.",
            "og_description": "Описание при публикации ссылки в соцсетях.",
            "og_media": "Изображение из медиатеки для публикации ссылки.",
            "recommended_products": "Товары для блока «Рекомендуем к этому товару».",
            "accessory_products": "Товары для блока «С этим товаром покупают».",
            "cost_price": "От этой суммы рассчитываются цены по коэффициентам.",
            "price": "Применяется, когда розничный коэффициент не задан. При включённом расчёте здесь хранится рассчитанная розничная цена.",
            "min_quantity": "Стартовое количество в корзине.",
            "quantity_step": "Шаг от минимального количества. Например, при минимуме 2 и шаге 3 можно заказать 2, 5 или 8 единиц.",
        }
        for name, help_text in help_texts.items():
            self.fields[name].help_text = help_text
        for name in ("recommended_products", "accessory_products"):
            field = self.fields[name]
            field.widget = forms.CheckboxSelectMultiple(choices=field.choices)
            field.queryset = field.queryset.prefetch_related("images__media").order_by("name", "pk")
            if self.instance.pk:
                field.queryset = field.queryset.exclude(pk=self.instance.pk)

    def _save_m2m(self):
        super()._save_m2m()
        if self.add_prefix("promotion_selection") in self.data or self.add_prefix("promotions") in self.data:
            self.instance.promotions.set(self.cleaned_data["promotions"])

    @property
    def groups(self):
        sections = [
            ("Основная информация", ["category", "name", "sku", "description", "keywords", "status"]),
            ("Цены", ["cost_price", "price", "retail_coefficient", "wholesale_coefficient", "special_coefficient", "old_price", "vat_rate"]),
            ("Остатки и продажа", ["unit", "min_quantity", "quantity_step", "stock_quantity", "availability", "is_hit", "is_new", "is_special"]),
            ("Связанные товары", ["recommended_products", "accessory_products"]),
            ("Модификации товара", ["variant_group", "new_variant_group", "variant_sort_order"]),
            ("Габариты и вес", ["length_mm", "width_mm", "height_mm", "weight_kg", "volume_m3"]),
            ("SEO страницы товара", ["slug", "h1", "seo_title", "meta_description", "canonical"]),
            ("Отображение ссылки в соцсетях", ["og_title", "og_description", "og_media"]),
            ("Файлы товара", ["media"]),
        ]
        return [(title, [self[name] for name in names]) for title, names in sections]


    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "sku",
            "slug",
            *SEO_FIELDS,
            "description",
            "keywords",
            "variant_group",
            "new_variant_group",
            "variant_sort_order",
            "price",
            "old_price",
            "cost_price", "retail_coefficient", "wholesale_coefficient", "special_coefficient", "vat_rate", "length_mm", "width_mm", "height_mm", "weight_kg", "media",
            "unit",
            "min_quantity",
            "quantity_step",
            "recommended_products",
            "accessory_products",
            "stock_quantity",
            "image",
            "image_url",
            "is_hit",
            "is_new",
            "is_special",
            "availability",
            "status",
        ]
        labels = {
            "category": "Категория",
            "name": "Название",
            "sku": "Артикул",
            "description": "Описание",
            "keywords": "Ключевые слова",
            "price": "Цена",
            "old_price": "Старая цена",
            "unit": "Единица измерения",
            "min_quantity": "Минимальное количество",
            "quantity_step": "Кратность заказа",
            "stock_quantity": "Количество на складе",
            "image": "Главное изображение",
            "image_url": "Или ссылка на главное изображение",
            "is_hit": "Хит продаж",
            "is_new": "Новинка",
            "availability": "Наличие",
            "status": "Статус",
        }
        widgets = {
            "image": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def clean(self):
        from django.db.models import Max
        from .pricing import MAX_UNIT_PRICE, calculate_unit_price

        data = super().clean()
        if name := data.get("name"):
            if "slug" in data:
                if not data["slug"] and self.instance.pk and self.instance.slug:
                    data["slug"] = self.instance.slug
                elif not data["slug"] or self.data.get("auto_slug") == "1":
                    data["slug"] = self.instance.available_slug(name)
            for field in ("h1", "seo_title"):
                if field in data and not data[field]:
                    data[field] = getattr(self.instance, field) or name[:self.fields[field].max_length]
        if data.get("new_variant_group") and data.get("variant_group"):
            self.add_error("new_variant_group", "Выберите существующую группу или создайте новую.")
        minimum = data.get("min_quantity")
        step = data.get("quantity_step")
        if minimum is not None and minimum < 1:
            self.add_error("min_quantity", "Минимальное количество должно быть не меньше 1.")
        if step is not None and step < 1:
            self.add_error("quantity_step", "Кратность заказа должна быть не меньше 1.")
        base = data.get("cost_price")
        coefficients = {name: data.get(name) for name in COEFFICIENT_FIELDS}
        if base is None and any(value is not None for value in coefficients.values()):
            self.add_error("cost_price", "Укажите себестоимость для расчёта цен по коэффициентам.")
        if base is not None:
            for name, coefficient in coefficients.items():
                if coefficient is not None and calculate_unit_price(base, coefficient) > MAX_UNIT_PRICE:
                    self.add_error(name, "Расчётная цена превышает допустимый предел.")
            if "cost_price" in self.changed_data:
                active_coefficients = CustomerProfile.objects.aggregate(**{
                    name: Max(name, filter=Q(price_level=name.removesuffix("_coefficient")))
                    for name in COEFFICIENT_FIELDS
                })
                highest = max((value for value in active_coefficients.values() if value is not None), default=None)
                if highest is not None and calculate_unit_price(base, highest) > MAX_UNIT_PRICE:
                    self.add_error("cost_price", "С действующим коэффициентом клиента эта базовая цена превышает предел цены товара.")
        retail = coefficients["retail_coefficient"]
        if base is not None and retail is not None and "retail_coefficient" in data:
            self.errors.pop("price", None)
            data["price"] = calculate_unit_price(base, retail)
        elif "price" in data and data["price"] is None:
            self.add_error("price", "Укажите ручную розничную цену или задайте базовую цену и коэффициент розницы.")
        return data

    def save(self, commit=True):
        product = super().save(commit=False)
        new_group_name = self.cleaned_data.get("new_variant_group", "").strip()
        if new_group_name:
            product.variant_group, _ = VariantGroup.objects.get_or_create(name=new_group_name)
        if commit:
            product.save()
            self.save_m2m()
        return product


class CategoryForm(ContentValidationMixin, forms.ModelForm):
    remove_image = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        excluded = self.instance.descendant_ids() if self.instance.pk else ()
        category_choices(self.fields["parent"], excluded)
        self.fields["filter_attributes"].queryset = AttributeDefinition.objects.filter(is_filterable=True, is_visible=True).order_by("sort_order", "name")
        self.fields["image_media"].widget = forms.HiddenInput()
        self.original_image = (self.instance.image.name, self.instance.image_media_id, self.instance.image_url)
        self.fields["sort_order"].required = False
        help_texts = {
            "parent": "Выберите родительскую категорию. Пустое значение создаёт раздел верхнего уровня.",
            "slug": "Часть адреса категории. Например: gofrokarton.",
            "h1": "Главный видимый заголовок страницы. Если пусто, используется название категории.",
            "seo_title": "Заголовок вкладки браузера и результата поиска. Если пусто, используется название категории.",
            "meta_description": "Описание для поисковых систем. Если пусто, используется описание категории.",
            "canonical": "Полный основной адрес страницы. Обычно оставьте пустым: адрес сформируется автоматически.",
        }
        for name, help_text in help_texts.items():
            self.fields[name].help_text = help_text

    @property
    def groups(self):
        sections = [
            ("Категория и вложенность", ["name", "parent", "sort_order", "is_active"]),
            ("Содержимое каталога", ["description"]),
            ("SEO категории", ["slug", "h1", "seo_title", "meta_description", "canonical"]),
            ("Отображение ссылки в соцсетях", ["og_title", "og_description", "og_media"]),
        ]
        return [(title, [self[name] for name in names]) for title, names in sections]

    def clean_filter_attributes(self):
        values = self.cleaned_data["filter_attributes"]
        if values.count() > 5:
            raise forms.ValidationError("Для одной категории можно выбрать не более пяти фильтров.")
        return values

    def clean_image_media(self):
        media = self.cleaned_data["image_media"]
        if media and (not media.file or not media.is_image):
            raise forms.ValidationError("Выберите изображение с файлом в медиатеке.")
        return media

    def clean(self):
        data = super().clean()
        if data.get("sort_order") is None:
            data["sort_order"] = self.instance.sort_order
        if data.get("name") and "slug" in data and not data["slug"]:
            slug = self.instance.slug or self.instance.available_slug(data["name"])
            if not slug:
                self.add_error("slug", "Укажите адрес категории буквами или цифрами.")
            else:
                data["slug"] = slug
        return data

    def save(self, commit=True):
        category = super().save(commit=False)
        image, media_id, url = self.original_image
        if self.cleaned_data["remove_image"]:
            category.image, category.image_media_id, category.image_url = "", None, ""
        elif self.files.get(self.add_prefix("image")):
            category.image_media_id, category.image_url = None, ""
        elif self.cleaned_data["image_url"] and "image_url" in self.changed_data:
            category.image, category.image_media_id = "", None
        elif self.cleaned_data["image_media"]:
            category.image, category.image_url = "", ""
        elif self.cleaned_data["image_url"]:
            category.image, category.image_media_id = "", None
        else:
            category.image, category.image_media_id, category.image_url = image, media_id, url
        if commit:
            category.save()
            if self.add_prefix("filter_attributes") in self.data:
                self.save_m2m()
        return category

    class Meta:
        model = Category
        fields = ["name", "parent", "sort_order", "slug", "image_media", "image", "image_url", "description", "filter_attributes", "is_active", *SEO_FIELDS]
        labels = {
            "name": "Название",
            "image": "Изображение",
            "image_url": "Или ссылка на изображение",
            "description": "Описание",
            "is_active": "Активна",
        }
        widgets = {
            "image": forms.FileInput(attrs={"accept": "image/*"}),
        }


class PromotionProductChoices(forms.CheckboxSelectMultiple):
    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        option["attrs"]["data-category"] = option["value"].instance.category_id
        return option


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = ["title", "description", "conditions", "starts_at", "ends_at", "is_active", "sort_order", "media", "products"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "conditions": forms.Textarea(attrs={"rows": 4}),
            "products": PromotionProductChoices(),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "media": forms.SelectMultiple(attrs={"size": 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure_media_fields(self.fields)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["media"].queryset = SiteMedia.objects.order_by("-created_at")
        self.fields["media"].help_text = "Выберите один или несколько файлов из общей медиатеки."
        self.fields["products"].queryset = Product.objects.order_by("name", "sku", "pk")
        self.fields["products"].label_from_instance = lambda product: f"{product.name} · {product.sku}"


class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ["name", "code", "kind", "provider_code", "is_active", "sort_order"]
        help_texts = {"provider_code": "Оставьте пустым, пока конкретный онлайн-провайдер не подключён."}


class DeliveryMethodForm(forms.ModelForm):
    class Meta:
        model = DeliveryMethod
        fields = ["name", "code", "kind", "description", "provider_code", "handoff_url", "provider_config", "is_active", "sort_order"]
        help_texts = {
            "provider_code": "Код зарегистрированного delivery provider. API перевозчиков пока не подключены.",
            "handoff_url": "Необязательная ссылка на портал перевозчика для ручного расчёта.",
            "provider_config": "JSON-параметры для будущей интеграции. Не храните здесь секретные ключи.",
        }
        widgets = {"provider_config": forms.Textarea(attrs={"rows": 6, "spellcheck": "false"})}


class EmployeeForm(ImageUploadMixin, forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["name", "role", "text", "image", "image_url", "email", "phone", "status"]
        labels = {
            "name": "Имя",
            "role": "Должность",
            "text": "Описание",
            "image": "Фото",
            "image_url": "Или ссылка на фото",
            "email": "Email",
            "phone": "Телефон",
            "status": "Статус",
        }
        widgets = {
            "image": forms.FileInput(attrs={"accept": "image/*"}),
            "phone": forms.TextInput(attrs={"class": "js-phone-mask", "placeholder": "+7 (___) ___-__-__"}),
        }

class CustomerRequestForm(forms.ModelForm):
    version = forms.CharField(widget=forms.HiddenInput(), error_messages={
        "required": "Откройте запрос заново перед сохранением.",
    })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["version"] = self.instance.updated_at.isoformat()
        self.fields["email"].error_messages["invalid"] = "Введите корректный email."
        self.fields["status"].error_messages["invalid_choice"] = "Выберите статус из списка."
        if self.is_bound:
            self.data = self.data.copy()
            for name in ("company", "phone", "admin_comment"):
                self.data.setdefault(self.add_prefix(name), self.initial[name])

    def clean_version(self):
        version = self.cleaned_data["version"]
        if version != self.initial["version"]:
            raise forms.ValidationError("Запрос уже изменён. Откройте актуальную карточку перед сохранением.")
        return version

    class Meta:
        model = CustomerRequest
        fields = ("name", "company", "email", "phone", "request_type", "text", "status", "admin_comment")
        widgets = {"text": forms.Textarea(attrs={"rows": 8}), "admin_comment": forms.Textarea(attrs={"rows": 5})}


class SiteSettingsForm(ContentValidationMixin, forms.ModelForm):
    remove_logo = forms.BooleanField(label="Удалить логотип", required=False, widget=forms.HiddenInput())

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("remove_logo"):
            cleaned_data["logo_image"] = False
            cleaned_data["logo_media"] = None
        elif self.files.get("logo_image"):
            cleaned_data["logo_media"] = None
        elif self.data.get("logo_media"):
            cleaned_data["logo_image"] = False
        return cleaned_data

    @property
    def groups(self):
        sections = [
            ("Компания", ["site_name", "company_name", "company_inn", "company_kpp"]),
            ("Логотип и оформление", ["logo_text", "logo_alt", "logo_media", "favicon_media"]),
            ("Показатели на главной", [f"stat_{index}_{part}" for index in range(1, 5) for part in ("value", "label")]),
            ("Общие контакты и доставка", ["contact_phone", "contact_email", "contact_email_b2b", "contact_address", "pickup_address", "contact_work_hours"]),
            ("Шапка и основная кнопка", ["header_phone", "header_email", "show_header_contacts", "show_header_account", "show_header_favorites", "show_header_cta", "cta_label", "cta_url"]),
            ("Подвал и юридическая информация", [name for name in self.fields if name.startswith("footer_")] + ["copyright_text"]),
            ("Поиск и отправка ссылок", ["public_url", "seo_description", "og_media", "allow_indexing"]),
            ("Валюта магазина", ["currency_code", "currency_symbol", "currency_decimals"]),
            ("Настройки заказа", [
                "track_abandoned_carts", "mark_products_in_orders", "show_zero_price_note",
                "zero_price_note_text", "hide_cart_login", "stock_change_mode",
                "track_referrer", "manage_transactions", "allow_repeat_orders", "checkout_steps",
            ]),
        ]
        return [(title, [self[name] for name in names]) for title, names in sections]

    class Meta:
        model = SiteSettings
        widgets = {"logo_image": forms.FileInput()}
        fields = [
            "site_name", "logo_text", "logo_media", "favicon_media",
            *[f"stat_{index}_{part}" for index in range(1, 5) for part in ("value", "label")], "public_url", "seo_description", "og_media", "allow_indexing",
            "cta_label", "cta_url", "show_header_contacts", "show_header_account", "show_header_favorites", "show_header_cta", "footer_extra_text", "footer_legal_text",
            "contact_phone",
            "currency_code", "currency_symbol", "currency_decimals",
            "track_abandoned_carts", "mark_products_in_orders", "show_zero_price_note",
            "zero_price_note_text", "hide_cart_login", "stock_change_mode",
            "track_referrer", "manage_transactions", "allow_repeat_orders", "checkout_steps",
            "contact_email",
            "contact_email_b2b",
            "contact_address",
            "pickup_address",
            "contact_work_hours",
            "company_name",
            "company_inn",
            "company_kpp",
            "logo_image", "logo_alt",
            "header_phone", "header_email",
            "footer_privacy_label", "footer_privacy_url", "footer_offer_label", "footer_offer_url",
            "footer_company", "footer_description", "footer_phone", "footer_email", "footer_address", "footer_work_time", "copyright_text",
        ]
        labels = {
            "home_hero_label": "Надпись-метка",
            "home_hero_title": "Заголовок",
            "home_hero_subtitle": "Подзаголовок",
            "catalog_title": "Заголовок",
            "catalog_subtitle": "Подзаголовок",
            "team_hero_label": "Надпись-метка",
            "team_hero_title": "Заголовок",
            "team_hero_subtitle": "Подзаголовок",
            "contacts_hero_label": "Надпись-метка",
            "contacts_hero_title": "Заголовок",
            "contacts_form_title": "Заголовок формы",
            "contacts_b2b_title": "Заголовок B2B",
            "contacts_b2b_subtitle": "Подзаголовок B2B",
            "contacts_b2b_text": "Текст B2B",
            "stat_1_value": "Значение 1",
            "stat_1_label": "Подпись 1",
            "stat_2_value": "Значение 2",
            "stat_2_label": "Подпись 2",
            "stat_3_value": "Значение 3",
            "stat_3_label": "Подпись 3",
            "stat_4_value": "Значение 4",
            "stat_4_label": "Подпись 4",
            "contact_phone": "Телефон",
            "contact_email": "Email",
            "contact_email_b2b": "Email B2B",
            "contact_address": "Адрес",
            "contact_work_hours": "Часы работы",
            "company_name": "Компания",
            "company_inn": "ИНН",
            "company_kpp": "КПП",
        }


class PageContentForm(ContentValidationMixin, forms.ModelForm):
    remove_hero = forms.BooleanField(required=False, widget=forms.HiddenInput())
    page_type = forms.ChoiceField(
        label="Тип страницы",
        choices=[("fixed", "Существующий раздел сайта"), ("custom", "Новая произвольная страница")],
        required=False,
        initial="fixed",
    )
    title = forms.CharField(label="Название страницы", max_length=220, required=False)
    slug = forms.SlugField(label="URL-адрес", max_length=180, allow_unicode=True, required=False)
    parent = forms.ModelChoiceField(
        label="Родительская страница",
        queryset=PageContent.objects.none(),
        required=False,
        empty_label="Без родительской страницы",
    )
    sort_order = forms.IntegerField(label="Порядок отображения", min_value=0, required=False, initial=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        custom = bool(self.instance.pk and self.instance.is_custom)
        self.fields["page_type"].initial = "custom" if custom else "fixed"
        self.fields["page_type"].disabled = bool(self.instance.pk)
        if self.instance.pk:
            choices = list(PageContent.PAGE_CHOICES)
            self.fields["page"].choices = choices
            self.fields["page"].required = not custom
            if custom:
                self.fields["page"].widget = forms.HiddenInput()
        else:
            used_pages = PageContent.objects.filter(is_custom=False).values_list("page", flat=True)
            self.fields["page"].choices = [
                choice for choice in PageContent.PAGE_CHOICES if choice[0] not in used_pages
            ]
            self.fields["page"].required = False

        excluded = set()
        if self.instance.pk:
            children = {}
            for page_id, parent_id in PageContent.objects.values_list("pk", "parent_id"):
                children.setdefault(parent_id, []).append(page_id)
            stack = [self.instance.pk]
            while stack:
                page_id = stack.pop()
                if page_id not in excluded:
                    excluded.add(page_id)
                    stack.extend(children.get(page_id, []))
        self.fields["parent"].queryset = PageContent.objects.exclude(pk__in=excluded).order_by("sort_order", "page")
        self.fields["parent"].label_from_instance = lambda page: page.title or page.get_page_display()
        if self.instance.pk:
            self.fields["sort_order"].initial = self.instance.sort_order

    def clean(self):
        cleaned_data = super().clean()
        page_type = cleaned_data.get("page_type") or ("custom" if self.instance.pk and self.instance.is_custom else "fixed")
        cleaned_data["page_type"] = page_type
        is_custom = page_type == "custom" or bool(self.instance.pk and self.instance.is_custom)
        if is_custom:
            title = (cleaned_data.get("title") or "").strip()
            slug = cleaned_data.get("slug") or slugify(title, allow_unicode=True)
            if not title:
                self.add_error("title", "Укажите название страницы.")
            if not slug:
                self.add_error("slug", "Укажите URL страницы или заполните название.")
            cleaned_data["title"] = title
            cleaned_data["slug"] = slug
            cleaned_data["is_custom"] = True
            page_key = self.instance.page if self.instance.pk else f"custom-{uuid4().hex}"
            cleaned_data["page"] = page_key
            self.instance.page = page_key
            self.instance.is_custom = True
        elif not cleaned_data.get("page"):
            self.add_error("page", "Выберите раздел сайта.")

        if cleaned_data.get("remove_hero"):
            cleaned_data["hero_image"] = False
            cleaned_data["hero_media"] = None
        elif self.files.get("hero_image"):
            cleaned_data["hero_media"] = None
        elif cleaned_data.get("hero_media"):
            cleaned_data["hero_image"] = False

        parent = cleaned_data.get("parent")
        if self.instance.pk and parent and parent.pk in self.instance.descendant_ids():
            self.add_error("parent", "Нельзя переместить страницу внутрь неё самой или её потомка.")
        return cleaned_data

    def save(self, commit=True):
        page = super().save(commit=False)
        custom = self.cleaned_data.get("page_type") == "custom" or bool(self.instance.pk and self.instance.is_custom)
        page.is_custom = custom
        page.sort_order = self.cleaned_data.get("sort_order") or 0
        page.requires_login = bool(self.cleaned_data.get("requires_login")) if custom else False
        if custom:
            page.title = self.cleaned_data["title"]
            page.slug = self.cleaned_data["slug"]
            page.page = self.cleaned_data["page"]
        else:
            page.title = self.cleaned_data.get("title", "")
            page.slug = None
            page.page = self.cleaned_data["page"]
        if commit:
            if page.pk:
                fields = [*self.Meta.fields, "is_custom", "updated_at"]
                page.save(update_fields=fields)
            else:
                page.save()
            self.save_m2m()
        return page

    @property
    def groups(self):
        sections = [
            ("Страница", ["page_type", "page", "title", "slug", "parent", "sort_order", "h1", "is_visible", "requires_login"]),
            ("Главный блок", ["hero_label", "subtitle", "hero_button_text", "hero_button_url", "hero_image", "hero_image_alt", "hero_media", "mobile_hero_media"]),
            ("Дополнительные тексты", ["content_title", "content_subtitle", "content_text", "b2b_title"]),
            ("Поисковые системы", ["seo_title", "meta_description", "canonical", "noindex"]),
            ("Отправка ссылки в социальных сетях", ["og_title", "og_description", "og_media"]),
        ]
        return [(title, [self[name] for name in names]) for title, names in sections]

    class Meta:
        model = PageContent
        widgets = {"hero_image": forms.FileInput()}
        fields = ["page", "title", "slug", "parent", "sort_order", "requires_login", *SEO_FIELDS, "noindex", "hero_label", "subtitle", "hero_button_text", "hero_button_url", "hero_image", "hero_image_alt", "hero_media", "mobile_hero_media", "content_title", "b2b_title", "content_subtitle", "content_text", "is_visible"]
        labels = {
            "page": "Страница",
            "subtitle": "Текст главного блока",
            "hero_label": "Короткая надпись над заголовком",
            "hero_button_text": "Текст кнопки",
            "seo_title": "SEO-заголовок (title)",
            "meta_description": "Описание для поисковых систем (meta description)",
            "h1": "Основной видимый заголовок (H1)",
            "hero_image": "Изображение главного блока",
            "hero_image_alt": "Alt изображения главного блока",
            "content_title": "Заголовок дополнительного блока",
            "b2b_title": "Заголовок B2B-блока",
            "content_subtitle": "Подзаголовок дополнительного блока",
            "content_text": "Текст дополнительного блока",
            "is_visible": "Использовать эти тексты и изображения на сайте",
        }


class SiteMediaForm(forms.ModelForm):
    def __init__(self, *args, upload_kind="all", **kwargs):
        super().__init__(*args, **kwargs)
        self.upload_kind = upload_kind
        self.fields["file"].widget.attrs.update(upload_policy(upload_kind))

    def clean_file(self):
        from django.db.models.fields.files import FieldFile
        value = self.cleaned_data["file"]
        if not isinstance(value, FieldFile):
            validate_upload(value, self.upload_kind)
        return value

    class Meta:
        model = SiteMedia
        fields = ["title", "file", "alt", "description"]
        widgets = {"file": forms.FileInput()}


class AttributeDefinitionForm(forms.ModelForm):
    filter_type = forms.ChoiceField(
        label="Тип фильтра в каталоге",
        choices=AttributeDefinition.FILTER_TYPE_CHOICES,
        required=False,
        initial=AttributeDefinition.FILTER_SINGLE,
        help_text="Один вариант, несколько вариантов или числовой диапазон. Для поля типа «Список» режим нескольких вариантов также меняет форму товара.",
    )

    choices_text = forms.CharField(
        label="Варианты списка",
        required=False,
        help_text="Например, «Белый» и «Крафт». Каждый вариант с новой строки. Убранный вариант сохраняется у товаров, где он был выбран, и исчезает из фильтра.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Каждый вариант с новой строки"}),
    )

    class Meta:
        model = AttributeDefinition
        fields = [
            "name",
            "value_type",
            "filter_type",
            "unit",
            "sort_order",
            "is_required",
            "default_value",
            "is_visible",
            "show_in_table",
            "is_filterable",
        ]
        labels = {
            "name": "Название поля",
            "value_type": "Тип данных",
            "filter_type": "Тип фильтра в каталоге",
            "unit": "Единица измерения",
            "sort_order": "Порядок отображения",
            "is_required": "Обязательное",
            "default_value": "Значение по умолчанию",
            "is_visible": "Показывать поле",
            "show_in_table": "Колонка в списке товаров",
            "is_filterable": "Использовать в фильтрах",
        }
        help_texts = {
            "name": "Под этим названием поле видно в форме товара и в списке характеристик.",
            "unit": "Например, мм или кг. Единица отображается рядом со значением.",
            "sort_order": "Меньшее число выводит поле раньше. Если числа одинаковые, поля сортируются по названию.",
            "is_required": "Заполнение требуется при сохранении товара. У флажка «Да/Нет» снятая отметка означает «Нет» и считается ответом.",
            "default_value": "Подставляется в форму товара, если значение ещё не сохранено. Для списка укажите один вариант из списка.",
            "is_visible": "Видимое поле доступно для заполнения в карточке товара и может использоваться на витрине. Скрытие сохраняет значения.",
            "show_in_table": "Добавляет колонку в список «Товары» в CMS, пока поле включено.",
            "is_filterable": "Чтобы фильтр появился на витрине, включите поле, добавьте его в настройках категории и заполните значения у товаров.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sort_order"].required = False
        if self.instance.pk and self.instance.choices:
            self.fields["choices_text"].initial = "\n".join(self.instance.choices)

    def clean(self):
        data = super().clean()
        if data.get("sort_order") is None:
            data["sort_order"] = self.instance.sort_order
        if "show_in_table" in self.fields and not (
            self.add_prefix("table_settings") in self.data or self.add_prefix("show_in_table") in self.data
        ):
            data["show_in_table"] = self.instance.show_in_table
        data["filter_type"] = data.get("filter_type") or (
            self.instance.filter_type if self.instance.pk else AttributeDefinition.FILTER_SINGLE
        )
        choices = [
            item.strip()
            for item in data.get("choices_text", "").splitlines()
            if item.strip()
        ]
        if data.get("value_type") == AttributeDefinition.TYPE_CHOICE and not choices:
            self.add_error("choices_text", "Для типа «Список» укажите хотя бы один вариант.")
        if any(len(choice) > 160 for choice in choices):
            self.add_error("choices_text", "Каждый вариант должен содержать не более 160 символов.")
        if "show_in_table" in self.fields:
            self._validate_existing_values(data)
        if data.get("is_filterable") and data.get("filter_type") == AttributeDefinition.FILTER_RANGE:
            if data.get("value_type") not in {
                AttributeDefinition.TYPE_INTEGER,
                AttributeDefinition.TYPE_DECIMAL,
                AttributeDefinition.TYPE_PRICE,
            }:
                self.add_error("filter_type", "Для диапазона выберите числовой тип данных.")
        if data.get("is_filterable") and data.get("filter_type") == AttributeDefinition.FILTER_MULTIPLE:
            if data.get("value_type") != AttributeDefinition.TYPE_CHOICE:
                self.add_error("filter_type", "Несколько вариантов доступны для типа данных «Список».")
        return data

    def _validate_existing_values(self, data):
        name = data.get("name")
        if name and not self.instance.slug:
            slug = slugify(name, allow_unicode=True)
            if not slug or AttributeDefinition.objects.exclude(pk=self.instance.pk).filter(slug=slug).exists():
                self.add_error("name", "Укажите название с буквами или цифрами, которое отличается от названий существующих полей.")
        if not self.instance.pk:
            return
        values = self.instance.product_values
        if data.get("value_type") and data["value_type"] != self.instance.value_type and values.exists():
            self.add_error("value_type", "У поля есть сохранённые значения. Создайте отдельное поле для другого типа данных.")
        if (
            self.instance.value_type == AttributeDefinition.TYPE_CHOICE
            and self.instance.filter_type == AttributeDefinition.FILTER_MULTIPLE
            and data.get("filter_type") != AttributeDefinition.FILTER_MULTIPLE
            and any(len(choices or []) > 1 for choices in values.values_list("value_choices", flat=True).iterator())
        ):
            self.add_error("filter_type", "У товаров выбрано несколько значений. Сократите их до одного в карточках товаров, прежде чем менять режим.")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.choices = list(dict.fromkeys(
            item.strip()
            for item in self.cleaned_data.get("choices_text", "").splitlines()
            if item.strip()
        ))
        if commit:
            instance.save()

        return instance


class CategoryFilterForm(AttributeDefinitionForm):
    class Meta(AttributeDefinitionForm.Meta):
        exclude = ("show_in_table",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved_value_type = self.instance.value_type
        self.fields["name"].label = "Название фильтра"
        self.fields["choices_text"].help_text = "Укажите по одному варианту на строку. На витрине появятся варианты, назначенные товарам."
        self.fields["sort_order"].help_text = "Меньшее число выводит фильтр раньше."

    def clean(self):
        data = super().clean()
        if data.get("sort_order") is None:
            data["sort_order"] = self.instance.sort_order
        if data.get("name") and not self.instance.slug and not slugify(data["name"], allow_unicode=True):
            self.add_error("name", "В названии фильтра должны быть буквы или цифры.")
        value_type = data.get("value_type")
        if self.instance.pk and value_type and value_type != self.saved_value_type:
            if self.instance.product_values.exists() or self.instance.variant_groups.exists():
                self.add_error("value_type", "Этот тип уже используется в товарах или модификациях. Создайте новый фильтр для другого типа данных.")
        return data


class ProductChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, product):
        sku = f" · {product.sku}" if product.sku else ""
        return f"{product.name}{sku}"


class VariantGroupForm(forms.ModelForm):
    attributes = forms.ModelMultipleChoiceField(
        label="Параметры вариантов",
        required=False,
        queryset=AttributeDefinition.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    products = ProductChoiceField(
        label="Товары в группе",
        required=False,
        queryset=Product.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Отметьте существующие товары. Снятые товары будут исключены из группы без удаления.",
    )

    class Meta:
        model = VariantGroup
        fields = ["name"]
        labels = {"name": "Название группы"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attribute_filter = Q(is_visible=True)
        if self.instance.pk:
            attribute_filter |= Q(variant_groups=self.instance)
        self.fields["attributes"].queryset = AttributeDefinition.objects.filter(
            attribute_filter
        ).distinct().order_by("sort_order", "name")
        product_filter = Q(variant_group__isnull=True)
        if self.instance.pk:
            product_filter |= Q(variant_group=self.instance)
        products = Product.objects.filter(product_filter).select_related(
            "category"
        ).order_by("name")
        self.fields["products"].queryset = products
        if self.instance.pk:
            self.fields["attributes"].initial = self.instance.attributes.all()
            self.fields["products"].initial = self.instance.products.all()


class VariantParameterForm(forms.Form):
    name = forms.CharField(label="Название", max_length=120, required=False)
    value_type = forms.ChoiceField(
        label="Тип значения",
        choices=AttributeDefinition.TYPE_CHOICES,
        required=False,
    )
    unit = forms.CharField(label="Единица измерения", max_length=40, required=False)
    choices_text = forms.CharField(
        label="Значения списка",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": "Каждый вариант — с новой строки"}
        ),
    )

    def clean(self):
        data = super().clean()
        name = data.get("name", "").strip()
        if name:
            data["name"] = name
            data["value_type"] = data.get("value_type") or AttributeDefinition.TYPE_TEXT
            existing = AttributeDefinition.objects.filter(name=name).first()
            if existing and not existing.is_visible:
                self.add_error("name", "Поле с таким названием скрыто. Откройте его в разделе «Поля товаров».")
            if not existing:
                slug = slugify(name, allow_unicode=True)
                if not slug or AttributeDefinition.objects.filter(slug=slug).exists():
                    self.add_error("name", "Укажите название с буквами или цифрами, которое отличается от названий существующих полей.")
                choices = [item.strip() for item in data.get("choices_text", "").splitlines() if item.strip()]
                if data["value_type"] == AttributeDefinition.TYPE_CHOICE and not choices:
                    self.add_error("choices_text", "Для списка укажите хотя бы один вариант.")
                if any(len(choice) > 160 for choice in choices):
                    self.add_error("choices_text", "Каждый вариант должен содержать не более 160 символов.")
        elif any(data.get(key) for key in ("unit", "choices_text")):
            raise forms.ValidationError("Укажите название параметра.")
        return data


VariantParameterFormSet = formset_factory(
    VariantParameterForm,
    extra=0,
    can_delete=True,
    max_num=30,
    validate_max=True,
)


class DynamicProductFieldsForm(forms.Form):
    def __init__(self, *args, product=None, definitions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        values = {}
        if product and product.pk:
            values = {value.attribute_id: value for value in product.attributes.all()}
        self.existing_value_ids = values.keys()
        posted = self.data if self.is_bound else None

        def ids(items):
            return {int(item) for item in map(str, items) if item.isascii() and item.isdecimal() and len(item) <= 18}

        def posted_list(key):
            if hasattr(posted, "getlist"):
                return posted.getlist(key)
            value = posted.get(key, [])
            return value if isinstance(value, (tuple, list)) else [value]

        self.removed_definitions = (
            AttributeDefinition.objects.filter(pk__in=ids(posted_list("remove_attribute")))
            if posted is not None else AttributeDefinition.objects.none()
        )
        if definitions is None:
            selected = set(values)
            if product and product.pk:
                selected.update(product.selected_attribute_definitions.values_list("pk", flat=True))
                selected.difference_update(product.excluded_attribute_definitions.values_list("pk", flat=True))
            if posted is not None:
                if "attribute_selection" in posted:
                    selected = ids(posted_list("select_attribute"))
                else:
                    selected.update(ids(key[6:] for key in (*posted, *self.files) if key.startswith("field_")))
            definitions = AttributeDefinition.objects.filter(pk__in=selected)
        self.definitions = definitions.exclude(pk__in=self.removed_definitions).order_by("sort_order", "name")

        for definition in self.definitions:
            field_name = f"field_{definition.pk}"
            stored = values.get(definition.pk)
            initial = self._initial_value(definition, stored)
            field = self._build_field(definition, initial)
            field.product_attribute_order = definition.sort_order
            field.product_attribute_has_saved_value = stored is not None and initial not in ("", None, [])
            if not getattr(field.widget, "allow_multiple_selected", False):
                field.widget.attrs["aria-labelledby"] = f"id_{field_name}_label"
            self.fields[field_name] = field

    def _initial_value(self, definition, value):
        if not value:
            if (
                definition.value_type == AttributeDefinition.TYPE_CHOICE
                and definition.filter_type == AttributeDefinition.FILTER_MULTIPLE
            ):
                return [definition.default_value] if definition.default_value else []
            return definition.default_value

        if definition.value_type == AttributeDefinition.TYPE_INTEGER:
            return value.value_integer
        if definition.value_type in [AttributeDefinition.TYPE_DECIMAL, AttributeDefinition.TYPE_PRICE]:
            return value.value_decimal
        if definition.value_type == AttributeDefinition.TYPE_BOOLEAN:
            return value.value_boolean
        if definition.value_type == AttributeDefinition.TYPE_DATE:
            return value.value_date
        if definition.value_type == AttributeDefinition.TYPE_CHOICE:
            if definition.filter_type == AttributeDefinition.FILTER_MULTIPLE:
                return value.value_choices or ([value.value_choice] if value.value_choice else [])
            return value.display_value()
        if definition.value_type in [AttributeDefinition.TYPE_IMAGE, AttributeDefinition.TYPE_FILE]:
            return value.value_file
        if definition.value_type == AttributeDefinition.TYPE_URL:
            return value.value_url

        return value.value_text

    def _build_field(self, definition, initial):
        kwargs = {
            "label": definition.name,
            "required": definition.is_required,
            "initial": initial,
            "help_text": definition.unit,
        }

        if definition.value_type == AttributeDefinition.TYPE_INTEGER:
            return forms.IntegerField(**kwargs)
        if definition.value_type in [AttributeDefinition.TYPE_DECIMAL, AttributeDefinition.TYPE_PRICE]:
            return forms.DecimalField(**kwargs)
        if definition.value_type == AttributeDefinition.TYPE_BOOLEAN:
            return forms.BooleanField(required=False, label=definition.name, initial=bool(initial))
        if definition.value_type == AttributeDefinition.TYPE_DATE:
            return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **kwargs)
        if definition.value_type == AttributeDefinition.TYPE_CHOICE:
            options = [(choice, choice) for choice in definition.choices]
            initial_choices = initial if isinstance(initial, list) else [initial]
            options.extend(
                (choice, f"{choice} (сохранённое значение)")
                for choice in initial_choices if choice and choice not in definition.choices
            )
            if definition.filter_type == AttributeDefinition.FILTER_MULTIPLE:
                return forms.MultipleChoiceField(
                    choices=options,
                    required=definition.is_required,
                    initial=initial,
                    widget=forms.CheckboxSelectMultiple,
                    label=definition.name,
                    help_text=definition.unit,
                )
            return forms.ChoiceField(choices=[("", "Не выбрано"), *options], **kwargs)
        if definition.value_type == AttributeDefinition.TYPE_IMAGE:
            kwargs["required"] = definition.is_required and not initial
            attrs = upload_policy()
            if initial and getattr(initial, "url", None):
                attrs["data-current-image"] = initial.url
            return forms.FileField(validators=[validate_upload], widget=forms.FileInput(attrs=attrs), **kwargs)
        if definition.value_type == AttributeDefinition.TYPE_FILE:
            kwargs["required"] = definition.is_required and not initial
            return forms.FileField(**kwargs)
        if definition.value_type == AttributeDefinition.TYPE_URL:
            return forms.URLField(**kwargs)

        return forms.CharField(widget=forms.Textarea(attrs={"rows": 1, "data-attribute-text": ""}), **kwargs)

    def save(self, product):
        removed = list(self.removed_definitions.values_list("pk", flat=True))
        if removed:
            product.selected_attribute_definitions.remove(*removed)
            product.excluded_attribute_definitions.add(*removed)
            product.attributes.filter(attribute_id__in=removed).delete()
        selected = [definition.pk for definition in self.definitions]
        if selected:
            product.selected_attribute_definitions.add(*selected)
            product.excluded_attribute_definitions.remove(*selected)
        for definition in self.definitions:
            field_name = f"field_{definition.pk}"
            value = self.cleaned_data.get(field_name)
            if definition.pk in self.existing_value_ids and definition.value_type == AttributeDefinition.TYPE_CHOICE:
                if field_name not in self.changed_data:
                    continue

            if value in ["", None, []] and not definition.is_required:
                ProductAttribute.objects.filter(product=product, attribute=definition).delete()
                continue

            product_attribute, _ = ProductAttribute.objects.get_or_create(product=product, attribute=definition)
            self._assign_value(product_attribute, definition, value)
            product_attribute.save()

    def _assign_value(self, product_attribute, definition, value):
        product_attribute.value_text = ""
        product_attribute.value_integer = None
        product_attribute.value_decimal = None
        product_attribute.value_boolean = None
        product_attribute.value_date = None
        product_attribute.value_choice = ""
        product_attribute.value_choices = []
        product_attribute.value_url = ""

        if definition.value_type == AttributeDefinition.TYPE_INTEGER:
            product_attribute.value_integer = value
        elif definition.value_type in [AttributeDefinition.TYPE_DECIMAL, AttributeDefinition.TYPE_PRICE]:
            product_attribute.value_decimal = value
        elif definition.value_type == AttributeDefinition.TYPE_BOOLEAN:
            product_attribute.value_boolean = value
        elif definition.value_type == AttributeDefinition.TYPE_DATE:
            product_attribute.value_date = value
        elif definition.value_type == AttributeDefinition.TYPE_CHOICE:
            if definition.filter_type == AttributeDefinition.FILTER_MULTIPLE:
                product_attribute.value_choices = list(value or [])
                product_attribute.value_choice = ""
            else:
                product_attribute.value_choice = value
        elif definition.value_type in [AttributeDefinition.TYPE_IMAGE, AttributeDefinition.TYPE_FILE]:
            if value:
                product_attribute.value_file = value
        elif definition.value_type == AttributeDefinition.TYPE_URL:
            product_attribute.value_url = value
        else:
            product_attribute.value_text = value


class SiteLinkForm(ContentValidationMixin, forms.ModelForm):
    class Meta:
        model = SiteLink
        fields = ["location", "label", "url", "sort_order", "is_visible"]


SiteLinkFormSet = forms.inlineformset_factory(SiteSettings, SiteLink, form=SiteLinkForm, extra=1, can_delete=True)


CustomerPriceFormSet = forms.inlineformset_factory(
    Product, CustomerPrice, fields=["user", "price"], extra=1, can_delete=True,
)
