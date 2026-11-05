from ..models import Order
from .accounts import get_favorites_context
from .cart import get_cart_context

def apply_common_context(request, context):
    context.update(get_cart_context(request))
    context.update(get_favorites_context(request))
    context["account_orders"] = (
        Order.objects.filter(user=request.user).select_related("payment_method", "delivery_method").prefetch_related("items").order_by("-created_at")
        if request.user.is_authenticated else []
    )

    return context
