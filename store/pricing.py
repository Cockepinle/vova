"""Central server-side product price calculation."""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist

from .models import CustomerPrice, CustomerProfile


MONEY_STEP = Decimal("0.01")


def as_money(value):
    return Decimal(str(value or 0)).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def customer_price_level(user):
    if not user or not getattr(user, "is_authenticated", False):
        return CustomerProfile.PRICE_RETAIL
    try:
        return user.customer_profile.price_level
    except ObjectDoesNotExist:
        return CustomerProfile.PRICE_RETAIL


def price_for_level(product, level):
    """Calculate a level price from cost and a database-stored coefficient.

    Missing cost/coefficient falls back to the retail calculation and finally
    to the existing product.price, preserving legacy catalogue data.
    """
    coefficient = getattr(product, f"{level}_coefficient", None)
    if product.cost_price is not None and coefficient is not None:
        return as_money(Decimal(product.cost_price) * Decimal(coefficient))
    if level != CustomerProfile.PRICE_RETAIL:
        return price_for_level(product, CustomerProfile.PRICE_RETAIL)
    return as_money(product.price)


def resolve_product_price(product, user=None, individual_prices=None):
    if user and getattr(user, "is_authenticated", False):
        if individual_prices is not None:
            individual = individual_prices.get(product.pk)
        else:
            individual = CustomerPrice.objects.filter(user=user, product=product).values_list("price", flat=True).first()
        if individual is not None:
            return as_money(individual)
    return price_for_level(product, customer_price_level(user))


def individual_price_map(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    return dict(CustomerPrice.objects.filter(user=user).values_list("product_id", "price"))
