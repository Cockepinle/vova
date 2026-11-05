from .common import ADDITION, AttributeDefinition, AttributeDefinitionForm, CHANGE, DELETION, PageContent, PageContentForm, ProductAttribute, SiteLinkFormSet, SiteMedia
from .common import SiteMediaForm, SiteSettings, SiteSettingsForm, delete_unreferenced_file, get_object_or_404, log_change, management_required, messages, redirect, render
from .common import require_POST, transaction

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
    log_change(request, page, DELETION, "Текст страницы удалён")
    page.delete()
    messages.success(request, "Текст страницы удалён.")
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
            log_change(request, page, ADDITION if is_new else CHANGE, "Текст страницы сохранён")
            messages.success(request, "Текст страницы сохранён.")
            return redirect("management_pages")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = PageContentForm(instance=page)

    return render(
        request,
        "store/management/page_content_form.html",
        {
            "section": "pages",
            "page_content": page,
            "form": form,
        },
    )

@management_required
def page_content_list(request):
    pages = PageContent.objects.order_by("page")

    return render(
        request,
        "store/management/page_content_list.html",
        {
            "section": "pages",
            "pages": pages,
        },
    )

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
