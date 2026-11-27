"""Metadata defaults and canonical URLs shared by HTML, robots and sitemap."""
from urllib.parse import urlencode
from django.urls import reverse
from .models import Category, Product

PAGE_PATHS = {'home':'/', 'catalog':'/catalog/', 'team':'/team/', 'contacts':'/contacts/', 'promotions':'/promotions/', 'privacy':'/documents/privacy/', 'offer':'/documents/offer/'}
PAGE_DEFAULTS = {
    'home': ('Упаковка для вашего бизнеса', 'Оптовые поставки упаковочных материалов. Подбор упаковки, доставка и консультация для бизнеса.'),
    'catalog': ('Каталог упаковочных материалов', 'Упаковочные материалы: категории, цены и характеристики. Выберите товары и оформите заказ.'),
    'team': ('Наша команда', 'Менеджеры, логисты и специалисты по упаковке. Познакомьтесь с командой и получите помощь в подборе материалов.'),
    'contacts': ('Контакты', 'Телефон, email, адрес и часы работы. Свяжитесь с нами или отправьте запрос на коммерческое предложение.'),
    'promotions': ('Акции', 'Действующие акции и специальные предложения на упаковочные материалы.'),
    'privacy': ('Политика конфиденциальности', 'Порядок обработки и защиты персональных данных посетителей сайта и покупателей.'),
    'offer': ('Публичная оферта', 'Условия заказа, оплаты и поставки упаковочных материалов. Информация для покупателей.'),
}


def absolute_url(request, settings, path):
    if path.startswith(('http://', 'https://')):
        return path
    origin = (settings.public_url or request.build_absolute_uri('/')).rstrip('/')
    return origin + '/' + path.lstrip('/')


def category_seo_defaults(request, settings, name, slug, description):
    canonical = absolute_url(request, settings, reverse("catalog") + "?" + urlencode({"category": slug})) if slug else ""
    return {"slug": slug, "h1": name, "seo_title": name, "meta_description": description.strip()[:320], "canonical": canonical}


def metadata(request, settings, pages, *, page_key=None):
    match = request.resolver_match
    key = page_key or (match.url_name if match else 'home')
    if key == 'document_page':
        key = match.kwargs.get('slug', 'privacy')
    if key in {'product_detail', 'api_products'}:
        key = 'catalog'
    record = pages.get(key)
    promotion = getattr(request, "_promotion", None)
    title, description = PAGE_DEFAULTS.get(key, (settings.site_name, settings.seo_description))
    canonical_path = PAGE_PATHS.get(key, request.path)
    if promotion:
        title = promotion.title
        description = promotion.description or PAGE_DEFAULTS["promotions"][1]
    if key in {"privacy", "offer"} and record and record.title:
        title = record.title
    if key == "custom_page" and record:
        title = record.title or title
        description = record.meta_description or record.subtitle or description
        canonical_path = reverse("custom_page", args=[record.slug])
    noindex = not settings.allow_indexing or bool(record and (record.noindex or record.requires_login))
    if key == 'home' and settings.seo_description:
        description = settings.seo_description
    category = None
    product = None
    if key == 'catalog':
        slug = match.kwargs.get('slug') if match and match.url_name == 'product_detail' else None
        product_id = request.GET.get('product', '')
        if slug:
            product = getattr(request, '_product_page', None)
            if product is None:
                product = Product.objects.filter(slug=slug, status='published', category_id__in=Category.visible_ids()).first()
            if getattr(request, '_product_preview', False):
                noindex = True
        elif product_id.isdigit():
            product = Product.objects.filter(pk=product_id, status='published', category_id__in=Category.visible_ids()).first()
        if product:
            record = product
            title = product.name
            description = product.description or f'{product.name}: цена, характеристики, минимальная партия и оформление заказа.'
            canonical_path = reverse('product_detail', args=[product.slug])
        elif request.GET.get('category'):
            category = Category.objects.filter(slug=request.GET['category'], pk__in=Category.visible_ids()).first()
            if category:
                record = category
                title = category.name
                description = category.description or f'{category.name}: ассортимент упаковочных материалов, цены и условия заказа.'
                canonical_path += '?' + urlencode({'category': category.slug})
        elif request.GET.get('hits') == '1':
            title = 'Хиты продаж'
            description = 'Популярные упаковочные материалы: цены, характеристики и заказ.'
            canonical_path += '?hits=1'
        has_catalog_modifiers = request.GET.get('q') or request.GET.get('sort') not in (None, '', 'default') or any(key.startswith('filter_') for key in request.GET)
        if has_catalog_modifiers:
            noindex = True
        if request.GET.get('q'):
            title = f'Поиск: {request.GET["q"][:100]}'
    seo_title = getattr(record, 'seo_title', '') or (title if category else f'{title} · {settings.site_name}')
    description = (getattr(record, 'meta_description', '') or description).strip()[:320]
    canonical = getattr(record, 'canonical', '') or absolute_url(request, settings, canonical_path)
    og_media = getattr(record, 'og_media', None) or settings.og_media
    image = og_media.file.url if og_media else (product.display_image_url if product else '')
    return {
        'title': seo_title, 'description': description, 'canonical': canonical,
        'og_title': getattr(record, 'og_title', '') or seo_title,
        'og_description': getattr(record, 'og_description', '') or description,
        'og_image': absolute_url(request, settings, image) if image else '',
        'noindex': noindex, 'h1': getattr(record, 'h1', '') or title,
    }
