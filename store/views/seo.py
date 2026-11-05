from .common import HttpResponse, PageContent, SiteSettings, get_store_categories_queryset, get_store_products_queryset, require_GET, reverse

@require_GET
def sitemap_xml(request):
    from urllib.parse import urlencode
    from xml.etree.ElementTree import Element, SubElement, tostring
    from django.urls import reverse
    from ..seo import absolute_url, PAGE_PATHS
    config = SiteSettings.get_solo()
    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    if config.allow_indexing:
        pages = {page.page: page for page in PageContent.objects.filter(is_visible=True)}
        paths = []
        for key, path in PAGE_PATHS.items():
            page = pages.get(key)
            if not (page and page.noindex):
                paths.append((page.canonical if page and page.canonical else path, page.updated_at if page else None))
        for category in get_store_categories_queryset():
            paths.append((category.canonical or '/catalog/?' + urlencode({'category':category.slug}), None))
        for product in get_store_products_queryset():
            paths.append((product.canonical or reverse('product_detail', args=[product.slug]), product.updated_at))
        origin = absolute_url(request, config, '/').rstrip('/')
        seen = set()
        for path, updated in paths:
            url = absolute_url(request, config, path)
            if url in seen or not url.startswith(origin + '/'):
                continue
            seen.add(url)
            node = SubElement(root, 'url')
            SubElement(node, 'loc').text = url
            if updated:
                SubElement(node, 'lastmod').text = updated.date().isoformat()
    return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml')

@require_GET
def robots_txt(request):
    from ..seo import absolute_url
    config = SiteSettings.get_solo()
    if not config.allow_indexing:
        content = "User-agent: *\nDisallow: /\n"
    else:
        content = "User-agent: *\nAllow: /\nDisallow: /management/\nDisallow: /admin/\nDisallow: /account/\nDisallow: /api/\nDisallow: /cart/\nDisallow: /favorites/\nDisallow: /requests/\n"
    return HttpResponse(content + "Sitemap: " + absolute_url(request, config, "/sitemap.xml") + "\n", content_type="text/plain; charset=utf-8")
