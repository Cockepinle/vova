from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import AttributeDefinition, Category, Employee, PageContent, Product, ProductAttribute, SiteMedia, SiteSettings, SiteLink



SEO_FIELDS = ["seo_title", "meta_description", "h1", "canonical", "og_title", "og_description", "og_media"]


def validate_content_link(value):
    from urllib.parse import urlsplit
    if not value:
        return
    parsed = urlsplit(value)
    if "\\" in value or any(ord(char) < 32 for char in value) or value.startswith("//"):
        raise forms.ValidationError("Укажите адрес страницы от / или полную ссылку https://.")
    if not (value.startswith("/") or value.startswith("#") or (parsed.scheme in {"http", "https"} and parsed.netloc) or (parsed.scheme in {"mailto", "tel"} and parsed.path)):
        raise forms.ValidationError("Допустимы ссылки /catalog/, https://example.ru, mailto: и tel:.")


class ContentValidationMixin:
    def clean(self):
        data = super().clean()
        for name, value in list(data.items()):
            if (name.endswith("_url") or name == "url") and isinstance(value, str) and value:
                try:
                    validate_content_link(value)
                except forms.ValidationError as error:
                    self.add_error(name, error)
            if name.endswith("_media") and value:
                from pathlib import PurePosixPath
                if PurePosixPath(value.file.name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"}:
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
    username = forms.CharField(label="Логин", widget=forms.TextInput(attrs={"placeholder": "Введите логин"}))
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"placeholder": "Введите пароль"}))


class ProductForm(ContentValidationMixin, forms.ModelForm):
    sku = forms.CharField(label="Артикул", required=False)

    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "sku",
            "slug",
            *SEO_FIELDS,
            "description",
            "price",
            "old_price",
            "unit",
            "min_quantity",
            "stock_quantity",
            "image",
            "image_url",
            "is_hit",
            "is_new",
            "availability",
            "status",
        ]
        labels = {
            "category": "Категория",
            "name": "Название",
            "sku": "Артикул",
            "description": "Описание",
            "price": "Цена",
            "old_price": "Старая цена",
            "unit": "Единица измерения",
            "min_quantity": "Минимальное количество",
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


class CategoryForm(ContentValidationMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug", "image", "image_url", "description", "is_active", *SEO_FIELDS]
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


class EmployeeForm(forms.ModelForm):
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
            ("Компания и бренд", ["site_name", "company_name", "company_inn", "company_kpp", "logo_text", "logo_image", "logo_alt", "logo_media", "favicon_media"]),
            ("Общие контакты", ["contact_phone", "contact_email", "contact_email_b2b", "contact_address", "contact_work_hours"]),
            ("Шапка и основная кнопка", ["header_phone", "header_email", "show_header_contacts", "show_header_account", "show_header_favorites", "show_header_cta", "cta_label", "cta_url"]),
            ("Подвал и юридическая информация", [name for name in self.fields if name.startswith("footer_")] + ["copyright_text"]),
            ("Поиск и отправка ссылок", ["public_url", "seo_description", "og_media", "allow_indexing"]),
        ]
        return [(title, [self[name] for name in names]) for title, names in sections]

    class Meta:
        model = SiteSettings
        fields = [
            "site_name", "logo_text", "logo_media", "favicon_media", "public_url", "seo_description", "og_media", "allow_indexing",
            "cta_label", "cta_url", "show_header_contacts", "show_header_account", "show_header_favorites", "show_header_cta", "footer_extra_text", "footer_legal_text",
            "contact_phone",
            "contact_email",
            "contact_email_b2b",
            "contact_address",
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
    @property
    def groups(self):
        sections = [
            ("Страница", ["page", "h1", "is_visible"]),
            ("Главный блок", ["hero_label", "subtitle", "hero_button_text", "hero_button_url", "hero_image", "hero_image_alt", "hero_media", "mobile_hero_media"]),
            ("Дополнительные тексты", ["content_title", "content_subtitle", "content_text", "b2b_title"]),
            ("Поисковые системы", ["seo_title", "meta_description", "canonical", "noindex"]),
            ("Отправка ссылки в социальных сетях", ["og_title", "og_description", "og_media"]),
        ]
        return [(title, [self[name] for name in names]) for title, names in sections]

    class Meta:
        model = PageContent
        fields = ["page", *SEO_FIELDS, "noindex", "hero_label", "subtitle", "hero_button_text", "hero_button_url", "hero_image", "hero_image_alt", "hero_media", "mobile_hero_media", "content_title", "b2b_title", "content_subtitle", "content_text", "is_visible"]
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
    def clean_file(self):
        from pathlib import PurePosixPath
        from PIL import Image
        value = self.cleaned_data["file"]
        if value.size > 20 * 1024 * 1024:
            raise forms.ValidationError("Размер файла не должен превышать 20 МБ.")
        extension = PurePosixPath(value.name).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico", ".pdf", ".mp4", ".webm"}:
            raise forms.ValidationError("Загрузите JPG, PNG, WebP, GIF, ICO, PDF, MP4 или WebM.")
        if extension in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".ico"}:
            try:
                Image.open(value).verify()
            except Exception:
                raise forms.ValidationError("Файл не является корректным изображением.")
            finally:
                value.seek(0)
        return value

    class Meta:
        model = SiteMedia
        fields = ["title", "file", "alt"]
        widgets = {"file": forms.FileInput(attrs={"accept": "image/*,video/*,application/pdf"})}


class AttributeDefinitionForm(forms.ModelForm):
    choices_text = forms.CharField(
        label="Варианты списка",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Каждый вариант с новой строки"}),
    )

    class Meta:
        model = AttributeDefinition
        fields = [
            "name",
            "value_type",
            "unit",
            "is_required",
            "default_value",
            "is_visible",
            "is_filterable",
        ]
        labels = {
            "name": "Название поля",
            "value_type": "Тип данных",
            "unit": "Единица измерения",
            "is_required": "Обязательное",
            "default_value": "Значение по умолчанию",
            "is_visible": "Видимое",
            "is_filterable": "Использовать в фильтрах",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.choices:
            self.fields["choices_text"].initial = "\n".join(self.instance.choices)

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.choices = [item.strip() for item in self.cleaned_data.get("choices_text", "").splitlines() if item.strip()]
        instance.show_in_table = True

        if commit:
            instance.save()

        return instance


class DynamicProductFieldsForm(forms.Form):
    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.product = product
        self.definitions = AttributeDefinition.objects.filter(is_visible=True).order_by("sort_order", "name")
        values = {}

        if product and product.pk:
            values = {value.attribute_id: value for value in product.attributes.select_related("attribute")}

        for definition in self.definitions:
            field_name = f"field_{definition.pk}"
            initial = self._initial_value(definition, values.get(definition.pk))
            field = self._build_field(definition, initial)
            self.fields[field_name] = field

    def _initial_value(self, definition, value):
        if not value:
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
            return value.value_choice
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
            choices = [("", "Не выбрано")] + [(choice, choice) for choice in definition.choices]
            return forms.ChoiceField(choices=choices, **kwargs)
        if definition.value_type == AttributeDefinition.TYPE_IMAGE:
            kwargs["required"] = definition.is_required and not initial
            return forms.FileField(**kwargs)
        if definition.value_type == AttributeDefinition.TYPE_FILE:
            kwargs["required"] = definition.is_required and not initial
            return forms.FileField(**kwargs)
        if definition.value_type == AttributeDefinition.TYPE_URL:
            return forms.URLField(**kwargs)

        return forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **kwargs)

    def save(self, product):
        for definition in self.definitions:
            field_name = f"field_{definition.pk}"
            value = self.cleaned_data.get(field_name)

            if value in ["", None] and not definition.is_required:
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
