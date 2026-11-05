from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from store import cms_views

urlpatterns = [
    path("admin/login/", cms_views.AdminLoginView.as_view(), name="admin_login"),
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
