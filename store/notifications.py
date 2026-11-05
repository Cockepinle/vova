import logging

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def notify_manager(subject, message):
    if not settings.MANAGER_EMAIL:
        return
    send_mail(subject, message, None, [settings.MANAGER_EMAIL], fail_silently=True)


def notify_manager_safely(subject, message):
    try:
        notify_manager(subject, message)
    except Exception:
        logger.exception("Manager notification failed: %s", subject)
