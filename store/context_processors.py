from .models import Category, PageContent, SiteSettings


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

    return {
        "site_settings": settings,
        "page_content": pages,
        "footer_categories": footer_categories,
    }
