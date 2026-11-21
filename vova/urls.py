from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.http import Http404, HttpResponseRedirect
from django.urls import include, path
from django.utils.encoding import filepath_to_uri

from store import cms_views

urlpatterns = [
    path("admin/login/", cms_views.AdminLoginView.as_view(), name="admin_login"),
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.MEDIA_URL.startswith(("https://", "http://")):
    def redirect_legacy_media(request, name):
        if "\\" in name or any(part in {".", ".."} for part in name.split("/")):
            raise Http404
        return HttpResponseRedirect(f"{settings.MEDIA_URL.rstrip('/')}/{filepath_to_uri(name)}")

    # Older page blocks can contain a literal /media/ URL.
    urlpatterns.insert(0, path("media/<path:name>", redirect_legacy_media))
