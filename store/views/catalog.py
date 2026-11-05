from urllib.parse import urlencode

from .common import ADVANTAGES, Category, Employee, JsonResponse, PageContent, Product, Promotion, SiteSettings, apply_common_context, category_filter_context, get_home_stats
from .common import customer_prices, format_price, get_object_or_404, get_store_categories, get_store_products, product_image_url, product_search, product_specs, product_variants, render, require_GET, reverse, safe_site_setting, safe_site_settings, serialize_product
from .common import settings, sort_products
from ..pricing import resolve_product_price

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
    if slug:
        detail_product = get_object_or_404(products, slug=slug)
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

    if slug:
        products = products.filter(pk=detail_product.pk)

    product_items = [serialize_product(product, request) for product in products]
    query_names = {
        "q", "category", "scope", "hits", "sort", "price_min",
        "price_max", "availability",
        *(filter_item["parameter"] for filter_item in catalog_filters if filter_item.get("parameter")),
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
    category_options = [
        {
            **category,
            "indent": "— " * category["depth"],
        }
        for category in categories
    ]

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

    context = {
        "categories": categories,
        "category_tree": category_roots,
        "category_tiles": category_tiles if not slug and not only_hits and not search_query else [],
        "breadcrumbs": breadcrumbs,
        "selected_category": selected,
        "products": product_items,
        "detail_product": detail_product,
        "detail_variants": product_variants(detail_product) if detail_product else [],
        "detail_specs": product_specs(detail_product) if detail_product else [],
        "active_category": active_category,
        "search_category": search_category,
        "only_hits": only_hits,
        "search_query": search_query,
        "search_in_category": search_in_category,
        "selected_sort": selected_sort,
        "catalog_filters": catalog_filters,
        "category_options": category_options,
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

    return render(
        request,
        "store/catalog.html",
        context,
    )

@require_GET
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
    return JsonResponse({"products": [serialize_product(product, request) for product in products], "seo": metadata(request, config, pages)})

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
