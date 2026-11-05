from dataclasses import dataclass
from typing import Any

from .models import DeliveryMethod, Order, SiteSettings


@dataclass(frozen=True)
class DeliveryHandoff:
    url: str
    data: dict[str, Any]


class BaseDeliveryProvider:
    code = ""

    def prepare_delivery(self, method: DeliveryMethod, request_data: dict[str, Any]) -> DeliveryHandoff:
        return DeliveryHandoff(
            url=method.handoff_url,
            data={"request": request_data},
        )


_providers: dict[str, BaseDeliveryProvider] = {}


def register_delivery_provider(provider: BaseDeliveryProvider) -> None:
    if not provider.code:
        raise ValueError("У delivery provider должен быть задан code.")
    _providers[provider.code] = provider


def delivery_request_data(order: Order, settings: SiteSettings) -> dict[str, Any]:
    packages = []
    for item in order.items.all():
        packages.append(
            {
                "sku": item.product_sku,
                "name": item.product_name,
                "quantity": item.quantity,
                "weight_kg": str(item.weight_kg) if item.weight_kg is not None else None,
                "volume_m3": str(item.volume_m3) if item.volume_m3 is not None else None,
                "dimensions_mm": {
                    "length": str(item.length_mm) if item.length_mm is not None else None,
                    "width": str(item.width_mm) if item.width_mm is not None else None,
                    "height": str(item.height_mm) if item.height_mm is not None else None,
                },
            }
        )

    return {
        "order": {"id": order.pk, "number": order.number},
        "recipient": {
            "name": order.full_name,
            "phone": order.phone,
            "email": order.email,
        },
        "origin_address": order.delivery_origin_address or settings.contact_address,
        "destination_address": order.delivery_address,
        "total_weight_kg": str(order.total_weight_kg) if order.total_weight_kg is not None else None,
        "total_volume_m3": str(order.total_volume_m3) if order.total_volume_m3 is not None else None,
        "packages": packages,
        "provider_config": order.delivery_method.provider_config if order.delivery_method_id else {},
    }


def prepare_delivery_handoff(order: Order) -> DeliveryHandoff:
    method = order.delivery_method
    if not method or order.delivery_method_kind != DeliveryMethod.KIND_CARRIER:
        return DeliveryHandoff(url="", data={})

    settings = SiteSettings.get_solo()
    request_data = delivery_request_data(order, settings)
    provider = _providers.get(method.provider_code, BaseDeliveryProvider())
    return provider.prepare_delivery(method, request_data)
