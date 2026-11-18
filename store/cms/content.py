import json

from .common import ADDITION, AttributeDefinition, AttributeDefinitionForm, CHANGE, DELETION, PageContent, PageContentForm, ProductAttribute, SiteLinkFormSet, SiteMedia
from .common import SiteMediaForm, SiteSettings, SiteSettingsForm, delete_unreferenced_file, get_object_or_404, log_change, management_required, messages, redirect, render
from .common import require_POST, transaction
from django.http import HttpResponseBadRequest, JsonResponse

def media_usage(media):
    usage = []
    for relation in media._meta.related_objects:
        for obj in getattr(media, relation.get_accessor_name()).all():
            usage.append(f"{obj}: {relation.field.verbose_name}")
    for model, fields in [(SiteSettings, ["logo_image"]), (PageContent, ["hero_image"])]:
        for field in fields:
            for obj in model.objects.filter(**{field: media.file.name}):
                usage.append(f"{obj}: {model._meta.get_field(field).verbose_name}")
    return usage

@management_required
@require_POST
def page_content_delete(request, page_id):
    page = get_object_or_404(PageContent, pk=page_id)
    if not page.is_custom:
        messages.error(request, "Системные страницы нельзя удалить. Можно изменить их содержимое и видимость.")
        return redirect("management_pages")
    if page.children.exists():
        messages.error(request, "Сначала переместите или удалите вложенные страницы.")
        return redirect("management_pages")
    log_change(request, page, DELETION, "Текст страницы удалён")
    page.delete()
    messages.success(request, "Страница удалена.")
    return redirect("management_pages")

@management_required
@require_POST
def site_media_upload(request):
    form = SiteMediaForm(request.POST, request.FILES)
    if not form.is_valid():
        return media_library(request, form=form)
    media = form.save()
    log_change(request, media, ADDITION, "Медиафайл загружен")
    messages.success(request, "Файл загружен. Теперь его можно выбрать в настройках сайта или страницы.")
    return redirect("management_media")

@management_required
def field_list(request):
    fields = AttributeDefinition.objects.order_by("sort_order", "name")

    return render(
        request,
        "store/management/field_list.html",
        {
            "section": "fields",
            "fields": fields,
        },
    )

@management_required
@require_POST
def site_media_delete(request, media_id):
    media = get_object_or_404(SiteMedia, pk=media_id)
    usage = media_usage(media)
    if usage:
        messages.error(request, "Сначала уберите файл из мест использования: " + "; ".join(usage))
        return redirect("management_media")
    file_field = media.file
    with transaction.atomic():
        log_change(request, media, DELETION, "Неиспользуемый медиафайл удалён")
        media.delete()
        transaction.on_commit(lambda: file_field.delete(save=False))
    messages.success(request, "Неиспользуемый файл удалён.")
    return redirect("management_media")

@management_required
@require_POST
def field_delete(request, field_id):
    field = get_object_or_404(AttributeDefinition, pk=field_id)
    ProductAttribute.objects.filter(attribute=field).delete()
    log_change(request, field, DELETION, "Поле удалено через CMS")
    field.delete()
    messages.success(request, "Поле удалено.")
    return redirect("management_fields")

@management_required
def site_settings(request):
    settings = SiteSettings.get_solo()

    if request.method == "POST":
        form = SiteSettingsForm(request.POST, request.FILES, instance=settings)
        link_formset = SiteLinkFormSet(request.POST, instance=settings, prefix="links")
        old_logo_name = settings.logo_image.name
        old_logo_storage = settings.logo_image.storage
        if form.is_valid() and link_formset.is_valid():
            with transaction.atomic():
                settings = form.save()
                link_formset.save()
                if old_logo_name and old_logo_name != settings.logo_image.name:
                    delete_unreferenced_file(old_logo_name, old_logo_storage, settings.pk)
            log_change(request, settings, CHANGE, "Настройки сайта обновлены")
            messages.success(request, "Настройки сайта сохранены.")
            return redirect("management_settings")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = SiteSettingsForm(instance=settings)
        link_formset = SiteLinkFormSet(instance=settings, prefix="links")

    return render(
        request,
        "store/management/site_settings.html",
        {
            "section": "settings",
            "form": form,
            "link_formset": link_formset,
            "media_form": SiteMediaForm(),
        },
    )

@management_required
@require_POST
def site_media_replace(request, media_id):
    media = get_object_or_404(SiteMedia, pk=media_id)
    old_name = media.file.name
    storage = media.file.storage
    form = SiteMediaForm(request.POST, request.FILES, instance=media)
    if form.is_valid():
        with transaction.atomic():
            media = form.save()
            # Older direct image references continue to resolve after replacement.
            SiteSettings.objects.filter(logo_image=old_name).update(logo_image=media.file.name)
            PageContent.objects.filter(hero_image=old_name).update(hero_image=media.file.name)
            if old_name != media.file.name:
                transaction.on_commit(lambda: storage.delete(old_name))
            log_change(request, media, CHANGE, "Медиафайл и его описание обновлены")
        messages.success(request, "Файл обновлён во всех местах использования.")
    else:
        messages.error(request, " ".join(str(error) for errors in form.errors.values() for error in errors))
    return redirect("management_media")

@management_required
def media_library(request, form=None):
    rows = [{"item": media, "usage": media_usage(media)} for media in SiteMedia.objects.all()]
    return render(request, "store/management/media_library.html", {"section": "media", "media": rows, "media_form": form or SiteMediaForm()})

@management_required
def page_content_form(request, page_id=None):
    page = get_object_or_404(PageContent, pk=page_id) if page_id else None

    if request.method == "POST":
        form = PageContentForm(request.POST, request.FILES, instance=page)
        if form.is_valid():
            is_new = page is None
            page = form.save()
            log_change(request, page, ADDITION if is_new else CHANGE, "Страница сохранена через CMS")
            messages.success(request, "Страница сохранена.")
            return redirect("management_pages")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = PageContentForm(instance=page)

    preview_url = ""
    if page:
        if page.is_custom and page.slug:
            preview_url = f"/pages/{page.slug}/?preview=1"
        else:
            preview_url = {
                "home": "/",
                "catalog": "/catalog/",
                "team": "/team/",
                "contacts": "/contacts/",
                "promotions": "/promotions/",
                "privacy": "/documents/privacy/",
                "offer": "/documents/offer/",
            }.get(page.page, "")
    return render(
        request,
        "store/management/page_content_form.html",
        {
            "section": "pages",
            "page_content": page,
            "form": form,
            "preview_url": preview_url,
        },
    )

@management_required
def page_content_list(request):
    pages = list(PageContent.objects.select_related("parent").order_by("sort_order", "page"))
    children = {}
    for page in pages:
        page.tree_url = (
            f"/pages/{page.slug}/"
            if page.is_custom and page.slug
            else {
                "home": "/",
                "catalog": "/catalog/",
                "team": "/team/",
                "contacts": "/contacts/",
                "promotions": "/promotions/",
                "privacy": "/documents/privacy/",
                "offer": "/documents/offer/",
            }.get(page.page, "")
        )
        page.display_name = page.title or page.get_page_display()
        page.is_protected = not page.is_custom
        children.setdefault(page.parent_id, []).append(page)

    def build_tree(parent_id=None, ancestors=frozenset()):
        nodes = []
        for page in children.get(parent_id, []):
            if page.pk in ancestors:
                continue
            page.tree_children = build_tree(parent_id=page.pk, ancestors=ancestors | {page.pk})
            nodes.append(page)
        return nodes

    query = request.GET.get("q", "").strip()
    tree = build_tree()

    return render(
        request,
        "store/management/page_content_list.html",
        {
            "section": "pages",
            "page_tree": tree,
            "page_count": len(pages),
            "query": query,
        },
    )

@management_required
@require_POST
def page_content_reorder(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Некорректный JSON.")
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        return HttpResponseBadRequest("Ожидался список страниц.")

    try:
        items = [
            (
                int(item["id"]),
                int(item["parent_id"]) if item.get("parent_id") is not None else None,
                int(item.get("order", order)),
            )
            for order, item in enumerate(payload["items"])
        ]
    except (KeyError, TypeError, ValueError):
        return HttpResponseBadRequest("Некорректные данные порядка страниц.")

    page_ids = {page_id for page_id, _, _ in items}
    existing_ids = set(PageContent.objects.values_list("pk", flat=True))
    if len(page_ids) != len(items) or page_ids != existing_ids:
        return HttpResponseBadRequest("Обновите список страниц и повторите изменение.")

    parent_by_id = {page_id: parent_id for page_id, parent_id, _ in items}
    if any(parent_id is not None and parent_id not in page_ids for parent_id in parent_by_id.values()):
        return HttpResponseBadRequest("Родительская страница не найдена.")
    for page_id, parent_id, order in items:
        if order < 0:
            return HttpResponseBadRequest("Порядок страницы не может быть отрицательным.")
    for page_id in page_ids:
        visited = set()
        current_id = page_id
        while current_id is not None:
            if current_id in visited:
                return HttpResponseBadRequest("Циклическая вложенность страниц запрещена.")
            visited.add(current_id)
            current_id = parent_by_id.get(current_id)

    with transaction.atomic():
        for page_id, parent_id, order in items:
            PageContent.objects.filter(pk=page_id).update(parent_id=parent_id, sort_order=order)
        if items:
            page = PageContent.objects.get(pk=items[0][0])
            log_change(request, page, CHANGE, "Порядок и вложенность страниц обновлены")
    return JsonResponse({"saved": True})

@management_required
def field_form(request, field_id=None):
    field = get_object_or_404(AttributeDefinition, pk=field_id) if field_id else None

    if request.method == "POST":
        form = AttributeDefinitionForm(request.POST, instance=field)
        if form.is_valid():
            field = form.save()
            log_change(request, field, ADDITION if field_id is None else CHANGE, "Поле сохранено через CMS")
            messages.success(request, "Поле сохранено.")
            return redirect("management_fields")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = AttributeDefinitionForm(instance=field)

    return render(
        request,
        "store/management/field_form.html",
        {
            "section": "fields",
            "field": field,
            "form": form,
        },
    )
