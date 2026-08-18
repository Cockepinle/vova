import json
import random
import smtplib

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .data import ADVANTAGES
from .models import CartItem, Category, CustomerProfile, CustomerRequest, EmailVerificationCode, Employee, FavoriteItem, Order, OrderItem, Product, SiteSettings


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


def safe_site_setting(settings, name):
    return getattr(settings, name, DEFAULT_SITE_SETTINGS[name]) if settings else DEFAULT_SITE_SETTINGS[name]


def safe_site_settings():
    try:
        return SiteSettings.get_solo()
    except Exception:
        return None


def get_product(product_id):
    try:
        product = (
            Product.objects.select_related("category")
            .prefetch_related("images", "attributes__attribute")
            .get(pk=product_id, status=Product.STATUS_PUBLISHED, category__is_active=True)
        )
        return product
    except (Product.DoesNotExist, ValueError, TypeError):
        return None


def get_store_categories_queryset():
    categories = Category.objects.filter(is_active=True).order_by("sort_order", "name")

    if categories.exists():
        return categories

    return Category.objects.order_by("sort_order", "name")


def get_store_products_queryset():
    return (
        Product.objects.filter(status=Product.STATUS_PUBLISHED, category__is_active=True)
        .select_related("category")
        .prefetch_related("images", "attributes__attribute")
        .order_by("name")
    )


def get_store_categories():
    return [serialize_category(category) for category in get_store_categories_queryset()]


def get_store_products():
    return get_store_products_queryset()


def format_price(value):
    if value == value.to_integral_value():
        return int(value)

    return float(value)


def image_url(image):
    return image.url if image else ""


def serialize_category(category):
    return {
        "id": str(category.id),
        "name": category.name,
        "slug": category.slug,
        "image": category.display_image_url,
        "description": category.description,
    }


def product_badge(product):
    if product.is_hit:
        return "ХИТ"
    if product.is_new:
        return "НОВИНКА"

    return ""


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

    for value in product.attributes.all():
        if not value.attribute.is_visible:
            continue

        display_value = value.display_value()
        if display_value in ["", None]:
            continue

        unit = f" {value.attribute.unit}" if value.attribute.unit else ""
        specs.append((value.attribute.name, f"{display_value}{unit}"))

    return specs


def serialize_product(product):
    main_image = product.display_image_url
    thumbs = [main_image] if main_image else []
    thumbs.extend(item.display_url for item in product.images.all() if item.display_url)

    return {
        "id": str(product.id),
        "sku": product.sku or "",
        "category": product.category.name,
        "category_slug": product.category.slug,
        "badge": product_badge(product),
        "name": product.name,
        "description": product.description,
        "price": format_price(product.price),
        "unit": product.unit,
        "min_quantity": product.min_quantity,
        "image": main_image,
        "thumbs": thumbs,
        "specs": product_specs(product),
    }


def serialize_order_item(item):
    return {
        "product_id": str(item.product_id),
        "name": item.product_name,
        "sku": item.product_sku,
        "unit": item.unit,
        "quantity": item.quantity,
        "price": format_price(item.price),
        "line_total": format_price(item.line_total),
    }


def serialize_order(order, include_items=False):
    data = {
        "id": str(order.id),
        "number": order.number,
        "status": order.status,
        "status_label": order.get_status_display(),
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "total": format_price(order.total),
        "customer": {
            "full_name": order.full_name,
            "phone": order.phone,
            "email": order.email,
            "company": order.company,
            "user_id": str(order.user_id),
            "user_email": order.user.email or order.user.username,
        },
        "comment": order.comment,
    }

    if include_items:
        data["items"] = [serialize_order_item(item) for item in order.items.all()]

    return data


def serialize_cart_item(product, quantity):
    product_data = serialize_product(product)

    return {
        "id": product_data["id"],
        "name": product_data["name"],
        "sku": product_data["sku"],
        "price": product_data["price"],
        "unit": product_data["unit"],
        "min_quantity": product_data["min_quantity"],
        "image": product_data["image"],
        "product": product_data,
        "quantity": quantity,
        "line_total": product_data["price"] * quantity,
    }


def normalize_quantity(product, quantity):
    minimum = max(1, int(getattr(product, "min_quantity", 1) or 1))

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = minimum

    return max(minimum, quantity)


def get_session_cart(request):
    return request.session.get("cart", {})


def save_session_cart(request, cart):
    request.session["cart"] = {str(product_id): int(quantity) for product_id, quantity in cart.items() if int(quantity) > 0}
    request.session.modified = True


def merge_session_cart_to_user(request, user):
    session_cart = get_session_cart(request)

    if not session_cart:
        return

    for product_id, quantity in session_cart.items():
        product = get_product(product_id)

        if not product:
            continue

        item, _ = CartItem.objects.get_or_create(user=user, product=product, defaults={"quantity": 0})
        item.quantity += normalize_quantity(product, quantity)
        item.save(update_fields=["quantity", "updated_at"])

    request.session["cart"] = {}
    request.session.modified = True


def get_cart_items(request):
    items = []

    if request.user.is_authenticated:
        cart_items = (
            CartItem.objects.filter(user=request.user)
            .select_related("product__category")
            .prefetch_related("product__images", "product__attributes__attribute")
        )

        for item in cart_items:
            items.append(serialize_cart_item(item.product, item.quantity))

        return items

    for product_id, quantity in get_session_cart(request).items():
        product = get_product(product_id)

        if product:
            items.append(serialize_cart_item(product, int(quantity)))

    return items


def get_cart_context(request):
    cart_items = get_cart_items(request)
    cart_quantities = {item["id"]: item["quantity"] for item in cart_items}

    return {
        "cart_items": cart_items,
        "cart_quantities": cart_quantities,
        "cart_count": sum(item["quantity"] for item in cart_items),
        "cart_total": sum(item["line_total"] for item in cart_items),
        "checkout_initial": get_checkout_initial(request),
    }


def get_checkout_initial(request):
    if not request.user.is_authenticated:
        return {"full_name": "", "phone": "", "email": "", "company": ""}

    profile = getattr(request.user, "customer_profile", None)

    return {
        "full_name": request.user.get_full_name(),
        "phone": profile.phone if profile else "",
        "email": request.user.email,
        "company": profile.company if profile else "",
    }


def cart_payload(request):
    cart_context = get_cart_context(request)

    return {
        "items": cart_context["cart_items"],
        "count": cart_context["cart_count"],
        "total": cart_context["cart_total"],
    }


def clear_user_cart(user):
    CartItem.objects.filter(user=user).delete()


def clear_cart_storage(request):
    if request.user.is_authenticated:
        clear_user_cart(request.user)
    else:
        request.session["cart"] = {}
        request.session.modified = True


def auth_required_payload():
    return JsonResponse({"auth_required": True, "error": "Войдите или зарегистрируйтесь, чтобы продолжить"}, status=403)


def notify_manager(subject, message):
    if not settings.MANAGER_EMAIL:
        return

    send_mail(
        subject,
        message,
        None,
        [settings.MANAGER_EMAIL],
        fail_silently=True,
    )


def send_account_code(email, subject, text):
    code = f"{random.randint(100000, 999999)}"
    EmailVerificationCode.objects.filter(email=email, is_used=False).update(is_used=True)

    try:
        send_mail(subject, text.format(code=code), None, [email], fail_silently=False)
    except (smtplib.SMTPException, OSError, TimeoutError):
        if settings.DEBUG:
            return code, f"Почта сейчас не отправилась, но код создан. Код для локальной проверки: {code}"

        return None, "Не удалось отправить код на почту. Проверьте SMTP-настройки и попробуйте ещё раз."

    return code, "Мы отправили код подтверждения на email."


def get_favorite_ids(request):
    if not request.user.is_authenticated:
        return []

    return [str(product_id) for product_id in FavoriteItem.objects.filter(user=request.user).values_list("product_id", flat=True)]


def get_favorites_context(request):
    favorite_ids = get_favorite_ids(request)
    favorite_products = [serialize_product(product) for product in get_store_products().filter(id__in=favorite_ids)]

    return {
        "favorite_ids": favorite_ids,
        "favorite_products": favorite_products,
        "favorite_count": len(favorite_ids),
        "account_user": request.user if request.user.is_authenticated else None,
    }


def apply_common_context(request, context):
    context.update(get_cart_context(request))
    context.update(get_favorites_context(request))

    return context


def get_home_stats(settings):
    return [
        {"value": safe_site_setting(settings, "stat_1_value"), "label": safe_site_setting(settings, "stat_1_label")},
        {"value": safe_site_setting(settings, "stat_2_value"), "label": safe_site_setting(settings, "stat_2_label")},
        {"value": safe_site_setting(settings, "stat_3_value"), "label": safe_site_setting(settings, "stat_3_label")},
        {"value": safe_site_setting(settings, "stat_4_value"), "label": safe_site_setting(settings, "stat_4_label")},
    ]


def home(request):
    settings = safe_site_settings()
    categories = get_store_categories()
    hit_products = [serialize_product(product) for product in get_store_products().filter(is_hit=True)[:3]]

    if not hit_products:
        hit_products = [serialize_product(product) for product in get_store_products()[:3]]

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


def catalog(request):
    active_category = request.GET.get("category")
    only_hits = request.GET.get("hits") == "1"
    search_query = request.GET.get("q", "").strip()
    settings = safe_site_settings()
    products = get_store_products()
    categories = get_store_categories()

    if active_category:
        products = products.filter(category__slug=active_category)

    if only_hits:
        products = products.filter(is_hit=True)

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(sku__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    product_items = [serialize_product(product) for product in products]

    if only_hits:
        page_title = "Хиты продаж"
    elif active_category:
        page_title = next((category["name"] for category in categories if category["slug"] == active_category), "Категория")
    else:
        page_title = safe_site_setting(settings, "catalog_title")

    context = {
        "categories": categories,
        "products": product_items,
        "active_category": active_category,
        "only_hits": only_hits,
        "search_query": search_query,
        "page_title": page_title,
        "catalog_subtitle": safe_site_setting(settings, "catalog_subtitle"),
        "open_product_id": request.GET.get("product", ""),
    }
    apply_common_context(request, context)

    return render(
        request,
        "store/catalog.html",
        context,
    )


@require_GET
def api_categories(request):
    return JsonResponse({"categories": get_store_categories()})


@require_GET
def api_products(request):
    products = get_store_products()
    category = request.GET.get("category")
    hits = request.GET.get("hits")
    query = (request.GET.get("q") or "").strip()

    if category:
        products = products.filter(category__slug=category)

    if hits == "1":
        products = products.filter(is_hit=True)

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )

    return JsonResponse({"products": [serialize_product(product) for product in products]})


@require_GET
def api_cart(request):
    return JsonResponse(cart_payload(request))


@staff_member_required(login_url="management_login")
@require_GET
def api_management_orders(request):
    orders = Order.objects.select_related("user").order_by("-created_at")
    status = request.GET.get("status")

    if status:
        orders = orders.filter(status=status)

    return JsonResponse({"orders": [serialize_order(order) for order in orders[:100]]})


@staff_member_required(login_url="management_login")
@require_GET
def api_management_order_detail(request, order_id):
    order = Order.objects.select_related("user").prefetch_related("items").get(pk=order_id)
    return JsonResponse({"order": serialize_order(order, include_items=True)})


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
            "lead": f"{company_name} предлагает упаковочные материалы, товары для склада и сопутствующие позиции на условиях, согласованных при оформлении заказа.",
            "sections": [
                {
                    "title": "Предмет оферты",
                    "items": [
                        f"{site_name} поставляет гофрокартон, стрейч-плёнку, скотч, пузырчатую плёнку и другие упаковочные материалы.",
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


@csrf_exempt
@require_POST
def add_to_cart(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    product_id = str(payload.get("product_id") or "")
    quantity = int(payload.get("quantity") or 1)
    product = get_product(product_id)

    if not product:
        return JsonResponse({"error": "Товар не найден"}, status=404)

    quantity = normalize_quantity(product, quantity)

    if request.user.is_authenticated:
        item, _ = CartItem.objects.get_or_create(user=request.user, product=product, defaults={"quantity": 0})
        item.quantity = item.quantity + quantity
        item.save(update_fields=["quantity", "updated_at"])
    else:
        cart = get_session_cart(request)
        cart[product_id] = int(cart.get(product_id, 0)) + quantity
        save_session_cart(request, cart)

    return JsonResponse(cart_payload(request))


@csrf_exempt
@require_POST
def update_cart(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    product_id = str(payload.get("product_id") or "")
    quantity = int(payload.get("quantity") or 0)
    product = get_product(product_id)

    if quantity > 0 and not product:
        return JsonResponse({"error": "Товар не найден"}, status=404)

    if product and quantity > 0:
        quantity = normalize_quantity(product, quantity)

    if request.user.is_authenticated:
        if quantity <= 0:
            CartItem.objects.filter(user=request.user, product_id=product_id).delete()
        else:
            CartItem.objects.update_or_create(user=request.user, product=product, defaults={"quantity": quantity})
    else:
        cart = get_session_cart(request)

        if quantity <= 0:
            cart.pop(product_id, None)
        else:
            cart[product_id] = quantity

        save_session_cart(request, cart)

    return JsonResponse(cart_payload(request))


@csrf_exempt
@require_POST
def clear_cart(request):
    clear_cart_storage(request)
    return JsonResponse(cart_payload(request))


@csrf_exempt
@require_POST
def checkout_order(request):
    if not request.user.is_authenticated:
        return auth_required_payload()

    cart_items = get_cart_items(request)

    if not cart_items:
        return JsonResponse({"error": "Корзина пуста"}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    full_name = (payload.get("full_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    company = (payload.get("company") or "").strip()
    comment = (payload.get("comment") or "").strip()

    if not full_name or not phone or not email:
        return JsonResponse({"error": "Заполните ФИО, телефон и email"}, status=400)

    order = Order.objects.create(
        user=request.user,
        full_name=full_name,
        phone=phone,
        email=email,
        company=company,
        comment=comment,
        total=sum(item["line_total"] for item in cart_items),
    )

    for item in cart_items:
        product = get_product(item["id"])

        if not product:
            continue

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=item["name"],
            product_sku=item["sku"],
            unit=item["unit"],
            quantity=item["quantity"],
            price=item["price"],
            line_total=item["line_total"],
        )

    order_lines = "\n".join(
        f"- {item['name']} × {item['quantity']} {item['unit']} (мин. {item['product']['min_quantity']} {item['unit']}) — {item['line_total']} ₽"
        for item in cart_items
    )
    notify_manager(
        f"Новый заказ {order.number}",
        "\n".join(
            [
                f"Номер заказа: {order.number}",
                f"Клиент: {full_name}",
                f"Телефон: {phone}",
                f"Email: {email}",
                f"Компания: {company or 'не указана'}",
                f"Итого: {order.total} ₽",
                "",
                "Состав заказа:",
                order_lines,
                "",
                f"Комментарий: {comment or 'не указан'}",
            ]
        ),
    )
    clear_cart_storage(request)

    return JsonResponse(
        {
            "ok": True,
            "message": f"Заказ {order.number} принят. Менеджер свяжется с вами.",
            "order_number": order.number,
            "cart": cart_payload(request),
        }
    )


@csrf_exempt
@require_POST
def toggle_favorite(request):
    if not request.user.is_authenticated:
        return auth_required_payload()

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    product_id = str(payload.get("product_id") or "")
    product = get_product(product_id)

    if not product:
        return JsonResponse({"error": "Товар не найден"}, status=404)

    favorite, created = FavoriteItem.objects.get_or_create(user=request.user, product=product)

    if created:
        is_favorite = True
    else:
        favorite.delete()
        is_favorite = False

    favorites = get_favorite_ids(request)

    return JsonResponse(
        {
            "ids": favorites,
            "count": len(favorites),
            "items": [serialize_product(product) for product in get_store_products().filter(id__in=favorites)],
            "is_favorite": is_favorite,
            "product_id": product_id,
        }
    )


@csrf_exempt
@require_POST
def account_login(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    user = authenticate(request, username=email, password=password)

    if not user:
        return JsonResponse({"error": "Неверный email или пароль"}, status=400)

    login(request, user)
    CustomerProfile.objects.get_or_create(user=user)
    merge_session_cart_to_user(request, user)

    return JsonResponse({"ok": True, "user": {"name": user.get_full_name() or user.username, "email": user.email}})


@csrf_exempt
@require_POST
def account_register(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    name = (payload.get("name") or "").strip()
    company = (payload.get("company") or "").strip()
    phone = (payload.get("phone") or "").strip()

    if not email or not password:
        return JsonResponse({"error": "Email и пароль обязательны"}, status=400)
    if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Пользователь с таким email уже существует"}, status=400)

    code, message = send_account_code(email, "Код подтверждения PakLine", "Ваш код подтверждения: {code}")

    if not code:
        return JsonResponse({"error": message}, status=503)

    EmailVerificationCode.objects.create(
        email=email,
        code=code,
        payload={
            "email": email,
            "password": password,
            "name": name,
            "company": company,
            "phone": phone,
        },
    )

    return JsonResponse({"ok": True, "verification_required": True, "message": message})


@csrf_exempt
@require_POST
def account_verify(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    email = (payload.get("email") or "").strip().lower()
    code = (payload.get("code") or "").strip()
    verification = EmailVerificationCode.objects.filter(email=email, code=code, is_used=False).first()

    if not verification:
        return JsonResponse({"error": "Неверный код подтверждения"}, status=400)

    data = verification.payload
    if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
        verification.is_used = True
        verification.save(update_fields=["is_used"])
        return JsonResponse({"error": "Пользователь с таким email уже существует"}, status=400)

    user = User.objects.create_user(username=email, email=email, password=data.get("password", ""))
    name = data.get("name", "")
    if name:
        parts = name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        user.save(update_fields=["first_name", "last_name"])

    CustomerProfile.objects.create(user=user, company=data.get("company", ""), phone=data.get("phone", ""))
    verification.is_used = True
    verification.save(update_fields=["is_used"])
    login(request, user)
    merge_session_cart_to_user(request, user)

    return JsonResponse({"ok": True, "user": {"name": user.get_full_name() or user.username, "email": user.email}})


@csrf_exempt
@require_POST
def account_password_reset_request(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    email = (payload.get("email") or "").strip().lower()

    if not email:
        return JsonResponse({"error": "Введите email"}, status=400)

    user = User.objects.filter(email=email).first() or User.objects.filter(username=email).first()

    if not user:
        return JsonResponse({"error": "Пользователь с таким email не найден"}, status=404)

    code, message = send_account_code(email, "Восстановление пароля PakLine", "Код для восстановления пароля: {code}")

    if not code:
        return JsonResponse({"error": message}, status=503)

    EmailVerificationCode.objects.create(email=email, code=code, payload={"type": "password_reset"})

    return JsonResponse({"ok": True, "verification_required": True, "message": message})


@csrf_exempt
@require_POST
def account_password_reset_confirm(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    email = (payload.get("email") or "").strip().lower()
    code = (payload.get("code") or "").strip()
    password = payload.get("password") or ""

    if not email or not code or not password:
        return JsonResponse({"error": "Введите email, код и новый пароль"}, status=400)

    verification = EmailVerificationCode.objects.filter(
        email=email,
        code=code,
        is_used=False,
        payload__type="password_reset",
    ).first()

    if not verification:
        return JsonResponse({"error": "Неверный код восстановления"}, status=400)

    user = User.objects.filter(email=email).first() or User.objects.filter(username=email).first()

    if not user:
        return JsonResponse({"error": "Пользователь не найден"}, status=404)

    user.set_password(password)
    user.save(update_fields=["password"])
    verification.is_used = True
    verification.save(update_fields=["is_used"])
    login(request, user)
    merge_session_cart_to_user(request, user)

    return JsonResponse({"ok": True, "message": "Пароль изменён. Вы вошли в аккаунт."})


@csrf_exempt
@require_POST
def account_logout(request):
    logout(request)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def create_customer_request(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    text = (payload.get("text") or "").strip()

    if not name or not email or not text:
        return JsonResponse({"error": "Заполните имя, email и описание заявки"}, status=400)

    customer_request = CustomerRequest.objects.create(
        user=request.user if request.user.is_authenticated else None,
        name=name,
        company=(payload.get("company") or "").strip(),
        email=email,
        phone=(payload.get("phone") or "").strip(),
        text=text,
    )
    notify_manager(
        "Новый запрос на КП",
        "\n".join(
            [
                f"Дата заявки: {customer_request.created_at:%d.%m.%Y %H:%M}",
                f"Клиент: {customer_request.name}",
                f"Телефон: {customer_request.phone or 'не указан'}",
                f"Email: {customer_request.email}",
                f"Компания: {customer_request.company or 'не указана'}",
                "",
                "Текст запроса:",
                customer_request.text,
            ]
        ),
    )

    return JsonResponse({"ok": True, "message": "Запрос на КП сохранён. Мы свяжемся с вами."})
