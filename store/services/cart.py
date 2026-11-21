from decimal import Decimal, ROUND_HALF_UP
from ..models import CartItem, Category, DeliveryMethod, PaymentMethod, Product
from .catalog import decimal_value, format_price, get_product, get_store_products_queryset, money, serialize_product

def save_session_cart(request, cart):
    request.session["cart"] = {str(product_id): int(quantity) for product_id, quantity in cart.items() if int(quantity) > 0}
    request.session.modified = True

def normalize_quantity(product, quantity):
    minimum = max(1, int(getattr(product, "min_quantity", 1) or 1))
    step = max(1, int(getattr(product, "quantity_step", 1) or 1))

    try:
        quantity = int(quantity)
    except (TypeError, ValueError, OverflowError):
        quantity = minimum

    quantity = max(minimum, quantity)
    return minimum + ((quantity - minimum + step - 1) // step) * step

def is_valid_quantity(product, quantity):
    minimum = max(1, int(getattr(product, "min_quantity", 1) or 1))
    step = max(1, int(getattr(product, "quantity_step", 1) or 1))
    try:
        parsed = int(quantity)
    except (TypeError, ValueError, OverflowError):
        return False
    if isinstance(quantity, bool) or (not isinstance(quantity, str) and parsed != quantity):
        return False
    return parsed >= minimum and (parsed - minimum) % step == 0

def serialize_cart_item(product, quantity, request=None):
    product_data = serialize_product(product, request)
    price = money(product_data["price"])
    quantity = normalize_quantity(product, quantity)
    line_total = money(price * quantity)
    unit_weight = Decimal(product.weight_kg) if product.weight_kg is not None else None
    unit_volume = Decimal(product.volume_m3) if product.volume_m3 is not None else None
    line_weight = unit_weight * quantity if unit_weight is not None else None
    line_volume = unit_volume * quantity if unit_volume is not None else None

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
        "line_total": format_price(line_total),
        "weight_kg": decimal_value(unit_weight),
        "volume_m3": decimal_value(unit_volume),
        "line_weight_kg": decimal_value(line_weight),
        "line_volume_m3": decimal_value(line_volume),
    }

def cart_metric_total(items, field):
    if not items:
        return Decimal("0")
    values = [item[field] for item in items]
    if any(value is None for value in values):
        return None
    return sum((Decimal(value) for value in values), Decimal("0"))

def clear_user_cart(user):
    CartItem.objects.filter(user=user).delete()

def get_cart_context(request):
    cart = cart_payload(request)
    return {
        "cart_items": cart["items"],
        "cart_quantities": {item["id"]: item["quantity"] for item in cart["items"]},
        "cart_count": cart["count"],
        "cart_total": cart["total"],
        "cart_weight_kg": cart["total_weight_kg"],
        "cart_volume_m3": cart["total_volume_m3"],
        "checkout_initial": get_checkout_initial(request),
        "payment_methods": PaymentMethod.objects.all(),
        "delivery_methods": DeliveryMethod.objects.all(),
    }

def cart_payload(request):
    items = get_cart_items(request)
    return {
        "items": items,
        "count": sum(item["quantity"] for item in items),
        "total": format_price(sum(money(item["line_total"]) for item in items)),
        "total_weight_kg": decimal_value(cart_metric_total(items, "line_weight_kg")),
        "total_volume_m3": decimal_value(cart_metric_total(items, "line_volume_m3")),
    }

def locked_checkout_snapshot(request):
    """Re-read the authenticated cart and all commercial values inside a transaction."""
    cart_rows = list(
        CartItem.objects.select_for_update()
        .filter(user=request.user, product__status=Product.STATUS_PUBLISHED, product__category_id__in=Category.visible_ids())
        .select_related("product")
        .prefetch_related("product__images__media", "product__media", "product__attributes__attribute", "product__variant_group__attributes")
    )
    rows = []
    unavailable_products = []
    invalid_quantities = []
    for row in cart_rows:
        if row.product.availability == Product.AVAILABILITY_OUT_OF_STOCK:
            unavailable_products.append(row.product.name)
            continue
        if not is_valid_quantity(row.product, row.quantity):
            invalid_quantities.append(row.product.name)
            continue
        quantity = normalize_quantity(row.product, row.quantity)
        if row.quantity != quantity:
            row.quantity = quantity
            row.save(update_fields=["quantity", "updated_at"])
        rows.append((row.product, serialize_cart_item(row.product, quantity, request)))
    items = [item for _product, item in rows]
    return {
        "rows": rows,
        "unavailable_products": unavailable_products,
        "invalid_quantities": invalid_quantities,
        "total": money(sum((money(item["line_total"]) for item in items), Decimal("0"))),
        "weight": cart_metric_total(items, "line_weight_kg"),
        "volume": cart_metric_total(items, "line_volume_m3"),
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

def merge_session_cart_to_user(request, user):
    session_cart = get_session_cart(request)

    if not session_cart:
        return

    for product_id, quantity in session_cart.items():
        product = get_product(product_id)

        if not product:
            continue

        item, _ = CartItem.objects.get_or_create(user=user, product=product, defaults={"quantity": 0})
        item.quantity = normalize_quantity(product, item.quantity + normalize_quantity(product, quantity))
        item.save(update_fields=["quantity", "updated_at"])

    request.session["cart"] = {}
    request.session.modified = True

def clear_cart_storage(request):
    if request.user.is_authenticated:
        clear_user_cart(request.user)
    else:
        request.session["cart"] = {}
        request.session.modified = True

def get_session_cart(request):
    return request.session.get("cart", {})

def get_cart_items(request):
    items = []

    if request.user.is_authenticated:
        cart_items = (
            CartItem.objects.filter(user=request.user, product__status=Product.STATUS_PUBLISHED, product__category_id__in=Category.visible_ids())
            .select_related("product__category", "product__variant_group")
            .prefetch_related("product__images__media", "product__media", "product__attributes__attribute", "product__variant_group__attributes")
        )

        for item in cart_items:
            normalized_quantity = normalize_quantity(item.product, item.quantity)
            if item.quantity != normalized_quantity:
                item.quantity = normalized_quantity
                item.save(update_fields=["quantity", "updated_at"])
            items.append(serialize_cart_item(item.product, item.quantity, request))

        return items

    session_cart = get_session_cart(request)
    if not session_cart:
        return items
    product_ids = {
        pk: int(pk) for pk in session_cart
        if str(pk).isascii() and str(pk).isdecimal() and len(str(pk)) <= 19 and int(pk) < 2**63
    }
    products = get_store_products_queryset().in_bulk(product_ids.values())
    normalized_session_cart = dict(session_cart)
    for product_id, quantity in session_cart.items():
        product = products.get(product_ids.get(product_id))

        if product:
            normalized_quantity = normalize_quantity(product, quantity)
            normalized_session_cart[product_id] = normalized_quantity
            items.append(serialize_cart_item(product, normalized_quantity, request))

    if normalized_session_cart != session_cart:
        save_session_cart(request, normalized_session_cart)

    return items
