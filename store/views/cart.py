from django.views.decorators.cache import never_cache

from .common import CartItem, DeliveryMethod, JsonResponse, Order, Payment, PaymentMethod, PaymentProviderError, User, auth_required_payload, cart_payload
from .common import clear_cart_storage, create_order_payment, csrf_exempt, current_checkout_order, get_checkout_initial, get_product, get_session_cart, is_valid_quantity, json, locked_checkout_snapshot, normalize_quantity
from .common import notify_manager_safely, process_webhook, refresh_delivery_handoff, replace_order_snapshot, require_GET, require_POST, reverse, save_session_cart, set_order_delivery, transaction
from .common import uuid4

MAX_CART_QUANTITY = 2_147_483_647


def cart_quantity(payload, *, default=None, minimum=0):
    value = payload.get("quantity", default)
    if type(value) is str and value.isascii() and value.isdecimal() and len(value) <= 10:
        value = int(value)
    if type(value) is not int or not minimum <= value <= MAX_CART_QUANTITY:
        raise ValueError
    return value


def cart_product_id(payload):
    value = str(payload.get("product_id", ""))
    if not value.isascii() or not value.isdecimal() or len(value) > 19 or not 0 < int(value) <= 2**63 - 1:
        raise ValueError
    return str(int(value))


@csrf_exempt
@require_POST
def payment_webhook(request, provider_code):
    try:
        payment = process_webhook(provider_code, request.body, dict(request.headers))
    except (PaymentProviderError, Payment.DoesNotExist):
        return JsonResponse({"ok": False}, status=400)
    return JsonResponse({"ok": True, "payment_id": payment.pk})

@require_POST
@transaction.atomic
def clear_cart(request):
    if request.user.is_authenticated:
        User.objects.select_for_update().get(pk=request.user.pk)
    clear_cart_storage(request)
    return JsonResponse(cart_payload(request))

@require_POST
@transaction.atomic
def update_cart(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        quantity = cart_quantity(payload)
        if "product_ids" in payload:
            if quantity or not isinstance(payload["product_ids"], list) or not payload["product_ids"]:
                raise ValueError
            product_ids = {cart_product_id({"product_id": pk}) for pk in payload["product_ids"]}
        else:
            product_id = cart_product_id(payload)
            product_ids = {product_id}
    except (ValueError, AttributeError):
        return JsonResponse({"error": "Укажите товар и целое количество"}, status=400)
    product = get_product(product_id, with_details=False) if quantity else None

    if quantity > 0 and not product:
        return JsonResponse({"error": "Товар не найден"}, status=404)

    if product and quantity > 0:
        if product.availability == product.AVAILABILITY_OUT_OF_STOCK:
            return JsonResponse({"error": "Товар временно отсутствует"}, status=409)
        quantity = normalize_quantity(product, quantity)
        if quantity > MAX_CART_QUANTITY:
            return JsonResponse({"error": "Количество слишком велико"}, status=400)

    if request.user.is_authenticated:
        User.objects.select_for_update().get(pk=request.user.pk)
        if quantity <= 0:
            CartItem.objects.filter(user=request.user, product_id__in=product_ids).delete()
        else:
            CartItem.objects.update_or_create(user=request.user, product=product, defaults={"quantity": quantity})
    else:
        cart = get_session_cart(request)

        if quantity <= 0:
            for selected_id in product_ids:
                cart.pop(selected_id, None)
        else:
            cart[product_id] = quantity

        save_session_cart(request, cart)

    return JsonResponse(cart_payload(request))

@require_POST
@transaction.atomic
def start_checkout(request):
    if not request.user.is_authenticated:
        return auth_required_payload()
    User.objects.select_for_update().get(pk=request.user.pk)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)
    payment_method = PaymentMethod.objects.filter(
        code=payload.get("payment_method") or "invoice",
        kind=PaymentMethod.KIND_INVOICE,
        is_active=True,
    ).first()
    delivery_method = DeliveryMethod.objects.filter(
        code=payload.get("delivery_method") or "pickup",
        kind=DeliveryMethod.KIND_PICKUP,
        is_active=True,
    ).first()
    if not payment_method:
        return JsonResponse({"error": "Выберите способ оплаты"}, status=400)
    if not delivery_method:
        return JsonResponse({"error": "Выберите способ доставки"}, status=400)
    snapshot = locked_checkout_snapshot(request)
    if snapshot["invalid_quantities"]:
        return JsonResponse(
            {"error": "Недопустимое количество для товара: " + ", ".join(snapshot["invalid_quantities"])},
            status=409,
        )
    invalid_quantities = [
        product.name
        for product, item in snapshot["rows"]
        if not is_valid_quantity(product, item["quantity"])
    ]
    if invalid_quantities:
        return JsonResponse(
            {"error": "Недопустимое количество для товара: " + ", ".join(invalid_quantities)},
            status=409,
        )
    if snapshot["unavailable_products"]:
        names = ", ".join(snapshot["unavailable_products"])
        return JsonResponse(
            {"error": f"Удалите товары, которых нет в наличии: {names}"},
            status=409,
        )
    if not snapshot["rows"]:
        return JsonResponse({"error": "Корзина пуста"}, status=400)
    order = current_checkout_order(request, payload.get("checkout_order_id"))
    initial = get_checkout_initial(request)
    if order is None:
        order = Order(user=request.user, status=Order.STATUS_CHECKOUT_STARTED)
    order.full_name = initial["full_name"]
    order.phone = initial["phone"]
    order.email = initial["email"] or request.user.email
    order.company = initial["company"]
    order.total = snapshot["total"]
    order.stored_total_weight_kg = snapshot["weight"]
    order.stored_total_volume_m3 = snapshot["volume"]
    order.payment_method = payment_method
    order.payment_method_name = payment_method.name
    set_order_delivery(order, delivery_method, str(payload.get("delivery_address") or "").strip())
    order.payment_status = Order.PAYMENT_PENDING
    order.save()
    replace_order_snapshot(order, snapshot)
    refresh_delivery_handoff(order)
    request.session["checkout_order_id"] = order.pk
    request.session.modified = True
    return JsonResponse({"ok": True, "checkout_order_id": order.pk, "order_number": order.number, "status": order.status})

@require_POST
@transaction.atomic
def checkout_order(request):
    if not request.user.is_authenticated:
        return auth_required_payload()
    User.objects.select_for_update().get(pk=request.user.pk)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Некорректные данные"}, status=400)

    full_name = (payload.get("full_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    company = (payload.get("company") or "").strip()
    comment = (payload.get("comment") or "").strip()
    payment_method = PaymentMethod.objects.filter(
        code=payload.get("payment_method") or "invoice",
        kind=PaymentMethod.KIND_INVOICE,
        is_active=True,
    ).first()
    delivery_method = DeliveryMethod.objects.filter(
        code=payload.get("delivery_method") or "pickup",
        kind=DeliveryMethod.KIND_PICKUP,
        is_active=True,
    ).first()

    if not full_name or not phone or not email:
        return JsonResponse({"error": "Заполните ФИО, телефон и email"}, status=400)
    if not payment_method:
        return JsonResponse({"error": "Выберите способ оплаты"}, status=400)
    if not delivery_method:
        return JsonResponse({"error": "Сейчас доступен только самовывоз"}, status=400)

    checkout_order_id = payload.get("checkout_order_id") or request.session.get("checkout_order_id")
    if str(checkout_order_id or "").isdigit():
        existing_order = Order.objects.select_for_update().filter(
            pk=checkout_order_id,
            user=request.user,
            status__in=[
                Order.STATUS_PENDING_PAYMENT,
                Order.STATUS_AWAITING_INVOICE,
                Order.STATUS_INVOICED,
                Order.STATUS_PROCESSING,
                Order.STATUS_PAID,
                Order.STATUS_DONE,
            ],
        ).first()
        if existing_order:
            payment = existing_order.payments.filter(status=Order.PAYMENT_PENDING).first()
            return JsonResponse({
                "ok": True,
                "message": f"Заказ {existing_order.number} уже оформлен.",
                "order_number": existing_order.number,
                "payment_url": payment.payment_url if payment else "",
                "payment_status": existing_order.payment_status,
                "delivery_url": existing_order.delivery_handoff_url,
                "delivery_data": existing_order.delivery_provider_data,
                "cart": cart_payload(request),
            })

    snapshot = locked_checkout_snapshot(request)
    invalid_quantities = [
        product.name
        for product, item in snapshot["rows"]
        if not is_valid_quantity(product, item["quantity"])
    ]
    if invalid_quantities:
        return JsonResponse(
            {"error": "Недопустимое количество для товара: " + ", ".join(invalid_quantities)},
            status=409,
        )
    if snapshot["unavailable_products"]:
        names = ", ".join(snapshot["unavailable_products"])
        return JsonResponse(
            {"error": f"Удалите товары, которых нет в наличии: {names}"},
            status=409,
        )
    if not snapshot["rows"]:
        return JsonResponse({"error": "Корзина пуста"}, status=400)
    order = current_checkout_order(request, payload.get("checkout_order_id"))
    if order is None:
        order = Order(user=request.user)
    order.full_name = full_name
    order.phone = phone
    order.email = email
    order.company = company
    order.comment = comment
    order.total = snapshot["total"]
    order.stored_total_weight_kg = snapshot["weight"]
    order.stored_total_volume_m3 = snapshot["volume"]
    order.payment_method = payment_method
    order.payment_method_name = payment_method.name
    set_order_delivery(order, delivery_method, str(payload.get("delivery_address") or "").strip())
    order.payment_status = Order.PAYMENT_PENDING
    order.status = Order.STATUS_PENDING_PAYMENT if payment_method.kind == PaymentMethod.KIND_ONLINE else Order.STATUS_AWAITING_INVOICE
    order.save()
    replace_order_snapshot(order, snapshot)
    refresh_delivery_handoff(order)
    cart_items = [item for _product, item in snapshot["rows"]]

    payment_url = ""
    payment_message = ""
    if payment_method.kind == PaymentMethod.KIND_ONLINE:
        payment, payment_message = create_order_payment(order, request.build_absolute_uri(reverse("home")))
        payment_url = payment.payment_url
    else:
        Payment.objects.create(
            order=order, payment_method=payment_method, provider_code=payment_method.provider_code,
            idempotency_key=uuid4().hex, amount=order.total, status=Order.PAYMENT_PENDING,
        )

    order_lines = "\n".join(
        f"- {item['name']} × {item['quantity']} {item['unit']} (мин. {item['product']['min_quantity']} {item['unit']}) — {item['line_total']} ₽"
        for item in cart_items
    )
    notify_manager_safely(
        (f"Клиент запросил счёт: {order.number}" if payment_method.kind == PaymentMethod.KIND_INVOICE else f"Новый заказ {order.number}"),
        "\n".join(
            [
                f"Номер заказа: {order.number}",
                f"Клиент: {full_name}",
                f"Телефон: {phone}",
                f"Email: {email}",
                f"Компания: {company or 'не указана'}",
                f"Итого: {order.total} ₽",
                f"Вес: {order.total_weight_kg} кг",
                f"Объём: {order.total_volume_m3} м³",
                f"Способ оплаты: {order.payment_method_name}",
                f"Способ доставки: {order.delivery_method_name}",
                f"Адрес получения: {order.delivery_address or 'не указан'}",
                "",
                "Состав заказа:",
                order_lines,
                "",
                f"Комментарий: {comment or 'не указан'}",
            ]
        ),
    )
    clear_cart_storage(request)
    request.session.pop("checkout_order_id", None)
    request.session.modified = True

    return JsonResponse(
        {
            "ok": True,
            "message": (f"Заказ {order.number} создан. {payment_message}" if payment_message else f"Заказ {order.number} принят. Менеджер свяжется с вами."),
            "order_number": order.number,
            "payment_url": payment_url,
            "payment_status": order.payment_status,
            "delivery_url": order.delivery_handoff_url,
            "delivery_data": order.delivery_provider_data,
            "cart": cart_payload(request),
        }
    )

@require_POST
@transaction.atomic
def add_to_cart(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        product_id = cart_product_id(payload)
        quantity = cart_quantity(payload, default=1, minimum=1)
    except (ValueError, AttributeError):
        return JsonResponse({"error": "Укажите товар и целое количество"}, status=400)
    product = get_product(product_id, with_details=False)

    if not product:
        return JsonResponse({"error": "Товар не найден"}, status=404)

    if product.availability == product.AVAILABILITY_OUT_OF_STOCK:
        return JsonResponse({"error": "Товар временно отсутствует"}, status=409)

    quantity = normalize_quantity(product, quantity)

    if request.user.is_authenticated:
        User.objects.select_for_update().get(pk=request.user.pk)
        existing = CartItem.objects.filter(user=request.user, product=product).values_list("quantity", flat=True).first()
        if existing and payload.get("if_absent") is True:
            return JsonResponse({**cart_payload(request), "already_in_cart": True})
        total = normalize_quantity(product, (existing or 0) + quantity)
        if total > MAX_CART_QUANTITY:
            return JsonResponse({"error": "Количество слишком велико"}, status=400)
        CartItem.objects.update_or_create(user=request.user, product=product, defaults={"quantity": total})
    else:
        cart = get_session_cart(request)
        if cart.get(product_id) and payload.get("if_absent") is True:
            return JsonResponse({**cart_payload(request), "already_in_cart": True})
        total = normalize_quantity(product, int(cart.get(product_id, 0)) + quantity)
        if total > MAX_CART_QUANTITY:
            return JsonResponse({"error": "Количество слишком велико"}, status=400)
        cart[product_id] = total
        save_session_cart(request, cart)

    return JsonResponse(cart_payload(request))

@require_GET
@never_cache
def api_cart(request):
    return JsonResponse(cart_payload(request))
