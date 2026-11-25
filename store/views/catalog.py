from urllib.parse import urlencode, urlsplit

from django.template.loader import render_to_string
from django.views.decorators.cache import never_cache

from .common import ADVANTAGES, Category, Employee, JsonResponse, PageContent, Product, Promotion, SiteSettings, apply_common_context, category_filter_context, get_home_stats
from .common import customer_prices, format_price, get_object_or_404, get_store_categories, get_store_products, get_store_products_queryset, product_image_url, product_search, render, require_GET, reverse, safe_site_setting, safe_site_settings, serialize_product
from .common import settings, sort_products
from ..pricing import resolve_product_price
from ..services.accounts import get_favorite_ids
from ..services.cart import get_cart_context
from ..services.catalog import variant_selectors

@require_GET
def api_categories(request):
    return JsonResponse({"categories": get_store_categories()})

def contacts(request):
    context = {
        "categories": get_store_categories(),
        "show_footer_cta": False,
    }
    apply_common_context(request, context)

    return render(
        request,
        "store/contacts.html",
        context,
    )

def document_page(request, slug):
    settings = safe_site_settings()
    get_setting = lambda name, default: getattr(settings, name, default) if settings else default
    site_name = get_setting("site_name", "PakLine")
    company_name = get_setting("company_name", "ООО «ПакЛайн»")
    company_inn = get_setting("company_inn", "7701234567")
    company_kpp = get_setting("company_kpp", "770101001")
    contact_phone = get_setting("contact_phone", "+7 (800) 555-38-22")
    contact_email = get_setting("contact_email", "info@pakline.ru")
    contact_address = get_setting("contact_address", "г. Москва, ул. Складская, д. 14")
    contact_work_hours = get_setting("contact_work_hours", "ПН–ПТ 9:00–18:00")
    documents = {
        "privacy": {
            "title": "Политика конфиденциальности",
            "lead": f"{site_name} обрабатывает персональные данные клиентов для связи, подготовки коммерческих предложений, оформления заказов и работы личного кабинета.",
            "sections": [
                {
                    "title": "Какие данные мы собираем",
                    "items": [
                        "Имя, телефон, email, название компании и текст обращения из форм сайта.",
                        "Данные аккаунта: email, пароль в хэшированном виде, корзина и избранное.",
                        "Технические данные: cookies, IP-адрес, сведения о браузере и действиях на сайте.",
                    ],
                },
                {
                    "title": "Зачем нужны данные",
                    "items": [
                        "Чтобы связаться с клиентом, подготовить коммерческое предложение и оформить заказ.",
                        "Чтобы сохранять корзину, избранное и историю заявок пользователя.",
                        "Чтобы обеспечивать безопасность сайта и улучшать удобство сервиса.",
                    ],
                },
                {
                    "title": "Передача и хранение",
                    "items": [
                        "Данные не продаются третьим лицам.",
                        "Передача возможна только подрядчикам, которые помогают обработать заказ, доставку или поддержку сайта.",
                        f"Запросить уточнение, удаление или изменение данных можно по email {contact_email} или телефону {contact_phone}.",
                    ],
                },
                {
                    "title": "Оператор данных",
                    "items": [
                        f"{company_name}, ИНН {company_inn}, КПП {company_kpp}.",
                        f"Адрес: {contact_address}.",
                        f"Время работы: {contact_work_hours}.",
                    ],
                },
            ],
        },
        "offer": {
            "title": "Оферта",
            "lead": f"{company_name} предлагает картонные коробки для отправлений, переезда, хранения и архива на условиях, согласованных при оформлении заказа.",
            "sections": [
                {
                    "title": "Предмет оферты",
                    "items": [
                        f"{site_name} предлагает картонные коробки для отправлений, переезда, хранения и архива.",
                        "Информация на сайте носит справочный характер и может уточняться менеджером перед оплатой.",
                    ],
                },
                {
                    "title": "Оформление, оплата и доставка",
                    "items": [
                        f"Заказ оформляется через сайт, по телефону {contact_phone}, email {contact_email} или через менеджера.",
                        "Стоимость, наличие, сроки доставки и условия оплаты подтверждаются в счёте или договоре.",
                        f"Самовывоз доступен по адресу: {contact_address}. Доставка выполняется по согласованному адресу.",
                    ],
                },
                {
                    "title": "Возврат и ответственность",
                    "items": [
                        "Возврат и обмен выполняются по действующему законодательству РФ и согласованным условиям поставки.",
                        "Стороны несут ответственность за достоверность предоставленных данных и выполнение согласованных обязательств.",
                        "Реквизиты продавца указаны на странице контактов и в счёте на оплату.",
                    ],
                },
                {
                    "title": "Реквизиты продавца",
                    "items": [
                        f"{company_name}.",
                        f"ИНН {company_inn}, КПП {company_kpp}.",
                        f"Контакты: {contact_phone}, {contact_email}.",
                    ],
                },
            ],
        },
        "cookies": {
            "title": "Управление cookie",
            "lead": f"{site_name} использует cookie для работы сайта, авторизации, корзины, избранного и улучшения сервиса.",
            "sections": [
                {
                    "title": "Как изменить выбор",
                    "items": [
                        "Нажмите «Управление cookie» в подвале сайта.",
                        "Выберите, какие категории cookie разрешить.",
                        "Сохраните настройки — выбор будет запомнен в браузере.",
                    ],
                },
                {
                    "title": "Контакты по вопросам cookie",
                    "items": [
                        f"По вопросам обработки данных можно написать на {contact_email}.",
                        f"Также можно связаться по телефону {contact_phone}.",
                    ],
                },
            ],
        },
    }
    document = documents.get(slug, documents["privacy"])
    context = {
        "document": document,
        "show_footer_cta": False,
    }
    apply_common_context(request, context)

    return render(request, "store/document.html", context)

def home(request):
    settings = safe_site_settings()
    categories = get_store_categories()
    hit_products = [serialize_product(product, request) for product in get_store_products().filter(is_hit=True)[:3]]

    if not hit_products:
        hit_products = [serialize_product(product, request) for product in get_store_products()[:3]]

    context = {
        "categories": categories,
        "hit_products": hit_products,
        "stats": get_home_stats(settings),
        "advantages": ADVANTAGES,
        "show_footer_cta": True,
    }
    apply_common_context(request, context)

    return render(
        request,
        "store/home.html",
        context,
    )

def custom_page(request, slug):
    page = get_object_or_404(PageContent, is_custom=True, slug=slug)
    preview = (
        request.GET.get("preview") == "1"
        and request.user.is_authenticated
        and request.user.is_staff
    )
    if not page.is_visible and not preview:
        from django.http import Http404
        raise Http404
    if page.requires_login and not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect("account_login")

    context = {
        "categories": get_store_categories(),
        "custom_page": page,
        "show_footer_cta": False,
    }
    apply_common_context(request, context)
    context["current_page"] = page
    if preview:
        draft = request.GET.get("preview_builder") == "1"
        context["builder_structure"] = page.draft_structure if draft else page.published_structure
        context["builder_design"] = page.draft_design if draft else page.published_design
    from ..seo import metadata
    context["seo"] = metadata(request, SiteSettings.get_solo(), {"custom_page": page})
    return render(request, "store/custom_page.html", context)

def team(request):
    context = {
        "categories": get_store_categories(),
        "team": Employee.objects.filter(status=Employee.STATUS_PUBLISHED).order_by("sort_order", "name"),
        "show_footer_cta": False,
    }
    apply_common_context(request, context)

    return render(
        request,
        "store/team.html",
        context,
    )

def catalog_back_url(request, category):
    path = reverse("catalog")
    origin = urlsplit(request.build_absolute_uri(path))
    try:
        source = urlsplit(request.headers.get("Referer", ""))
    except ValueError:
        source = None
    if source and (source.scheme, source.netloc, source.path) == (origin.scheme, origin.netloc, path):
        return f"{path}?{source.query}" if source.query else path
    return f"{path}?{urlencode({'category': category.slug})}" if category else path


@never_cache
def catalog(request, slug=None):
    search_query = " ".join(request.GET.get("q", "").split())
    requested_category = request.GET.get("category")
    search_in_category = request.GET.get("scope") == "category"
    requested_category_obj = Category.objects.filter(
        slug=requested_category,
        pk__in=Category.visible_ids(),
    ).first() if requested_category else None
    search_category = requested_category_obj.slug if requested_category_obj else ""
    active_category = search_category if not search_query or search_in_category else None
    only_hits = request.GET.get("hits") == "1" and not search_query
    selected_sort = request.GET.get("sort", "default")
    settings = safe_site_settings()
    products = get_store_products()
    categories = get_store_categories()

    detail_product = None
    detail_is_hidden = False
    if slug:
        preview = request.GET.get("preview") == "1" and request.user.is_authenticated and request.user.is_staff
        if preview:
            detail_product = get_object_or_404(
                Product.objects.select_related("category__parent", "variant_group")
                .prefetch_related("images__media", "media", "attributes__attribute", "variant_group__attributes"),
                slug=slug,
            )
            detail_is_hidden = not products.filter(pk=detail_product.pk).exists()
        else:
            detail_product = get_object_or_404(products, slug=slug)
        request._product_page = detail_product
        request._product_preview = preview
        active_category = detail_product.category.slug
        search_category = active_category

    selected = None
    if active_category:
        selected = Category.objects.filter(slug=active_category, pk__in=Category.visible_ids()).first()
        if not slug:
            products = products.filter(category_id=selected.pk if selected else None)

    if only_hits and not slug:
        products = products.filter(is_hit=True)

    if not slug:
        products = product_search(products, search_query)
        products, catalog_filters = category_filter_context(selected, products, request)
        products = sort_products(products, selected_sort, request)
    else:
        catalog_filters = []

    product_items = [] if slug else [serialize_product(product, request) for product in products]
    query_names = {
        "q", "category", "scope", "hits", "sort", "price_min",
        "price_max", "availability",
        *(filter_item["parameter"] for filter_item in catalog_filters if filter_item.get("parameter")),
        *(filter_item["min_parameter"] for filter_item in catalog_filters if filter_item.get("min_parameter")),
        *(filter_item["max_parameter"] for filter_item in catalog_filters if filter_item.get("max_parameter")),
    }
    query_fields = [
        {"name": name, "value": value}
        for name, values in request.GET.lists()
        if name in query_names or name.startswith("filter_")
        for value in values
    ]
    category_query_parameters = request.GET.copy()
    category_query_parameters.pop("category", None)

    def preserved_fields(excluded):
        return [field for field in query_fields if field["name"] not in excluded]

    attribute_parameters = {
        filter_item["parameter"]
        for filter_item in catalog_filters
        if filter_item.get("parameter")
    }
    attribute_parameters.update(
        parameter
        for filter_item in catalog_filters
        for parameter in (filter_item.get("min_parameter"), filter_item.get("max_parameter"))
        if parameter
    )

    if slug:
        page_title = detail_product.name
    elif search_query:
        page_title = "Результаты поиска"
    elif only_hits:
        page_title = "Хиты продаж"
    elif selected:
        page_title = selected.name
    else:
        page_title = safe_site_setting(settings, "catalog_title")

    category_by_id = {category["id"]: category for category in categories}
    category_nodes = {
        category["id"]: {
            **category,
            "children": [],
            "is_active": bool(selected and category["id"] == str(selected.pk)),
            "is_expanded": False,
        }
        for category in categories
    }
    category_roots = []
    for category in categories:
        node = category_nodes[category["id"]]
        parent_id = category["parent_id"]
        if parent_id and parent_id in category_nodes:
            category_nodes[parent_id]["children"].append(node)
        else:
            category_roots.append(node)

    category_tiles = [
        category
        for category in categories
        if category["parent_id"] == (str(selected.pk) if selected else None)
    ] if not active_category or selected else []
    breadcrumbs = []
    ancestor = selected
    while ancestor:
        category_nodes[str(ancestor.pk)]["is_expanded"] = True
        breadcrumbs.append(category_by_id[str(ancestor.pk)])
        ancestor = ancestor.parent
    breadcrumbs.reverse()

    content_page = PageContent.objects.filter(page="catalog", is_visible=True).first()
    if detail_product:
        page = detail_product.h1 or detail_product.name
    elif search_query:
        page = page_title
    elif selected:
        page = selected.h1 or page_title
    else:
        page = getattr(content_page, "h1", "") or page_title

    recommended_items = []
    accessory_items = []
    detail_data = {}
    detail_gallery_images = []
    if detail_product:
        detail_data = serialize_product(detail_product, request)
        image_alts = {}
        for product_image in detail_product.images.all():
            if not product_image.display_url or (
                product_image.media_id and not product_image.media.is_image
            ):
                continue
            image_alts.setdefault(
                product_image.display_url,
                product_image.alt or getattr(product_image.media, "alt", "") or detail_product.name,
            )
        for media in detail_product.media.all():
            if media.file and media.is_image:
                image_alts.setdefault(media.file.url, media.alt or detail_product.name)
        gallery_urls = detail_data["thumbs"] or [detail_data["image"]]
        detail_gallery_images = [
            {"url": image_url, "alt": image_alts.get(image_url, detail_product.name)}
            for image_url in gallery_urls
        ]
        related_products = get_store_products_queryset().exclude(pk=detail_product.pk)
        recommended_items = list(related_products.filter(recommended_for=detail_product)[:8])
        if not recommended_items:
            recommended_items = list(
                related_products.filter(category=detail_product.category)[:8]
            )
        accessory_items = list(related_products.filter(accessory_for=detail_product)[:8])

    context = {
        "categories": categories,
        "category_tree": category_roots,
        "category_tiles": category_tiles if not slug and not only_hits and not search_query else [],
        "breadcrumbs": breadcrumbs,
        "selected_category": selected,
        "products": product_items,
        "detail_product": detail_product,
        "catalog_back_url": catalog_back_url(request, selected) if detail_product else "",
        "detail_data": detail_data,
        "detail_is_hidden": detail_is_hidden,
        "detail_can_purchase": not detail_is_hidden and detail_data.get("can_purchase", False),
        "detail_gallery_images": detail_gallery_images,
        "detail_variant_selectors": variant_selectors(detail_data.get("variants", [])),
        "detail_specs": detail_data.get("specs", []),
        "recommended_items": [
            serialize_product(item, request) for item in recommended_items
        ],
        "accessory_items": [
            serialize_product(item, request) for item in accessory_items
        ],
        "active_category": active_category,
        "search_category": search_category,
        "only_hits": only_hits,
        "search_query": search_query,
        "search_in_category": search_in_category,
        "selected_sort": selected_sort,
        "catalog_filters": catalog_filters,
        "category_options": categories,
        "category_query_string": category_query_parameters.urlencode(),
        "search_query_fields": preserved_fields({"q", "category", "scope"}),
        "category_query_fields": preserved_fields({"category"}),
        "price_query_fields": preserved_fields({"price_min", "price_max"}),
        "availability_query_fields": preserved_fields({"availability"}),
        "sort_query_fields": preserved_fields({"sort"}),
        "advanced_query_fields": preserved_fields(
            {"price_min", "price_max", "availability", *attribute_parameters}
        ),
        "selected_price_min": catalog_filters[0]["price_min"] if catalog_filters else "",
        "selected_price_max": catalog_filters[0]["price_max"] if catalog_filters else "",
        "selected_availability": catalog_filters[1]["value"] if len(catalog_filters) > 1 else "",
        "availability_options": catalog_filters[1]["options"] if len(catalog_filters) > 1 else [],
        "page_title": page,
        "catalog_subtitle": safe_site_setting(settings, "catalog_subtitle"),
        "open_product_id": request.GET.get("product", ""),
    }
    reset_parameters = {}
    if search_category:
        reset_parameters["category"] = search_category
    if search_query:
        reset_parameters["q"] = search_query
    if search_in_category:
        reset_parameters["scope"] = "category"
    if only_hits:
        reset_parameters["hits"] = "1"
    if selected_sort != "default":
        reset_parameters["sort"] = selected_sort
    context["filter_reset_url"] = reverse("catalog")
    if reset_parameters:
        context["filter_reset_url"] += "?" + urlencode(reset_parameters)
    active_filter_tags = []
    for filter_item in catalog_filters:
        filter_kind = filter_item.get("kind")
        tag_values = []
        if filter_kind == "price":
            price_parts = []
            if filter_item["price_min"]:
                price_parts.append(f"от {filter_item['price_min']} ₽")
            if filter_item["price_max"]:
                price_parts.append(f"до {filter_item['price_max']} ₽")
            if price_parts:
                tag_values.append(("price", " · ".join(price_parts)))
        elif filter_kind == "availability":
            if filter_item["value"]:
                label = dict(Product.AVAILABILITY_CHOICES).get(filter_item["value"], filter_item["value"])
                tag_values.append(("availability", label))
        elif filter_kind == "range":
            range_parts = []
            if filter_item["min_value"]:
                range_parts.append(f"от {filter_item['min_value']}")
            if filter_item["max_value"]:
                range_parts.append(f"до {filter_item['max_value']}")
            if range_parts:
                tag_values.append(("range", filter_item["name"], " · ".join(range_parts)))
        else:
            tag_values.extend(
                (filter_item["parameter"], option["value"], f"{filter_item['name']}: {option['label']}")
                for option in filter_item["values"]
                if option["selected"]
            )
        for item in tag_values:
            parameters = request.GET.copy()
            if filter_kind == "price":
                parameters.pop("price_min", None)
                parameters.pop("price_max", None)
                label = item[1]
            elif filter_kind == "availability":
                parameters.pop("availability", None)
                label = item[1]
            elif filter_kind == "range":
                parameters.pop(filter_item["min_parameter"], None)
                parameters.pop(filter_item["max_parameter"], None)
                _, name, value = item
                label = f"{name}: {value}"
            else:
                parameter, value, label = item
                remaining = [existing for existing in parameters.getlist(parameter) if existing != value]
                if remaining:
                    parameters.setlist(parameter, remaining)
                else:
                    parameters.pop(parameter, None)
            suffix = parameters.urlencode()
            active_filter_tags.append({
                "label": label,
                "url": reverse("catalog") + (f"?{suffix}" if suffix else ""),
            })
    context["active_filter_tags"] = active_filter_tags
    context["active_filter_count"] = len(active_filter_tags)
    apply_common_context(request, context)
    if detail_product:
        context["detail_cart_quantity"] = context["cart_quantities"].get(detail_data["id"], 0)

    response = render(request, "store/catalog.html", context)
    if slug and preview:
        response["X-Robots-Tag"] = "noindex"
    return response

@require_GET
@never_cache
def api_products(request):
    products = get_store_products()
    category = request.GET.get("category")
    hits = request.GET.get("hits")
    query = (request.GET.get("q") or "").strip()
    selected_sort = request.GET.get("sort", "default")

    selected = None
    if category and (not query or request.GET.get("scope") == "category"):
        selected = Category.objects.filter(slug=category, pk__in=Category.visible_ids()).first()
        products = products.filter(category_id=selected.pk if selected else None)

    if hits == "1" and not query:
        products = products.filter(is_hit=True)

    products = product_search(products, query)
    products, _ = category_filter_context(selected, products, request)
    products = sort_products(products, selected_sort, request)

    from ..seo import metadata
    config = SiteSettings.get_solo()
    pages = {page.page: page for page in PageContent.objects.filter(is_visible=True)}
    items = [serialize_product(product, request) for product in products]
    payload = {"seo": metadata(request, config, pages)}
    if request.GET.get("cards") == "1":
        payload["count"] = len(items)
        payload["cards_html"] = render_to_string("store/partials/catalog_cards.html", {
            "products": items,
            "cart_quantities": get_cart_context(request)["cart_quantities"],
            "favorite_ids": get_favorite_ids(request),
            "search_query": query,
        })
    else:
        payload["products"] = items
    return JsonResponse(payload)

@require_GET
def api_product_suggestions(request):
    query = " ".join(request.GET.get("q", "").split())
    if len(query) < 2:
        return JsonResponse({"suggestions": []})
    products = product_search(get_store_products(), query).order_by("name")[:8]
    return JsonResponse({
        "suggestions": [
            {
                "id": str(product.pk),
                "name": product.name,
                "sku": product.sku or "",
                "price": format_price(
                    resolve_product_price(
                        product,
                        request.user if request.user.is_authenticated else None,
                        customer_prices(request),
                    )
                ),
                "image": product_image_url(product),
                "url": reverse("product_detail", args=[product.slug]),
            }
            for product in products
        ]
    })

@require_GET
def api_product_detail(request, product_id):
    product = get_object_or_404(get_store_products(), pk=product_id)
    return JsonResponse({"product": serialize_product(product, request)})

@require_GET
def promotions(request):
    context = {
        "categories": get_store_categories(),
        "promotions": Promotion.visible().prefetch_related("media"),
        "show_footer_cta": True,
    }
    apply_common_context(request, context)
    return render(request, "store/promotions.html", context)
