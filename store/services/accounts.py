import secrets
import smtplib
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from ..models import Category, EmailVerificationCode, FavoriteItem, Product
from .catalog import get_store_products, serialize_product

def auth_required_payload():
    return JsonResponse({"auth_required": True, "error": "Войдите или зарегистрируйтесь, чтобы продолжить"}, status=403)

def send_account_code(email, subject, text):
    code = str(100000 + secrets.randbelow(900000))
    EmailVerificationCode.objects.filter(email=email, is_used=False).update(is_used=True)

    try:
        send_mail(subject, text.format(code=code), None, [email], fail_silently=False)
    except (smtplib.SMTPException, OSError, TimeoutError):
        if settings.DEBUG:
            return code, f"Почта сейчас не отправилась, но код создан. Код для локальной проверки: {code}"

        return None, "Не удалось отправить код на почту. Проверьте SMTP-настройки и попробуйте ещё раз."

    return code, "Мы отправили код подтверждения на email."


def check_account_verification(email, code, purpose):
    """Check the newest code within the caller's transaction."""
    if len(code) != 6 or not code.isascii() or not code.isdecimal():
        return None
    purpose_filter = Q(payload__type=purpose)
    if purpose == "registration":
        purpose_filter |= Q(payload__has_key="password")  # Legacy pending signups.
    verification = EmailVerificationCode.objects.select_for_update().filter(
        purpose_filter, email=email,
        created_at__gte=timezone.now() - timedelta(minutes=15),
    ).order_by("-created_at", "-pk").first()
    if not verification or verification.is_used:
        return None
    if constant_time_compare(verification.code, code):
        return verification
    attempts = verification.payload.get("failed_attempts", 0) + 1
    verification.payload["failed_attempts"] = attempts
    verification.is_used = attempts >= 5
    if verification.is_used:
        verification.payload = {"type": purpose}
    verification.save(update_fields=["payload", "is_used"])
    return None


def consume_account_verification(verification, purpose):
    verification.is_used = True
    verification.payload = {"type": purpose}
    verification.save(update_fields=["is_used", "payload"])

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
