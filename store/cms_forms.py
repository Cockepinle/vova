from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import AttributeDefinition, Category, Employee, PageContent, Product, ProductAttribute, SiteSettings


class ManagementLoginForm(AuthenticationForm):
    username = forms.CharField(label="Логин", widget=forms.TextInput(attrs={"placeholder": "Введите логин"}))
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"placeholder": "Введите пароль"}))


class ProductForm(forms.ModelForm):
    sku = forms.CharField(label="Артикул", required=False)

    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "sku",
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


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "image", "image_url", "description", "is_active"]
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


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "home_hero_label",
            "home_hero_title",
            "home_hero_subtitle",
            "catalog_title",
            "catalog_subtitle",
            "team_hero_label",
            "team_hero_title",
            "team_hero_subtitle",
            "contacts_hero_label",
            "contacts_hero_title",
            "contacts_form_title",
            "contacts_b2b_title",
            "contacts_b2b_subtitle",
            "contacts_b2b_text",
            "stat_1_value",
            "stat_1_label",
            "stat_2_value",
            "stat_2_label",
            "stat_3_value",
            "stat_3_label",
            "stat_4_value",
            "stat_4_label",
            "contact_phone",
            "contact_email",
            "contact_email_b2b",
            "contact_address",
            "contact_work_hours",
            "company_name",
            "company_inn",
            "company_kpp",
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


class PageContentForm(forms.ModelForm):
    class Meta:
        model = PageContent
        fields = ["page", "title", "subtitle", "hero_label", "hero_button_text", "is_visible"]
        labels = {
            "page": "Страница",
            "title": "Заголовок",
            "subtitle": "Подзаголовок / текст",
            "hero_label": "Метка",
            "hero_button_text": "Текст кнопки",
            "is_visible": "Показывать",
        }


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
