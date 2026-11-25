import os
from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Error, register


@register("media_storage", deploy=True)
def check_persistent_media(app_configs, **kwargs):
    if settings.CLOUDINARY_URL:
        try:
            url = urlsplit(settings.CLOUDINARY_URL)
            if url.scheme == "cloudinary" and url.hostname and url.username and url.password:
                return []
        except ValueError:
            pass
        return [Error("Invalid CLOUDINARY_URL.", hint="Use the server-side connection URL from Cloudinary.", id="store.E001")]
    if settings.IS_VERCEL or (not settings.DEBUG and not settings.PERSISTENT_MEDIA_VOLUME):
        return [Error("Persistent media storage is not configured.",
                      hint="Set CLOUDINARY_URL or mount a persistent MEDIA_ROOT outside the source tree on a non-Vercel host.",
                      id="store.E002")]
    if not settings.DEBUG and (not settings.MEDIA_ROOT.is_dir() or not os.access(settings.MEDIA_ROOT, os.W_OK)):
        return [Error("MEDIA_ROOT must be an existing writable directory on the persistent volume.", id="store.E003")]
    return []
