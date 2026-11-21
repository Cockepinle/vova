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
