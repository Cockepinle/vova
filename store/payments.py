"""Provider-neutral payment lifecycle.

Concrete providers register an implementation without changing order logic.
Only a verified provider webhook may mark a payment as paid.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from django.db import transaction

from .models import Order, Payment


class PaymentProviderError(Exception):
    pass


@dataclass(frozen=True)
class PaymentCreationResult:
    external_id: str = ""
    payment_url: str = ""
    status: str = Order.PAYMENT_PENDING
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentCallbackResult:
    external_id: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)


class BasePaymentProvider(ABC):
    code: str

    @abstractmethod
    def create_payment(self, payment: Payment, return_url: str) -> PaymentCreationResult:
        """Create a remote payment and return its URL/data."""

    @abstractmethod
    def check_status(self, payment: Payment) -> PaymentCallbackResult:
        """Request the current status from the provider."""

    @abstractmethod
    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentCallbackResult:
        """Verify signature and parse a provider webhook."""

    def cancel(self, payment: Payment) -> PaymentCallbackResult:
        raise PaymentProviderError("Отмена не поддерживается провайдером.")

    def refund(self, payment: Payment, amount=None) -> PaymentCallbackResult:
        raise PaymentProviderError("Возврат не поддерживается провайдером.")


_providers: dict[str, BasePaymentProvider] = {}


def register_provider(provider: BasePaymentProvider):
    _providers[provider.code] = provider
    return provider


def get_provider(code: str) -> BasePaymentProvider:
    try:
        return _providers[code]
    except KeyError as error:
        raise PaymentProviderError("Платёжный провайдер пока не настроен.") from error


def create_order_payment(order: Order, return_url: str):
    method = order.payment_method
    payment = Payment.objects.create(
        order=order,
        payment_method=method,
        provider_code=method.provider_code,
        idempotency_key=uuid4().hex,
        amount=order.total,
    )
    try:
        result = get_provider(method.provider_code).create_payment(payment, return_url)
    except PaymentProviderError as error:
        payment.provider_data = {"integration_error": str(error)}
        payment.save(update_fields=["provider_data", "updated_at"])
        return payment, str(error)
    apply_provider_result(payment, result.external_id, result.status, result.payment_url, result.data)
    return payment, ""


@transaction.atomic
def apply_provider_result(payment: Payment, external_id: str, status: str, payment_url: str = "", data=None):
    if status not in dict(Order.PAYMENT_STATUS_CHOICES):
        raise PaymentProviderError("Провайдер вернул неизвестный статус.")
    payment.external_id = external_id or payment.external_id
    payment.status = status
    payment.payment_url = payment_url or payment.payment_url
    payment.provider_data = data or payment.provider_data
    payment.save(update_fields=["external_id", "status", "payment_url", "provider_data", "updated_at"])
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    order.payment_status = status
    fields = ["payment_status", "updated_at"]
    if status == Order.PAYMENT_PAID and order.status not in {Order.STATUS_DONE, Order.STATUS_CANCELED}:
        order.status = Order.STATUS_PAID
        fields.append("status")
    order.save(update_fields=fields)


@transaction.atomic
def process_webhook(provider_code: str, body: bytes, headers: dict[str, str]):
    provider = get_provider(provider_code)
    result = provider.parse_webhook(body, headers)
    payment = Payment.objects.select_for_update().get(provider_code=provider_code, external_id=result.external_id)
    apply_provider_result(payment, result.external_id, result.status, data=result.data)
    return payment
