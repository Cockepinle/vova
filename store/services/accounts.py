import random
import smtplib
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse
from ..models import Category, EmailVerificationCode, FavoriteItem, Product
from .catalog import get_store_products, serialize_product

def auth_required_payload():
    return JsonResponse({"auth_required": True, "error": "Войдите или зарегистрируйтесь, чтобы продолжить"}, status=403)

def send_account_code(email, subject, text):
    code = f"{random.randint(100000, 999999)}"
    EmailVerificationCode.objects.filter(email=email, is_used=False).update(is_used=True)

    try:
        send_mail(subject, text.format(code=code), None, [email], fail_silently=False)
    except (smtplib.SMTPException, OSError, TimeoutError):
        if settings.DEBUG:
            return code, f"Почта сейчас не отправилась, но код создан. Код для локальной проверки: {code}"

        return None, "Не удалось отправить код на почту. Проверьте SMTP-настройки и попробуйте ещё раз."

    return code, "Мы отправили код подтверждения на email."

def get_favorite_ids(request):
    if not request.user.is_authenticated:
        return []

    return [str(product_id) for product_id in FavoriteItem.objects.filter(user=request.user, product__status=Product.STATUS_PUBLISHED, product__category_id__in=Category.visible_ids()).values_list("product_id", flat=True)]

def get_favorites_context(request):
    favorite_ids = get_favorite_ids(request)
    favorite_products = [serialize_product(product, request) for product in get_store_products().filter(id__in=favorite_ids)]

    return {
        "favorite_ids": favorite_ids,
        "favorite_products": favorite_products,
        "favorite_count": len(favorite_ids),
        "account_user": request.user if request.user.is_authenticated else None,
    }
