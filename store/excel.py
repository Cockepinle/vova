"""Round-trip XLSX import and export for the existing product catalogue."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.db import transaction
from django.utils.text import slugify
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .models import AttributeDefinition, Category, Product, ProductAttribute


BASE_COLUMNS = [
    "Артикул", "Название", "Категория", "Подкатегория", "Описание", "Ключевые слова",
    "Цена", "Себестоимость", "Коэф. розницы", "Коэф. опта", "Коэф. спеццены", "Старая цена", "Остаток", "Единица", "Минимальное количество",
    "НДС", "Длина, мм", "Ширина, мм", "Высота, мм", "Вес, кг", "Статус", "Наличие",
    "Хит", "Новинка", "Спецпредложение", "Slug", "H1", "SEO Title", "SEO Description",
    "Главное изображение URL", "Фильтры категории",
]
REQUIRED_COLUMNS = {"Артикул", "Название", "Категория", "Цена"}
ATTRIBUTE_PREFIX = "Характеристика: "


def text(value):
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value).strip()


def decimal_value(value, field, allow_empty=True):
    value = text(value).replace(" ", "").replace(",", ".")
    if not value and allow_empty:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}: ожидается число")


def integer_value(value, field, default=0):
    value = text(value)
    if not value:
        return default
    try:
        result = int(Decimal(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{field}: ожидается целое число")
    if result < 0:
        raise ValueError(f"{field}: значение не может быть отрицательным")
    return result


def boolean_value(value):
    return text(value).casefold() in {"1", "да", "true", "yes", "on", "+"}


def category_parts(category):
    result, seen = [], set()
    while category and category.pk not in seen:
        seen.add(category.pk)
        result.append(category.name)
        category = category.parent
    result.reverse()
    return result


def resolve_category(category_name, subcategory_name):
    parts = [part.strip() for part in text(category_name).split("/") if part.strip()]
    parts.extend(part.strip() for part in text(subcategory_name).split("/") if part.strip())
    if not parts:
        raise ValueError("Категория: значение обязательно")
    parent = None
    for part in parts:
        matches = Category.objects.filter(name__iexact=part, parent=parent)
        if matches.count() != 1:
            raise ValueError(f"Категория не найдена однозначно: {' / '.join(parts)}")
        parent = matches.first()
    return parent


def attribute_raw_value(row):
    attribute = row.attribute
    value_type = attribute.value_type
    if value_type == AttributeDefinition.TYPE_INTEGER:
        return row.value_integer
    if value_type in {AttributeDefinition.TYPE_DECIMAL, AttributeDefinition.TYPE_PRICE}:
        return row.value_decimal
    if value_type == AttributeDefinition.TYPE_BOOLEAN:
        return "Да" if row.value_boolean else "Нет"
    if value_type == AttributeDefinition.TYPE_DATE:
        return row.value_date
    if value_type == AttributeDefinition.TYPE_CHOICE:
        return row.value_choice
    if value_type == AttributeDefinition.TYPE_URL:
        return row.value_url
    return row.value_text


def assign_attribute(product, attribute, raw_value):
    value = text(raw_value)
    if not value:
        ProductAttribute.objects.filter(product=product, attribute=attribute).delete()
        return
    item, _ = ProductAttribute.objects.get_or_create(product=product, attribute=attribute)
    item.value_text = ""
    item.value_integer = None
    item.value_decimal = None
    item.value_boolean = None
    item.value_date = None
    item.value_choice = ""
    item.value_url = ""
    if attribute.value_type == AttributeDefinition.TYPE_INTEGER:
        item.value_integer = integer_value(value, attribute.name)
    elif attribute.value_type in {AttributeDefinition.TYPE_DECIMAL, AttributeDefinition.TYPE_PRICE}:
        item.value_decimal = decimal_value(value, attribute.name, allow_empty=False)
    elif attribute.value_type == AttributeDefinition.TYPE_BOOLEAN:
        item.value_boolean = boolean_value(value)
    elif attribute.value_type == AttributeDefinition.TYPE_DATE:
        try:
            item.value_date = date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{attribute.name}: используйте дату ГГГГ-ММ-ДД")
    elif attribute.value_type == AttributeDefinition.TYPE_CHOICE:
        if attribute.choices and value not in attribute.choices:
            raise ValueError(f"{attribute.name}: допустимо {', '.join(attribute.choices)}")
        item.value_choice = value
    elif attribute.value_type == AttributeDefinition.TYPE_URL:
        item.value_url = value
    else:
        item.value_text = value
    item.save()


def export_products():
    attributes = list(AttributeDefinition.objects.order_by("sort_order", "name"))
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Товары"
    headers = BASE_COLUMNS + [ATTRIBUTE_PREFIX + attribute.name for attribute in attributes]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1238F4")
    products = Product.objects.select_related("category", "category__parent").prefetch_related("attributes__attribute", "category__filter_attributes").order_by("name")
    for product in products:
        parts = category_parts(product.category)
        values = {item.attribute_id: attribute_raw_value(item) for item in product.attributes.all()}
        row = [
            product.sku or "", product.name, parts[0] if parts else "", " / ".join(parts[1:]), product.description, product.keywords,
            product.price, product.cost_price, product.retail_coefficient, product.wholesale_coefficient, product.special_coefficient, product.old_price, product.stock_quantity, product.unit, product.min_quantity,
            product.vat_rate, product.length_mm, product.width_mm, product.height_mm, product.weight_kg,
            product.status, product.availability, "Да" if product.is_hit else "Нет", "Да" if product.is_new else "Нет",
            "Да" if product.is_special else "Нет", product.slug, product.h1, product.seo_title, product.meta_description,
            product.display_image_url, ", ".join(product.category.filter_attributes.values_list("name", flat=True)),
        ]
        row.extend(values.get(attribute.pk, "") for attribute in attributes)
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        letter = column[0].column_letter
        sheet.column_dimensions[letter].width = min(45, max(12, max(len(text(cell.value)) for cell in column) + 2))
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def import_products(file_object):
    try:
        workbook = load_workbook(file_object, read_only=True, data_only=True)
    except Exception as error:
        raise ValueError(f"Не удалось открыть XLSX: {error}")
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        raw_headers = next(rows)
    except StopIteration:
        raise ValueError("Файл пустой")
    headers = [text(value) for value in raw_headers]
    missing = sorted(REQUIRED_COLUMNS - set(headers))
    if missing:
        raise ValueError("Отсутствуют обязательные колонки: " + ", ".join(missing))
    if len(headers) != len(set(headers)):
        raise ValueError("Названия колонок не должны повторяться")
    attribute_columns = {index: header[len(ATTRIBUTE_PREFIX):].strip() for index, header in enumerate(headers) if header.startswith(ATTRIBUTE_PREFIX)}
    result = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
    status_values = {label.casefold(): code for code, label in Product.STATUS_CHOICES} | {code: code for code, _ in Product.STATUS_CHOICES}
    availability_values = {label.casefold(): code for code, label in Product.AVAILABILITY_CHOICES} | {code: code for code, _ in Product.AVAILABILITY_CHOICES}
    for row_number, raw_row in enumerate(rows, start=2):
        values = dict(zip(headers, raw_row))
        if not any(text(value) for value in raw_row):
            result["skipped"] += 1
            continue
        sku = text(values.get("Артикул"))
        if not sku:
            result["skipped"] += 1
            result["errors"].append(f"Строка {row_number}: артикул обязателен")
            continue
        try:
            with transaction.atomic():
                product = Product.objects.filter(sku=sku).first()
                created = product is None
                if created:
                    product = Product(sku=sku)
                name = text(values.get("Название"))
                if not name:
                    raise ValueError("Название обязательно")
                category = resolve_category(values.get("Категория"), values.get("Подкатегория"))
                price = decimal_value(values.get("Цена"), "Цена", allow_empty=False)
                product.name = name
                product.category = category
                product.description = text(values.get("Описание"))
                product.keywords = text(values.get("Ключевые слова"))
                product.price = price
                product.cost_price = decimal_value(values.get("Себестоимость"), "Себестоимость")
                product.retail_coefficient = decimal_value(values.get("Коэф. розницы"), "Коэф. розницы")
                product.wholesale_coefficient = decimal_value(values.get("Коэф. опта"), "Коэф. опта")
                product.special_coefficient = decimal_value(values.get("Коэф. спеццены"), "Коэф. спеццены")
                product.old_price = decimal_value(values.get("Старая цена"), "Старая цена")
                product.stock_quantity = integer_value(values.get("Остаток"), "Остаток")
                product.unit = text(values.get("Единица")) or "шт"
                product.min_quantity = max(1, integer_value(values.get("Минимальное количество"), "Минимальное количество", 1))
                product.vat_rate = decimal_value(values.get("НДС"), "НДС") if text(values.get("НДС")) else Decimal("22")
                product.length_mm = decimal_value(values.get("Длина, мм"), "Длина, мм")
                product.width_mm = decimal_value(values.get("Ширина, мм"), "Ширина, мм")
                product.height_mm = decimal_value(values.get("Высота, мм"), "Высота, мм")
                product.weight_kg = decimal_value(values.get("Вес, кг"), "Вес, кг")
                status = text(values.get("Статус")).casefold() or Product.STATUS_DRAFT
                availability = text(values.get("Наличие")).casefold() or Product.AVAILABILITY_IN_STOCK
                if status not in status_values:
                    raise ValueError("Неизвестный статус товара")
                if availability not in availability_values:
                    raise ValueError("Неизвестное значение наличия")
                product.status = status_values[status]
                product.availability = availability_values[availability]
                product.is_hit = boolean_value(values.get("Хит"))
                product.is_new = boolean_value(values.get("Новинка"))
                product.is_special = boolean_value(values.get("Спецпредложение"))
                supplied_slug = text(values.get("Slug"))
                if supplied_slug:
                    product.slug = supplied_slug
                elif created:
                    product.slug = slugify(name, allow_unicode=True)
                product.h1 = text(values.get("H1"))
                product.seo_title = text(values.get("SEO Title"))
                product.meta_description = text(values.get("SEO Description"))
                product.image_url = text(values.get("Главное изображение URL"))
                product.full_clean(exclude=["media"])
                product.save()
                for index, attribute_name in attribute_columns.items():
                    if not attribute_name:
                        continue
                    attribute, _ = AttributeDefinition.objects.get_or_create(name=attribute_name, defaults={"value_type": AttributeDefinition.TYPE_TEXT})
                    assign_attribute(product, attribute, raw_row[index] if index < len(raw_row) else None)
                filter_names = [name.strip() for name in text(values.get("Фильтры категории")).split(",") if name.strip()]
                if filter_names:
                    filters = []
                    for filter_name in filter_names[:5]:
                        attribute = AttributeDefinition.objects.filter(name__iexact=filter_name).first()
                        if not attribute:
                            raise ValueError(f"Фильтр не найден среди характеристик: {filter_name}")
                        filters.append(attribute)
                    category.filter_attributes.set(filters)
                result["created" if created else "updated"] += 1
        except Exception as error:
            result["skipped"] += 1
            result["errors"].append(f"Строка {row_number}, артикул {sku}: {error}")
    return result
