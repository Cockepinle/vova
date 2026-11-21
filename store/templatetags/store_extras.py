import json
import re

from django import template

from store.uploads import upload_policy

register = template.Library()
register.simple_tag(upload_policy)


@register.filter
def to_json(value):
    return json.dumps(value, ensure_ascii=False)


@register.filter
def get_item(value, key):
    return value.get(key)


@register.filter
def phone_href(value):
    phone = re.sub(r"[^\d+]", "", str(value or ""))

    if phone.startswith("8"):
        phone = f"+7{phone[1:]}"
    elif phone.startswith("7"):
        phone = f"+{phone}"

    return phone


DEMO_COPY_REPLACEMENTS = {
    "демо-категорий": "",
    "примеров товаров": "",
    "Демонстрационные размеры и цены. Подтвердите параметры, наличие и стоимость перед оформлением заказа.": "",
    (
        "Короба для отправлений, переезда, хранения и маркетплейсов. "
        "Каталог содержит демонстрационные товары и цены — уточняйте характеристики и условия перед заказом."
    ): "Короба для отправлений, переезда, хранения и маркетплейсов.",
    (
        "Укажите размеры коробки, тип гофрокартона и нужное количество. "
        "Цены и сроки на сайте приведены как демонстрационные примеры."
    ): "Укажите размеры коробки, тип гофрокартона и нужное количество.",
    (
        "Демонстрационный каталог картонных коробок для оптовых заказов. "
        "Проверьте цены, характеристики и реквизиты перед публикацией."
    ): "",
}


@register.filter
def without_demo_copy(value):
    return DEMO_COPY_REPLACEMENTS.get(" ".join(str(value or "").split()), value)
