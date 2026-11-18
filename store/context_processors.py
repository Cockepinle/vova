from .models import Category, PageContent, SiteSettings
from .seo import metadata


def site_content(request):
    footer_categories = []
    new_orders_count = 0

    try:
        settings = SiteSettings.get_solo()
        all_pages = list(PageContent.objects.filter(is_visible=True))
        pages = {item.page: item for item in all_pages if not item.is_custom}
        pages.update({f"custom:{item.slug}": item for item in all_pages if item.is_custom and item.slug})
    except Exception:
        settings = None
        pages = {}

    try:
        footer_categories = Category.tree_rows(visible_only=True)
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
    elif key == "custom_page":
        page = pages.get(f"custom:{request.resolver_match.kwargs.get('slug')}")
        if page:
            pages["custom_page"] = page
    if key == "product_detail":
        key = "catalog"
    if key and key.startswith("management_"):
        from .models import Order
        new_orders_count = Order.objects.filter(status__in=[Order.STATUS_NEW, Order.STATUS_CHECKOUT_STARTED]).count()
    return {
        "seo": metadata(request, settings, pages),
        "current_page": pages.get(key),
        "header_links": [link for link in links if link.location == "header"],
        "footer_links": [link for link in links if link.location == "footer"],
        "social_links": [link for link in links if link.location == "social"],
        "site_settings": settings,
        "page_content": pages,
        "footer_categories": footer_categories,
        "new_orders_count": new_orders_count,
    }
