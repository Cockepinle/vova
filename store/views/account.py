from .common import CartItem, CustomerProfile, CustomerRequest, EmailVerificationCode, FavoriteItem, JsonResponse, Order, User, auth_required_payload, authenticate
from .common import cart_payload, csrf_exempt, get_favorite_ids, get_object_or_404, get_product, get_store_products, get_store_products_queryset, json, login, logout
from .common import merge_session_cart_to_user, normalize_quantity, notify_manager_safely, require_GET, require_POST, send_account_code, serialize_order, serialize_product, staff_member_required, transaction

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
    notify_manager_safely(
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
@transaction.atomic
def repeat_order(request, order_id):
    if not request.user.is_authenticated:
        return auth_required_payload()
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=order_id, user=request.user)
    available = {
        product.pk: product for product in get_store_products_queryset().filter(
            pk__in=[item.product_id for item in order.items.all()]
        )
    }
    skipped = []
    added = 0
    for item in order.items.all():
        product = available.get(item.product_id)
        if not product:
            skipped.append(item.product_name)
            continue
        cart_item, _created = CartItem.objects.select_for_update().get_or_create(
            user=request.user, product=product, defaults={"quantity": 0}
        )
        cart_item.quantity = normalize_quantity(product, cart_item.quantity + item.quantity)
        cart_item.save(update_fields=["quantity", "updated_at"])
        added += 1
    if not added:
        return JsonResponse({"error": "В заказе нет доступных для покупки товаров.", "skipped": skipped}, status=409)
    message = "Товары добавлены в текущую корзину по актуальным ценам."
    if skipped:
        message += " Недоступны: " + ", ".join(skipped) + "."
    return JsonResponse({"ok": True, "message": message, "skipped": skipped, "cart": cart_payload(request)})

@staff_member_required(login_url="management_login")
@require_GET
def api_management_order_detail(request, order_id):
    order = Order.objects.select_related("user", "payment_method").prefetch_related("items").get(pk=order_id)
    return JsonResponse({"order": serialize_order(order, include_items=True)})

@require_GET
def account_order_detail(request, order_id):
    if not request.user.is_authenticated:
        return auth_required_payload()
    order = get_object_or_404(
        Order.objects.select_related("payment_method", "delivery_method").prefetch_related("items", "payments", "status_history"),
        pk=order_id, user=request.user,
    )
    return JsonResponse({"order": serialize_order(order, include_items=True)})

@csrf_exempt
@require_POST
def account_logout(request):
    logout(request)
    return JsonResponse({"ok": True})

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
            "items": [serialize_product(product, request) for product in get_store_products().filter(id__in=favorites)],
            "is_favorite": is_favorite,
            "product_id": product_id,
        }
    )

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

@staff_member_required(login_url="management_login")
@require_GET
def api_management_orders(request):
    orders = Order.objects.select_related("user", "payment_method").prefetch_related("items").order_by("-created_at")
    status = request.GET.get("status")

    if status:
        orders = orders.filter(status=status)

    return JsonResponse({"orders": [serialize_order(order) for order in orders[:100]]})

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

@require_GET
def account_orders(request):
    if not request.user.is_authenticated:
        return auth_required_payload()
    orders = Order.objects.filter(user=request.user).select_related("payment_method", "delivery_method").prefetch_related("items", "payments", "status_history").order_by("-created_at")
    return JsonResponse({"orders": [serialize_order(order, include_items=True) for order in orders]})
