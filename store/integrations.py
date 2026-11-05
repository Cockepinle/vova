"""Provider-neutral contracts for optional external commerce integrations.

This module defines only the store-side boundary. It contains no vendor API
details and is not called by the order or catalog flows.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import Order


@dataclass(frozen=True)
class CatalogUpdate:
    sku: str
    price: Decimal | None = None
    stock_quantity: int | None = None


class StoreIntegrationError(Exception):
    pass


class BaseStoreIntegration(ABC):
    code = ""

    @abstractmethod
    def send_order(self, order: Order) -> None:
        """Send a store order through a future vendor-specific adapter."""

    @abstractmethod
    def fetch_catalog_updates(self) -> Iterable[CatalogUpdate]:
        """Return normalized price/stock changes without applying them."""


_integrations: dict[str, BaseStoreIntegration] = {}


def register_integration(integration: BaseStoreIntegration) -> None:
    if not integration.code:
        raise ValueError("У интеграции должен быть задан code.")
    _integrations[integration.code] = integration


def get_integration(code: str) -> BaseStoreIntegration:
    try:
        return _integrations[code]
    except KeyError as error:
        raise StoreIntegrationError(f"Интеграция не настроена: {code}") from error
