from .models import Category, PageContent, SiteSettings
from .seo import metadata


def site_content(request):
    footer_categories = []

    try:
        settings = SiteSettings.get_solo()
        pages = {item.page: item for item in PageContent.objects.filter(is_visible=True)}
    except Exception:
        settings = None
        pages = {}

    try:
        footer_categories = Category.objects.filter(is_active=True).order_by("sort_order", "name")

        if not footer_categories.exists():
            footer_categories = Category.objects.order_by("sort_order", "name")
    except Exception:
        footer_categories = []

    # Missing or hidden CMS records must still allow template fallback values.
    for key, _label in PageContent.PAGE_CHOICES:
        pages.setdefault(key, PageContent(page=key))

    settings = settings or SiteSettings()
    links = list(settings.links.filter(is_visible=True)) if settings.pk else []
    key = request.resolver_match.url_name if request.resolver_match else "home"
    if key == "document_page":
        key = request.resolver_match.kwargs.get("slug")
    if key == "product_detail":
        key = "catalog"
    return {
        "seo": metadata(request, settings, pages),
        "current_page": pages.get(key),
        "header_links": [link for link in links if link.location == "header"],
        "footer_links": [link for link in links if link.location == "footer"],
        "social_links": [link for link in links if link.location == "social"],
        "site_settings": settings,
        "page_content": pages,
        "footer_categories": footer_categories,
    }
