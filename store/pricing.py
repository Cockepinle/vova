"""Central server-side product price calculation."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist

from .models import CustomerPrice, CustomerProfile


MONEY_STEP = Decimal("0.01")
MAX_UNIT_PRICE = Decimal("9999999999.99")
PRICE_LEVELS = dict(CustomerProfile.PRICE_LEVEL_CHOICES)


@dataclass(frozen=True)
class PriceQuote:
    amount: Decimal
    level: str
    source: str
    coefficient: Decimal | None = None


def as_money(value):
    return Decimal(str(value or 0)).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def customer_price_level(user):
    if not user or not getattr(user, "is_authenticated", False):
        return CustomerProfile.PRICE_RETAIL
    try:
        level = user.customer_profile.price_level
        return level if level in PRICE_LEVELS else CustomerProfile.PRICE_RETAIL
    except ObjectDoesNotExist:
        return CustomerProfile.PRICE_RETAIL


def calculate_unit_price(base, coefficient):
    return as_money(Decimal(base) * Decimal(coefficient))


def quote_for_level(product, level, coefficient=None):
    if level not in PRICE_LEVELS:
        level = CustomerProfile.PRICE_RETAIL
    if product.cost_price is not None:
        if coefficient is not None:
            return PriceQuote(calculate_unit_price(product.cost_price, coefficient), level, "customer", coefficient)
        product_coefficient = getattr(product, f"{level}_coefficient", None)
        if product_coefficient is not None:
            return PriceQuote(calculate_unit_price(product.cost_price, product_coefficient), level, "product", product_coefficient)
    if level != CustomerProfile.PRICE_RETAIL:
        return quote_for_level(product, CustomerProfile.PRICE_RETAIL)
    return PriceQuote(as_money(product.price), level, "manual")


def price_for_level(product, level, coefficient=None):
    return quote_for_level(product, level, coefficient).amount


def resolve_product_price(product, user=None, individual_prices=None):
    return resolve_product_quote(product, user, individual_prices).amount


def resolve_product_quote(product, user=None, individual_prices=None):
    level = customer_price_level(user)
    if user and getattr(user, "is_authenticated", False):
        if individual_prices is not None:
            individual = individual_prices.get(product.pk)
        else:
            individual = CustomerPrice.objects.filter(user=user, product=product).values_list("price", flat=True).first()
        if individual is not None:
            return PriceQuote(as_money(individual), level, "individual")
    coefficient = None
    if user and getattr(user, "is_authenticated", False):
        try:
            coefficient = getattr(user.customer_profile, f"{level}_coefficient", None)
        except ObjectDoesNotExist:
            coefficient = None
    return quote_for_level(product, level, coefficient)


def individual_price_map(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    return dict(CustomerPrice.objects.filter(user=user).values_list("product_id", "price"))
