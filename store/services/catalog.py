from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from ..models import AttributeDefinition, Category, Product, ProductAttribute, SiteSettings
from ..pricing import individual_price_map, resolve_product_price

DEFAULT_SITE_SETTINGS = {
    "catalog_title": "Все товары",
    "catalog_subtitle": "Каталог упаковочных материалов",
    "stat_1_value": "300+",
    "stat_1_label": "SKU на складе",
    "stat_2_value": "12 лет",
    "stat_2_label": "на рынке",
    "stat_3_value": "2400+",
    "stat_3_label": "клиентов",
    "stat_4_value": "День в день",
    "stat_4_label": "отгрузка",
}

def serialize_category(category):
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "image": category.display_image_url,
        "description": category.description,
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "depth": getattr(category, "tree_depth", 0),
        "path": getattr(category, "tree_label", category.name),
    }

def product_badge(product):
    return " · ".join(product_badges(product))

def attribute_lookup(attribute, value):
    field = {
        AttributeDefinition.TYPE_INTEGER: "attributes__value_integer",
        AttributeDefinition.TYPE_DECIMAL: "attributes__value_decimal",
        AttributeDefinition.TYPE_PRICE: "attributes__value_decimal",
        AttributeDefinition.TYPE_BOOLEAN: "attributes__value_boolean",
        AttributeDefinition.TYPE_DATE: "attributes__value_date",
        AttributeDefinition.TYPE_CHOICE: "attributes__value_choice",
        AttributeDefinition.TYPE_URL: "attributes__value_url",
    }.get(attribute.value_type, "attributes__value_text")
    if attribute.value_type == AttributeDefinition.TYPE_BOOLEAN:
        value = value == "1"
    return {"attributes__attribute": attribute, field: value}

def get_store_products():
    return get_store_products_queryset()

def get_store_categories_queryset():
    return Category.objects.filter(pk__in=Category.visible_ids()).order_by("sort_order", "name")

def product_specs(product):
    specs = []

    if product.sku:
        specs.append(("Артикул", product.sku))

    specs.extend(
        [
            ("Категория", product.category.name),
            ("Наличие", product.get_availability_display()),
            ("На складе", f"{product.stock_quantity} {product.unit}"),
            ("Минимальный заказ", f"{product.min_quantity} {product.unit}"),
        ]
    )

    specs.append(("НДС", f"{product.vat_rate}%"))
    for label, field in [("Длина, мм", "length_mm"), ("Ширина, мм", "width_mm"), ("Высота, мм", "height_mm"), ("Вес, кг", "weight_kg"), ("Объём, м³", "volume_m3")]:
        value = getattr(product, field)
        if value is not None:
            specs.append((label, decimal_value(value)))

    for value in product.attributes.all():
        if not value.attribute.is_visible:
            continue

        display_value = value.display_value()
        if display_value in ["", None]:
            continue

        unit = f" {value.attribute.unit}" if value.attribute.unit else ""
        specs.append((value.attribute.name, f"{display_value}{unit}"))

    return specs

def get_product(product_id):
    try:
        product = get_store_products_queryset().get(pk=product_id)
        return product
    except (Product.DoesNotExist, ValueError, TypeError):
        return None

def category_filter_context(category, products, request):
    filters = []
    category_products = products
    if category:
        attributes = category.filter_attributes.filter(
            is_filterable=True,
            is_visible=True,
        ).order_by("sort_order", "name")[:5]
    else:
        attributes = []
    for attribute in attributes:
        parameter = f"filter_{attribute.pk}"
        if attribute.filter_type == AttributeDefinition.FILTER_RANGE:
            min_parameter = f"{parameter}_min"
            max_parameter = f"{parameter}_max"
            min_value = request.GET.get(min_parameter, "").strip()
            max_value = request.GET.get(max_parameter, "").strip()
            lookup_field = (
                "value_integer"
                if attribute.value_type == AttributeDefinition.TYPE_INTEGER
                else "value_decimal"
            )
            has_values = ProductAttribute.objects.filter(
                product__in=category_products,
                attribute=attribute,
            ).exclude(**{f"{lookup_field}__isnull": True}).exists()
            if not has_values:
                continue
            min_number = max_number = None
            for raw, bound in ((min_value, "gte"), (max_value, "lte")):
                if not raw:
                    continue
                try:
                    number = Decimal(raw)
                    if not number.is_finite():
                        raise InvalidOperation
                except (InvalidOperation, ValueError):
                    if bound == "gte":
                        min_value = ""
                    else:
                        max_value = ""
                    continue
                if bound == "gte":
                    min_number = number
                else:
                    max_number = number
            if min_value and max_value:
                if min_number is not None and max_number is not None and min_number > max_number:
                    min_value = max_value = ""
                    min_number = max_number = None
            if min_number is not None:
                products = products.filter(**{
                    "attributes__attribute": attribute,
                    f"attributes__{lookup_field}__gte": min_number,
                })
            if max_number is not None:
                products = products.filter(**{
                    "attributes__attribute": attribute,
                    f"attributes__{lookup_field}__lte": max_number,
                })
            filters.append({
                "name": attribute.name,
                "kind": "range",
                "filter_type": attribute.filter_type,
                "value_type": attribute.value_type,
                "parameter": parameter,
                "min_parameter": min_parameter,
                "max_parameter": max_parameter,
                "min_value": min_value,
                "max_value": max_value,
            })
            continue

        selected = request.GET.getlist(parameter)
        values = []
        seen = set()
        rows = ProductAttribute.objects.filter(
            product__in=products,
            attribute=attribute,
        ).select_related("attribute")
        option_rows = ProductAttribute.objects.filter(
            product__in=category_products,
            attribute=attribute,
        ).select_related("attribute")
        for row in option_rows:
            if attribute.filter_type == AttributeDefinition.FILTER_MULTIPLE:
                raw_values = row.value_choices or ([row.value_choice] if row.value_choice else [])
                row_values = [(value, value) for value in raw_values]
            else:
                display = row.display_value()
                raw_value = (
                    "1" if row.value_boolean else "0"
                ) if attribute.value_type == AttributeDefinition.TYPE_BOOLEAN else str(display)
                row_values = [] if display in (None, "") else [(raw_value, display)]
            for raw, display in row_values:
                raw = str(raw)
                if raw not in seen:
                    seen.add(raw)
                    values.append({
                        "value": raw,
                        "label": f"{display}{(' ' + attribute.unit) if attribute.unit else ''}",
                        "selected": raw in selected,
                    })
        if selected:
            valid_selected = [value for value in selected if value in seen]
            if attribute.filter_type == AttributeDefinition.FILTER_MULTIPLE:
                matching_ids = [
                    row.product_id
                    for row in rows
                    if set(valid_selected).intersection(
                        str(value) for value in (
                            row.value_choices or ([row.value_choice] if row.value_choice else [])
                        )
                    )
                ]
                products = products.filter(pk__in=matching_ids)
            elif valid_selected:
                choice_query = Q()
                for value in valid_selected:
                    choice_query |= Q(**attribute_lookup(attribute, value))
                products = products.filter(choice_query)
        if values:
            filters.append({
                "name": attribute.name,
                "filter_type": attribute.filter_type,
                "parameter": parameter,
                "values": values,
            })

    price_min = request.GET.get("price_min", "").strip()
    price_max = request.GET.get("price_max", "").strip()
    availability = request.GET.get("availability", "").strip()
    if availability in dict(Product.AVAILABILITY_CHOICES):
        products = products.filter(availability=availability)
    else:
        availability = ""

    min_price = None
    max_price = None
    try:
        min_price = Decimal(price_min) if price_min else None
        if min_price is not None and (not min_price.is_finite() or min_price < 0):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        price_min = ""
        min_price = None
    try:
        max_price = Decimal(price_max) if price_max else None
        if max_price is not None and (not max_price.is_finite() or max_price < 0):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        price_max = ""
        max_price = None

    user = getattr(request, "user", None)
    if min_price is not None or max_price is not None:
        individual_prices = individual_price_map(user) if user and user.is_authenticated else None
        products = [
            product for product in products
            if (min_price is None or resolve_product_price(product, user, individual_prices) >= min_price)
            and (max_price is None or resolve_product_price(product, user, individual_prices) <= max_price)
        ]

    filters.insert(0, {
        "name": "Цена, ₽",
        "kind": "price",
        "price_min": price_min,
        "price_max": price_max,
    })
    filters.insert(1, {
        "name": "Наличие",
        "kind": "availability",
        "value": availability,
        "options": [
            {"value": value, "label": label}
            for value, label in Product.AVAILABILITY_CHOICES
        ],
    })
    if hasattr(products, "distinct"):
        products = products.distinct()
    return products, filters

def get_home_stats(settings):
    return [
        {"value": safe_site_setting(settings, "stat_1_value"), "label": safe_site_setting(settings, "stat_1_label")},
        {"value": safe_site_setting(settings, "stat_2_value"), "label": safe_site_setting(settings, "stat_2_label")},
        {"value": safe_site_setting(settings, "stat_3_value"), "label": safe_site_setting(settings, "stat_3_label")},
        {"value": safe_site_setting(settings, "stat_4_value"), "label": safe_site_setting(settings, "stat_4_label")},
    ]

def get_store_categories():
    return [serialize_category(category) for category in Category.tree_rows(visible_only=True)]

def get_store_products_queryset():
    return (
        Product.objects.filter(status=Product.STATUS_PUBLISHED, category_id__in=Category.visible_ids())
        .select_related("category", "variant_group")
        .prefetch_related("images__media", "media", "attributes__attribute", "variant_group__attributes")
        .order_by("name")
    )

def product_variants(product):
    if not product.variant_group_id:
        return []
    parameters = list(product.variant_group.attributes.all())
    variants = get_store_products_queryset().filter(variant_group_id=product.variant_group_id)
    result = []
    for variant in variants:
        values = {value.attribute_id: value for value in variant.attributes.all()}
        labels = []
        for parameter in parameters:
            value = values.get(parameter.pk)
            display = value.display_value() if value else None
            if display not in (None, ""):
                suffix = f" {parameter.unit}" if parameter.unit else ""
                labels.append(f"{parameter.name}: {display}{suffix}")
        result.append({
            "id": str(variant.pk),
            "name": variant.name,
            "label": " · ".join(labels) or variant.name,
            "url": reverse("product_detail", args=[variant.slug]),
            "data_url": reverse("api_product_detail", args=[variant.pk]),
            "current": variant.pk == product.pk,
            "availability": variant.availability,
            "availability_label": variant.get_availability_display(),
            "unavailable": variant.availability == Product.AVAILABILITY_OUT_OF_STOCK,
        })
    return result

def safe_site_settings():
    try:
        return SiteSettings.get_solo()
    except Exception:
        return None

def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def safe_site_setting(settings, name):
    return getattr(settings, name, DEFAULT_SITE_SETTINGS[name]) if settings else DEFAULT_SITE_SETTINGS[name]

def product_badges(product):
    return [label for enabled, label in [(product.is_hit, "ХИТ"), (product.is_new, "НОВИНКА"), (product.is_special, "СПЕЦПРЕДЛОЖЕНИЕ")] if enabled]

def customer_prices(request):
    if request is None or not request.user.is_authenticated:
        return {}
    if not hasattr(request, "_customer_prices"):
        request._customer_prices = individual_price_map(request.user)
    return request._customer_prices

def decimal_value(value):
    return format(value, "f") if value is not None else None

def image_url(image):
    return image.url if image else ""

def product_image_url(product):
    image = product.display_image_url
    if image:
        return image
    for product_image in product.images.all():
        if product_image.display_url and (
            not product_image.media_id or product_image.media.is_image
        ):
            return product_image.display_url
    for media in product.media.all():
        if media.file and media.is_image:
            return media.file.url
    return static("store/images/no-photo.svg")

def product_search(products, query):
    query = " ".join((query or "").split())
    if not query:
        return products
    database_matches = products.filter(
        Q(name__icontains=query)
        | Q(sku__icontains=query)
        | Q(description__icontains=query)
        | Q(keywords__icontains=query)
        | Q(category__name__icontains=query)
    ).values_list("pk", flat=True)
    # SQLite's case-insensitive LIKE is ASCII-only; casefold keeps Cyrillic
    # search behaviour identical in local development and PostgreSQL.
    matches = Q(pk__in=database_matches)
    if connection.vendor == "sqlite":
        needle = query.casefold()
        unicode_matches = []
        rows = products.values(
            "pk", "name", "sku", "description", "keywords", "category__name",
        )
        for product in rows.iterator(chunk_size=1000):
            haystack = " ".join([
                product["name"],
                product["sku"] or "",
                product["description"],
                product["keywords"],
                product["category__name"],
            ]).casefold()
            if needle in haystack:
                unicode_matches.append(product["pk"])
        matches |= Q(pk__in=unicode_matches)
    return products.filter(matches).distinct()

def serialize_product(product, request=None):
    main_image = product_image_url(product)
    thumbs = [main_image] if main_image else []
    product_links = list(product.images.all())
    thumbs.extend(item.display_url for item in product_links if item.display_url and (not item.media_id or item.media.is_image))
    thumbs = list(dict.fromkeys(thumbs))
    media = list(product.media.all())
    media.extend(item.media for item in product_links if item.media_id and not item.media.is_image)
    media = list({item.pk: item for item in media}.values())
    thumbs.extend(item.file.url for item in media if item.file and item.is_image)
    main_image = main_image or (thumbs[0] if thumbs else static("store/images/no-photo.svg"))

    return {
        "id": str(product.id),
        "url": reverse("product_detail", args=[product.slug]),
        "created_at": product.created_at.isoformat(),
        "sku": product.sku or "",
        "category": product.category.name,
        "category_slug": product.category.slug,
        "badge": product_badge(product),
        "badges": product_badges(product),
        "is_new": product.is_new,
        "is_special": product.is_special,
        "stock_quantity": product.stock_quantity,
        "availability": product.availability,
        "availability_label": product.get_availability_display(),
        "can_purchase": product.availability != Product.AVAILABILITY_OUT_OF_STOCK,
        "category_id": str(product.category_id),
        "category_parent_id": str(product.category.parent_id) if product.category.parent_id else None,
        "vat_rate": decimal_value(product.vat_rate),
        "length_mm": decimal_value(product.length_mm),
        "width_mm": decimal_value(product.width_mm),
        "height_mm": decimal_value(product.height_mm),
        "weight_kg": decimal_value(product.weight_kg),
        "volume_m3": decimal_value(product.volume_m3),
        "media": [{"id": str(item.pk), "title": item.title, "url": item.file.url, "is_video": item.is_video} for item in media if item.file and not item.is_image],
        "name": product.name,
        "description": product.description,
        "price": format_price(resolve_product_price(product, request.user if request else None, customer_prices(request))),
        "unit": product.unit,
        "min_quantity": product.min_quantity,
        "image": main_image,
        "thumbs": thumbs,
        "specs": product_specs(product),
        "variants": product_variants(product),
    }

def format_price(value):
    value = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return format(value, "f")

def sort_products(products, sort, request=None):
    user = getattr(request, "user", None)
    if sort in {"price_asc", "price_desc"}:
        individual_prices = individual_price_map(user) if user and user.is_authenticated else None
        reverse_order = sort == "price_desc"
        return sorted(
            products,
            key=lambda product: (
                resolve_product_price(product, user, individual_prices) * (-1 if reverse_order else 1),
                product.name.casefold(),
            ),
        )

    if not hasattr(products, "order_by"):
        if sort == "name_desc":
            return sorted(products, key=lambda product: product.name.casefold(), reverse=True)
        if sort == "newest":
            return sorted(products, key=lambda product: (-product.created_at.timestamp(), product.name.casefold()))
        return sorted(products, key=lambda product: product.name.casefold())

    ordering = {
        "price_asc": ("price", "name"),
        "price_desc": ("-price", "name"),
        "name": ("name",),
        "name_desc": ("-name",),
        "newest": ("-created_at", "name"),
        "default": ("name",),
    }
    return products.order_by(*ordering.get(sort, ordering["default"]))
