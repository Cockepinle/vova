from decimal import Decimal, ROUND_HALF_UP
from ..models import DeliveryMethod, Order, OrderItem, SiteSettings
from ..deliveries import prepare_delivery_handoff
from .catalog import decimal_value, format_price, money

def set_order_delivery(order, method, address):
    shop_settings = SiteSettings.get_solo()
    order.delivery_method = method
    order.delivery_method_name = method.name
    order.delivery_method_kind = method.kind
    order.delivery_provider_code = method.provider_code
    order.delivery_origin_address = shop_settings.contact_address
    order.delivery_address = (
        shop_settings.pickup_address or shop_settings.contact_address
        if method.kind == DeliveryMethod.KIND_PICKUP
        else address
    )

def serialize_order_item(item):
    return {
        "product_id": str(item.product_id),
        "name": item.product_name,
        "sku": item.product_sku,
        "unit": item.unit,
        "quantity": item.quantity,
        "price": format_price(item.price),
        "line_total": format_price(item.line_total),
        "vat_rate": decimal_value(item.vat_rate),
        "weight_kg": decimal_value(item.weight_kg),
        "volume_m3": decimal_value(item.volume_m3),
        "dimensions_mm": {
            "length": decimal_value(item.length_mm),
            "width": decimal_value(item.width_mm),
            "height": decimal_value(item.height_mm),
        },
    }

def refresh_delivery_handoff(order):
    handoff = prepare_delivery_handoff(order)
    order.delivery_handoff_url = handoff.url
    order.delivery_provider_data = handoff.data
    order.save(update_fields=["delivery_handoff_url", "delivery_provider_data", "updated_at"])

def replace_order_snapshot(order, snapshot):
    order.items.all().delete()
    for product, item in snapshot["rows"]:
        OrderItem.objects.create(
            order=order, product=product, product_name=item["name"], product_sku=item["sku"], unit=item["unit"],
            quantity=item["quantity"], price=money(item["price"]), line_total=money(item["line_total"]),
            vat_rate=Decimal(item["product"]["vat_rate"]),
            weight_kg=Decimal(item["product"]["weight_kg"]) if item["product"]["weight_kg"] is not None else None,
            volume_m3=Decimal(item["product"]["volume_m3"]) if item["product"]["volume_m3"] is not None else None,
            length_mm=product.length_mm,
            width_mm=product.width_mm,
            height_mm=product.height_mm,
        )

def serialize_order(order, include_items=False):
    data = {
        "id": str(order.id),
        "number": order.number,
        "status": order.status,
        "status_label": order.get_status_display(),
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "total": format_price(order.total),
        "total_weight_kg": decimal_value(order.total_weight_kg),
        "total_volume_m3": decimal_value(order.total_volume_m3),
        "payment_method": order.payment_method.code if order.payment_method_id else "",
        "payment_method_label": order.payment_method_name or (order.payment_method.name if order.payment_method_id else ""),
        "payment_status": order.payment_status,
        "payment_status_label": order.get_payment_status_display(),
        "delivery_method": order.delivery_method.code if order.delivery_method_id else "",
        "delivery_method_label": order.delivery_method_name or (order.delivery_method.name if order.delivery_method_id else ""),
        "delivery_kind": order.delivery_method_kind,
        "delivery_kind_label": order.get_delivery_method_kind_display(),
        "delivery_provider_code": order.delivery_provider_code,
        "delivery_address": order.delivery_address,
        "delivery_url": order.delivery_handoff_url,
        "customer": {
            "full_name": order.full_name,
            "phone": order.phone,
            "email": order.email,
            "company": order.company,
            "user_id": str(order.user_id),
            "user_email": order.user.email or order.user.username,
        },
        "comment": order.comment,
        "items_count": sum(item.quantity for item in order.items.all()),
    }

    if include_items:
        data["items"] = [serialize_order_item(item) for item in order.items.all()]
        data["status_history"] = [{"status": entry.status, "created_at": entry.created_at.isoformat()} for entry in order.status_history.all()]
        data["payments"] = [
            {"id": str(payment.pk), "amount": format_price(payment.amount), "currency": payment.currency,
             "status": payment.status, "provider_code": payment.provider_code, "external_id": payment.external_id,
             "payment_url": payment.payment_url, "created_at": payment.created_at.isoformat()}
            for payment in order.payments.all()
        ]

    return data

def current_checkout_order(request, supplied_id=None):
    order_id = supplied_id or request.session.get("checkout_order_id")
    orders = Order.objects.select_for_update().filter(user=request.user, status=Order.STATUS_CHECKOUT_STARTED)
    if str(order_id or "").isdigit():
        order = orders.filter(pk=order_id).first()
        if order:
            return order
    return orders.order_by("-updated_at").first()
