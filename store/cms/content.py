import copy
import html
import json
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit
from uuid import uuid4

from django.db import IntegrityError
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils.encoding import filepath_to_uri

from ..models import Category, Employee, Product, ProductAttribute, ProductImage
from ..uploads import MediaProviderError, MediaStorageUnavailable, local_media_missing
from .common import ADDITION, AttributeDefinition, AttributeDefinitionForm, BuilderRevision, CHANGE, DELETION, PageContent, PageContentForm, SiteLinkFormSet, SiteMedia
from .common import SiteMediaForm, SiteSettings, SiteSettingsForm, delete_unreferenced_file, get_object_or_404, log_change, management_required, messages, redirect, render
from .common import require_POST, transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.urls import reverse
from django.views.csrf import csrf_failure
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


MEDIA_REFERENCE_FIELDS = (
    (SiteSettings, ("logo_image",)), (PageContent, ("hero_image",)),
    (Category, ("image", "image_url")), (Product, ("image", "image_url")),
    (ProductImage, ("image", "image_url")),
    (Employee, ("image", "image_url")),
    (ProductAttribute, ("value_file", "value_url")),
)


def media_reference_urls(file):
    url = file.url
    storage = file.storage
    if getattr(storage, "is_local_name", lambda name: True)(file.name):
        return (url, f"/media/{filepath_to_uri(file.name)}")
    return (url,)


def media_usage(media):
    usage = []
    for relation in media._meta.related_objects:
        related = getattr(media, relation.get_accessor_name()).all()
        if relation.related_model is ProductImage:
            usage.extend(f"{image.product.name}: фотография товара" for image in related.select_related("product"))
        else:
            usage.extend(f"{obj}: {relation.field.verbose_name}" for obj in related)
    if not media.file:
        return usage
    media_urls = media_reference_urls(media.file)
    for model, fields in MEDIA_REFERENCE_FIELDS:
        for field in fields:
            lookup = {f"{field}__in": media_urls} if field.endswith("_url") else {field: media.file.name}
            for obj in model.objects.filter(**lookup):
                usage.append(f"{obj}: {model._meta.get_field(field).verbose_name}")

    def structure_uses_media(nodes):
        if not isinstance(nodes, list):
            return False
        for node in nodes:
            if not isinstance(node, dict):
                continue
            content = node.get("content", {})
            if isinstance(content, dict) and (
                str(content.get("media_id", "")) == str(media.pk)
                or content.get("url") in media_urls or content.get("src") in media_urls
            ):
                return True
            if structure_uses_media(node.get("children")):
                return True
        return False

    for page in PageContent.objects.only("pk", "title", "page", "draft_structure", "published_structure"):
        if structure_uses_media(page.draft_structure) or structure_uses_media(page.published_structure):
            usage.append(f"{page}: Изображение блока страницы")
    return usage


def _replace_builder_media_urls(structure, media, old_urls, new_url):
    changed = False
    if not isinstance(structure, list):
        return changed
    for node in structure:
        if not isinstance(node, dict):
            continue
        content = node.get("content")
        if isinstance(content, dict) and (
            str(content.get("media_id", "")) == str(media.pk)
            or content.get("url") in old_urls or content.get("src") in old_urls
        ):
            key = "src" if node.get("type") == "banner" and "src" in content else "url"
            content[key] = new_url
            content["media_id"] = media.pk
            content["alt"] = media.alt
            changed = True
        if _replace_builder_media_urls(node.get("children"), media, old_urls, new_url):
            changed = True
    return changed


def update_builder_media_references(media, old_url, *, old_urls=None):
    old_urls = tuple(old_urls or [old_url])
    new_url = media.file.url
    for page in PageContent.objects.only("pk", "draft_structure", "published_structure"):
        changed_fields = []
        for field in ("draft_structure", "published_structure"):
            structure = getattr(page, field)
            if _replace_builder_media_urls(structure, media, old_urls, new_url):
                setattr(page, field, structure)
                changed_fields.append(field)
        if changed_fields:
            page.save(update_fields=[*changed_fields, "updated_at"])

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


def management_csrf_failure(request, reason=""):
    if request.path == reverse("management_media_upload_api"):
        logger.warning("Media upload CSRF check failed: %s", reason)
        response = media_access_error(request)
        if response is not None:
            return response
        return JsonResponse({"error": "Не удалось подтвердить сессию. Обновите страницу и повторите загрузку."}, status=403)
    return csrf_failure(request, reason=reason)


def media_access_error(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Срок действия сессии истёк. Войдите в систему повторно"}, status=401)
    if not request.user.is_staff:
        return JsonResponse({"error": "Недостаточно прав для загрузки файла"}, status=403)
    return None


@management_required
@require_POST
def site_media_upload(request):
    form = SiteMediaForm(request.POST, request.FILES)
    if not form.is_valid():
        return media_library(request, form=form)
    try:
        with transaction.atomic():
            media = form.save()
    except MediaStorageUnavailable:
        logger.exception("Persistent media storage is not configured")
        form.add_error("file", "На сервере не настроено постоянное хранилище файлов.")
        return media_library(request, form=form)
    except MediaProviderError as error:
        logger.warning("Cloudinary media upload failed: %s", type(error.__cause__).__name__)
        form.add_error("file", error.public_message)
        return media_library(request, form=form)
    except IntegrityError:
        logger.exception("Database rejected the media library record")
        form.add_error("file", "Файл принят, но запись медиатеки не удалось сохранить в базе данных.")
        return media_library(request, form=form)
    except (OSError, ValueError):
        logger.exception("Could not store media uploaded from library")
        form.add_error("file", "Не удалось сохранить файл на сервере")
        return media_library(request, form=form)
    log_change(request, media, ADDITION, "Медиафайл загружен")
    messages.success(request, "Файл загружен в медиатеку.")
    return redirect("management_media")

@management_required
def media_library_api(request):
    kind = request.GET.get("kind") or "image"
    if kind not in {"image", "attachment", "all"}:
        return JsonResponse({"error": "Неизвестный тип файлов."}, status=400)
    items = []
    files = SiteMedia.objects.order_by("-created_at", "-pk")
    if kind == "image":
        files = files.filter(media_type=SiteMedia.TYPE_IMAGE)
    for media in files:
        if kind == "image" and not media.is_image:
            continue
        if kind == "attachment" and media.is_image:
            continue
        try:
            if not media.file:
                continue
            if local_media_missing(media.file):
                continue
            items.append({
                "id": media.pk,
                "title": media.title,
                "filename": media.filename,
                "alt": media.alt,
                "url": media.file.url,
                "type": media.media_type,
            })
        except (OSError, ValueError):
            continue
    return JsonResponse({"items": items})

@require_POST
def media_library_upload_api(request):
    forbidden = media_access_error(request)
    if forbidden is not None:
        return forbidden
    kind = request.POST.get("kind") or "all"
    if request.POST.get("images_only") == "1":
        kind = "image"
    if kind not in {"image", "attachment", "all"}:
        return JsonResponse({"error": "Неизвестный тип файлов."}, status=400)
    form = SiteMediaForm(request.POST, request.FILES, upload_kind=kind)
    if not form.is_valid():
        error = "; ".join(str(error) for errors in form.errors.values() for error in errors)
        return JsonResponse({"error": error or "Проверьте данные файла."}, status=400)
    media = form.save(commit=False)
    try:
        with transaction.atomic():
            media.save()
    except MediaStorageUnavailable:
        logger.exception("Persistent media storage is not configured")
        return JsonResponse({"error": "На сервере не настроено постоянное хранилище файлов."}, status=503)
    except MediaProviderError as error:
        logger.warning("Cloudinary picker upload failed: %s", type(error.__cause__).__name__)
        return JsonResponse({"error": error.public_message}, status=503)
    except IntegrityError:
        logger.exception("Database rejected the media library record")
        return JsonResponse({"error": "Файл принят, но запись медиатеки не удалось сохранить в базе данных."}, status=503)
    except (OSError, ValueError):
        logger.exception("Could not store media uploaded from picker")
        return JsonResponse({"error": "Не удалось сохранить файл на сервере"}, status=503)
    log_change(request, media, ADDITION, "Медиафайл загружен через выборщик")
    result = {
        "id": media.pk,
        "title": media.title,
        "filename": media.filename,
        "alt": media.alt,
        "url": media.file.url,
        "type": media.media_type,
    }
    if request.POST.get("library") == "1":
        result["html"] = render_to_string(
            "store/management/media_library_item.html",
            {"row": media_library_row(media, usage=[])}, request=request,
        )
    return JsonResponse(result)

@management_required
def field_list(request):
    fields = AttributeDefinition.objects.annotate(value_count=Count("product_values")).order_by("sort_order", "name")

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
    try:
        with transaction.atomic():
            media = get_object_or_404(SiteMedia.objects.select_for_update(), pk=media_id)
            usage = media_usage(media)
            if usage:
                messages.error(request, "Файл используется. Сначала уберите его из перечисленных мест: " + "; ".join(usage))
                return redirect("management_media")
            file_field = media.file
            log_change(request, media, DELETION, "Неиспользуемый медиафайл удалён")
            media.delete()
            if file_field:
                transaction.on_commit(lambda: delete_unreferenced_file(file_field.name, file_field.storage), robust=True)
    except IntegrityError:
        messages.error(request, "Файл используется и не может быть удалён.")
    else:
        messages.success(request, "Файл удалён из медиатеки.")
    return redirect("management_media")

@management_required
@require_POST
@transaction.atomic
def field_delete(request, field_id):
    field = get_object_or_404(AttributeDefinition.objects.select_for_update(), pk=field_id)
    ProductAttribute.objects.filter(attribute=field).delete()
    log_change(request, field, DELETION, "Поле удалено через CMS")
    field.delete()
    messages.success(request, "Поле и его значения удалены. Карточки товаров сохранены.")
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
            try:
                with transaction.atomic():
                    settings = form.save()
                    link_formset.save()
                    if old_logo_name and old_logo_name != settings.logo_image.name:
                        transaction.on_commit(
                            lambda: delete_unreferenced_file(old_logo_name, old_logo_storage, settings.pk),
                            robust=True,
                        )
            except OSError:
                form.add_error("logo_image", "Не удалось записать логотип. Повторите загрузку позже.")
            else:
                log_change(request, settings, CHANGE, "Настройки сайта обновлены")
                messages.success(request, "Настройки сайта сохранены.")
                return redirect(request.path + ("?tab=brand" if request.GET.get("tab") == "brand" else ""))
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = SiteSettingsForm(instance=settings)
        link_formset = SiteLinkFormSet(instance=settings, prefix="links")

    return render(
        request,
        "store/management/site_settings.html",
        {
            "section": "settings",
            "content_section": "brand" if request.GET.get("tab") == "brand" else "settings",
            "form": form,
            "link_formset": link_formset,
            "media_form": SiteMediaForm(),
        },
    )

@management_required
@require_POST
@transaction.atomic
def site_media_replace(request, media_id):
    media = get_object_or_404(SiteMedia.objects.select_for_update(), pk=media_id)
    old_name = media.file.name
    old_url = media.file.url if old_name else ""
    old_urls = media_reference_urls(media.file) if old_name else set()
    storage = media.file.storage
    upload = request.FILES.get("file")
    form = SiteMediaForm(request.POST, request.FILES, instance=media, auto_id=f"replace_{media_id}_%s")
    if upload and media.is_image and not SiteMedia(file=upload).is_image and media_usage(media):
        form.add_error("file", "Изображение используется на сайте. Для замены выберите другое изображение.")
    if form.is_valid():
        try:
            with transaction.atomic():
                media = form.save()
                if old_name and old_name != media.file.name:
                    for model, fields in MEDIA_REFERENCE_FIELDS:
                        for field in fields:
                            if field.endswith("_url"):
                                model.objects.filter(**{f"{field}__in": old_urls}).update(**{field: media.file.url})
                            else:
                                model.objects.filter(**{field: old_name}).update(**{field: media.file.name})
                    transaction.on_commit(lambda: delete_unreferenced_file(old_name, storage), robust=True)
                if old_url and media.file:
                    update_builder_media_references(media, old_url, old_urls=old_urls)
                log_change(request, media, CHANGE, "Медиафайл и его описание обновлены")
        except OSError:
            form.add_error("file", "Не удалось записать файл. Повторите загрузку позже.")
        else:
            messages.success(request, "Файл обновлён во всех местах использования.")
            return redirect("management_media")
    return media_library(request, replacement_form=form)

def media_library_row(media, *, form=None, usage=None):
    missing = not media.file or local_media_missing(media.file)
    return {
        "item": media, "url": media.file.url if not missing else "", "missing": missing,
        "usage": media_usage(media) if usage is None else usage,
        "form": form if form is not None else SiteMediaForm(instance=media, auto_id=f"replace_{media.pk}_%s"),
    }


@management_required
def media_library(request, form=None, replacement_form=None):
    rows = [
        media_library_row(media, form=replacement_form if replacement_form is not None and
                          replacement_form.instance.pk == media.pk else None)
        for media in SiteMedia.objects.all()
    ]
    return render(request, "store/management/media_library.html", {"section": "media", "media": rows, "media_form": form or SiteMediaForm()})

@management_required
def page_content_form(request, page_id=None):
    page = get_object_or_404(PageContent, pk=page_id) if page_id else None

    document_preview = None
    is_document = page and not page.is_custom and page.page in {"privacy", "offer"}
    if is_document:
        from ..views.catalog import default_document

        original_document = render_to_string("store/partials/document_text.html", {
            "document": default_document(page.page),
            "current_page": page,
        }).strip()
    tabs = {
        "texts": ("Тексты страниц", ("title", "h1", "content_title", "content_subtitle", "content_text", "b2b_title")),
        "banners": ("Баннеры", ("hero_label", "subtitle", "hero_button_text", "hero_button_url")),
        "images": ("Изображения страниц", ("hero_media", "mobile_hero_media", "hero_image_alt")),
        "properties": ("Свойства и доступ", ("page_type", "page", "slug", "parent", "sort_order", "is_visible", "requires_login")),
        "seo": ("SEO", ("seo_title", "meta_description", "canonical", "og_title", "og_description", "og_media", "noindex")),
    }
    if is_document:
        tabs["texts"] = ("Юридический текст", ("title", "h1", "document_html"))
    tab = request.GET.get("tab") or ("texts" if page else "properties")
    if tab not in tabs:
        tab = "texts"

    if request.method == "POST":
        form = PageContentForm(request.POST, request.FILES, instance=page)
        if is_document and request.POST.get("preview_document"):
            if form.is_valid():
                document_preview = _sanitize_html(form.cleaned_data["document_html"], limit=40000) or original_document
        elif form.is_valid():
            is_new = page is None
            try:
                if is_document and "document_html" in request.POST:
                    source = form.cleaned_data["document_html"].replace("\r\n", "\n")
                    form.instance.document_html = (
                        _sanitize_html(source, limit=40000) if source != original_document else ""
                    )
                page = form.save()
            except OSError:
                form.add_error("hero_image", "Не удалось записать изображение. Повторите загрузку позже.")
            else:
                log_change(request, page, ADDITION if is_new else CHANGE, "Страница сохранена через CMS")
                messages.success(request, "Страница сохранена.")
                return redirect(f"{request.path}?tab={tab}" if not is_new else reverse("management_page_edit", args=[page.pk]))
        if form.errors:
            messages.error(request, "Проверьте ошибки в форме.")
    else:
        if is_document:
            initial = {"document_html": page.document_html or original_document}
        else:
            initial = {"page": request.GET["page"]} if page is None and request.GET.get("page") in {"privacy", "offer"} else None
        form = PageContentForm(instance=page, initial=initial)

    return render(request, "store/management/page_content_form.html", {
        "section": "pages", "content_section": tab if tab in {"texts", "images", "banners"} else "texts",
        "page_content": page, "form": form, "active_tab": tab,
        "tabs": [(key, label, [form[name] for name in fields]) for key, (label, fields) in tabs.items()],
        "preview_url": _page_preview_url(page) if page else "",
        "is_document": is_document, "document_preview": document_preview,
    })


@management_required
def page_content_list(request):
    pages = list(PageContent.objects.select_related("parent").order_by("sort_order", "page"))
    documents = {page.page: page for page in pages if not page.is_custom and page.page in {"privacy", "offer"}}
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
    sections = {"texts": "Тексты страниц", "banners": "Баннеры", "images": "Изображения страниц",
                "blocks": "Информационные блоки"}
    content_section = request.GET.get("section", "texts")
    if content_section not in sections:
        content_section = "texts"

    return render(
        request,
        "store/management/page_content_list.html",
        {
            "section": "pages",
            "content_section": content_section,
            "content_title": sections[content_section],
            "document_links": [(slug, label, documents.get(slug)) for slug, label in PageContent.PAGE_CHOICES if slug in {"privacy", "offer"}],
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


BUILDER_TYPES = {
    "section", "container", "columns", "text", "heading", "image", "button",
    "icon", "link", "banner", "slider", "video", "gallery", "products",
    "category", "form", "advantages", "faq", "html", "divider",
}

SAFE_CSS_PROPERTIES = {
    "color", "background-color", "font-family", "font-size", "font-weight",
    "line-height", "text-align", "padding", "padding-top", "padding-right",
    "padding-bottom", "padding-left", "margin", "margin-top", "margin-right",
    "margin-bottom", "margin-left", "width", "height", "min-height", "max-width",
    "border", "border-radius", "box-shadow", "opacity", "display",
    "align-items", "justify-content", "grid-template-columns", "gap",
}

CSS_VALUE_RE = re.compile(r"^[^;<>{}]{0,180}$")


def _safe_builder_url(value, *, image=False):
    value = str(value or "").strip()
    if not value or "\\" in value or any(ord(char) < 32 for char in value):
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if value.startswith("/") and not value.startswith("//"):
        return value
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    if not image and (value.startswith("#") or (parsed.scheme in {"mailto", "tel"} and parsed.path)):
        return value
    return ""


class _BuilderHTMLSanitizer(HTMLParser):
    allowed_tags = {
        "a", "b", "blockquote", "br", "div", "em", "h2", "h3", "h4",
        "i", "li", "ol", "p", "span", "strong", "u", "ul",
    }
    void_tags = {"br"}
    blocked_tags = {"embed", "form", "iframe", "math", "object", "script", "style", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.open_tags = []
        self.blocked = []

    def handle_starttag(self, tag, attrs):
        if self.blocked:
            if tag in self.blocked_tags:
                self.blocked.append(tag)
            return
        if tag in self.blocked_tags:
            self.blocked.append(tag)
            return
        if tag not in self.allowed_tags:
            return
        safe_attrs = []
        if tag == "a":
            attributes = dict(attrs)
            href = _safe_builder_url(attributes.get("href"))
            if href:
                safe_attrs.append(f'href="{html.escape(href, quote=True)}"')
            title = attributes.get("title")
            if title:
                safe_attrs.append(f'title="{html.escape(title[:180], quote=True)}"')
        attrs_text = " " + " ".join(safe_attrs) if safe_attrs else ""
        self.output.append(f"<{tag}{attrs_text}>")
        if tag not in self.void_tags:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in self.allowed_tags and tag not in self.void_tags:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked[-1]:
                self.blocked.pop()
            return
        if tag in self.void_tags:
            return
        if tag not in self.open_tags:
            return
        while self.open_tags:
            open_tag = self.open_tags.pop()
            self.output.append(f"</{open_tag}>")
            if open_tag == tag:
                break

    def handle_data(self, data):
        if not self.blocked:
            self.output.append(html.escape(data))

    def get_html(self):
        while self.open_tags:
            self.output.append(f"</{self.open_tags.pop()}>")
        return "".join(self.output)


def _sanitize_css(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, css_value in value.items():
        key = str(key).strip().lower()
        if key in SAFE_CSS_PROPERTIES:
            css_value = str(css_value).strip()
            if CSS_VALUE_RE.fullmatch(css_value):
                result[key] = css_value
    return result


def _sanitize_html(value, *, limit=10000):
    parser = _BuilderHTMLSanitizer()
    parser.feed(str(value or "")[:limit])
    parser.close()
    return parser.get_html()


def sanitize_builder_structure(raw, depth=0, budget=None, used_ids=None):
    if budget is None:
        budget = [300]
    if used_ids is None:
        used_ids = set()
    if depth > 6 or not isinstance(raw, list) or budget[0] <= 0:
        return []
    result = []
    for index, item in enumerate(raw):
        if budget[0] <= 0:
            break
        budget[0] -= 1
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type", "")).strip().lower()
        if kind not in BUILDER_TYPES:
            continue
        base_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(item.get("id", "")))[:80] or f"block-{index}"
        element_id = base_id
        suffix = 1
        while element_id in used_ids:
            element_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(element_id)
        content = item.get("content", {})
        if not isinstance(content, dict):
            content = {}
        safe_content = {}
        for key, value in content.items():
            key = re.sub(r"[^a-zA-Z0-9_-]", "", str(key))[:40]
            if not key:
                continue
            if isinstance(value, str):
                if key == "html":
                    safe_content[key] = _sanitize_html(value)
                elif key in {"url", "href", "src"}:
                    safe_content[key] = _safe_builder_url(value, image=kind == "image" or key == "src")
                else:
                    safe_content[key] = value[:10000]
            elif isinstance(value, (int, float, bool)):
                safe_content[key] = value
        styles = _sanitize_css(item.get("styles", {}))
        responsive = item.get("responsive", {})
        if not isinstance(responsive, dict):
            responsive = {}
        css_parts = [f"{key}:{value}" for key, value in styles.items()]
        node = {
            "id": element_id,
            "type": kind,
            "content": safe_content,
            "styles": styles,
            "responsive": {
                "hidden_mobile": bool(responsive.get("hidden_mobile")),
                "hidden_tablet": bool(responsive.get("hidden_tablet")),
            },
            "style_css": ";".join(css_parts),
        }
        if "children" in item:
            node["children"] = sanitize_builder_structure(item.get("children"), depth + 1, budget, used_ids)
        result.append(node)
    return result


BLOCK_LABELS = dict(zip(
    ("heading", "text", "image", "button", "banner", "slider", "video", "gallery",
     "products", "category", "form", "advantages", "faq", "html", "divider",
     "container", "columns", "section", "link", "icon"),
    ("Заголовок", "Текст", "Изображение", "Кнопка", "Баннер", "Слайдер", "Видео", "Галерея",
     "Товары", "Категории", "Форма", "Преимущества", "Вопросы и ответы", "HTML", "Разделитель",
     "Контейнер", "Колонки", "Секция", "Ссылка", "Иконка"),
))
BLOCK_GROUPS = {"section", "container", "columns", "banner"}
CREATABLE_BLOCKS = BLOCK_GROUPS | {"heading", "text", "image", "button", "video", "html", "divider", "link"}
PLACEHOLDER_BLOCKS = {"slider", "gallery", "products", "category", "form", "advantages", "faq"}
BLOCK_STYLES = {
    "color": "Цвет текста", "background-color": "Цвет фона", "font-size": "Размер шрифта",
    "font-weight": "Начертание", "text-align": "Выравнивание", "padding": "Внутренний отступ",
    "margin": "Внешний отступ", "min-height": "Минимальная высота",
    "border-radius": "Скругление", "opacity": "Прозрачность (от 0 до 1)",
}
BLOCK_FIELDS = {
    "heading": ("text", "level"), "image": ("url", "alt"), "html": ("html",),
    "button": ("text", "url"), "link": ("text", "url"), "video": ("text", "url"),
    "banner": ("text", "src", "alt"), "divider": (),
    **dict.fromkeys(PLACEHOLDER_BLOCKS, ()),
}
BLOCK_FIELD_LABELS = {"text": "Текст", "level": "Уровень заголовка", "url": "Адрес",
                      "alt": "Описание изображения", "html": "HTML-код", "src": "Адрес изображения"}


def _block_rows(nodes, prefix="", depth=0):
    if not isinstance(nodes, list):
        return
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        path = f"{prefix}.{index}" if prefix else str(index)
        kind = node.get("type")
        content = node.get("content") or {}
        teaser = (content.get("text") or content.get("alt") or "") if isinstance(content, dict) else ""
        yield {
            "path": path, "depth": depth, "node": node, "siblings": nodes, "index": index,
            "label": BLOCK_LABELS.get(kind, kind or "Блок"), "teaser": teaser,
            "up": index > 0, "down": index + 1 < len(nodes),
        }
        yield from _block_rows(node.get("children"), path, depth + 1)


def _block_update(node, data):
    kind = node.get("type")
    content = node.get("content")
    if not isinstance(content, dict):
        content = {}
    changes = {
        key: data[f"content-{key}"].strip()
        for key in BLOCK_FIELDS.get(kind, ("text",))
        if f"content-{key}" in data and data[f"content-{key}"].strip() != str(content.get(key) or "")
    }
    image_key = {"image": "url", "banner": "src"}.get(kind)
    if image_key and data.get("replace-image"):
        media_id = data["replace-image"]
        media = SiteMedia.objects.filter(pk=media_id, media_type=SiteMedia.TYPE_IMAGE).first() if media_id.isdecimal() and len(media_id) < 19 else None
        if not media or not media.file:
            raise ValueError("Выберите доступное изображение из медиатеки.")
        content["media_id"] = media.pk
        changes[image_key] = media.file.url
    elif image_key and image_key in changes:
        content.pop("media_id", None)
    if changes:
        normalized = sanitize_builder_structure([{"type": kind, "content": changes}])[0]["content"]
        if any(changes.get(key) and not normalized.get(key) for key in ("url", "href", "src")):
            raise ValueError("Укажите полный HTTP(S)-адрес или путь, начинающийся с /.")
        content.update(normalized)
        node["content"] = content

    styles = node.get("styles") or {}
    if isinstance(styles, dict):
        style_edits = {key: data[f"style-{key}"].strip() for key in BLOCK_STYLES
                       if f"style-{key}" in data and data[f"style-{key}"].strip() != str(styles.get(key) or "")}
        if style_edits:
            validated = _sanitize_css(style_edits)
            if validated.keys() != style_edits.keys():
                raise ValueError("Проверьте значения параметров оформления.")
            for key, value in validated.items():
                if value:
                    styles[key] = value
                else:
                    styles.pop(key, None)
            node["styles"] = styles
            stored_css = node.get("style_css")
            if isinstance(stored_css, str):
                untouched = [part for part in stored_css.split(";")
                             if part and part.partition(":")[0].strip().lower() not in validated]
                edited = [f"{key}:{value}" for key, value in validated.items() if value]
                node["style_css"] = ";".join([*untouched, *edited])
            else:
                node["style_css"] = ";".join(f"{key}:{value}" for key, value in _sanitize_css(styles).items())
    if "visibility-fields" in data:
        responsive = node.get("responsive")
        if not isinstance(responsive, dict):
            responsive = {}
        for key in ("hidden_mobile", "hidden_tablet"):
            checked = key in data
            if checked != bool(node.get(f"public_{key}")):
                responsive[key] = checked
                node[f"public_{key}"] = checked
        if responsive:
            node["responsive"] = responsive


def _block_action(structure, rows, data):
    action = data.get("action")
    row = rows.get(data.get("block"))
    if action == "add":
        kind = data.get("kind")
        if kind not in CREATABLE_BLOCKS or len(rows) >= 300:
            raise ValueError("Проверьте тип блока. На странице допускается до 300 блоков.")
        target = structure
        if row:
            if row["node"].get("type") not in BLOCK_GROUPS or row["depth"] >= 6:
                raise ValueError("Этот блок не поддерживает вложенные элементы.")
            target = row["node"].setdefault("children", [])
            if not isinstance(target, list):
                raise ValueError("У этого блока нестандартная структура вложенности.")
        new = {"id": f"block-{uuid4().hex}", "type": kind, "content": {}}
        target.append(new)
        return next(item["path"] for item in _block_rows(structure) if item["node"] is new)
    if not row:
        raise ValueError("Блок не найден. Обновите страницу и повторите действие.")
    siblings, index, node = row["siblings"], row["index"], row["node"]
    if action == "edit" and node.get("type") in BLOCK_LABELS:
        _block_update(node, data)
        return row["path"]
    if action == "move":
        destination = data.get("destination")
        parent = rows.get(destination)
        if destination and (not parent or parent["node"].get("type") not in BLOCK_GROUPS
                            or destination == row["path"] or destination.startswith(row["path"] + ".")):
            raise ValueError("Выберите допустимый родительский блок.")
        target = parent["node"].setdefault("children", []) if parent else structure
        height = max((child["depth"] for child in _block_rows([node])), default=0)
        if not isinstance(target, list) or (parent and parent["depth"] + height >= 6):
            raise ValueError("Превышена допустимая вложенность блоков.")
        siblings.pop(index)
        target.append(node)
    elif action == "delete":
        siblings.pop(index)
    elif action == "duplicate":
        duplicate = copy.deepcopy(node)
        descendants = list(_block_rows([duplicate]))
        if len(rows) + len(descendants) > 300:
            raise ValueError("На странице допускается до 300 блоков.")
        for child in descendants:
            child["node"]["id"] = f"block-{uuid4().hex}"
        siblings.insert(index + 1, duplicate)
    elif action in {"up", "down"} and row[action]:
        other = index + (-1 if action == "up" else 1)
        siblings[other], siblings[index] = siblings[index], siblings[other]
    else:
        raise ValueError("Действие недоступно для выбранного блока.")
    return ""


def _page_preview_url(page):
    if page.is_custom and page.slug:
        return reverse("custom_page", args=[page.slug]) + "?preview=1"
    return {"home": "/", "catalog": "/catalog/", "team": "/team/", "contacts": "/contacts/",
            "promotions": "/promotions/", "privacy": "/documents/privacy/",
            "offer": "/documents/offer/"}.get(page.page, "")


def _working_blocks(page):
    if page.draft_structure or page.draft_design or page.builder_revisions.exists():
        return page.draft_structure, page.draft_design
    return page.published_structure, page.published_design


@management_required
@require_http_methods(["GET", "POST"])
def page_builder(request, page_id):
    url = reverse("management_page_blocks", args=[page_id])
    if request.path != url:
        return redirect(url)
    if request.method == "POST":
        try:
            with transaction.atomic():
                page = get_object_or_404(PageContent.objects.select_for_update(), pk=page_id)
                if request.POST.get("version") != page.updated_at.isoformat():
                    raise ValueError("Страница уже изменена. Повторите действие с актуальной версией.")
                structure, design = _working_blocks(page)
                action = request.POST.get("action")
                selected = ""
                fields = ["draft_structure", "draft_design", "updated_at"]
                if page.published_structure and not page.builder_revisions.exists():
                    BuilderRevision.objects.create(
                        page=page, structure=copy.deepcopy(page.published_structure),
                        design=copy.deepcopy(page.published_design), label="Исходная опубликованная версия",
                        created_by=request.user,
                    )
                if action == "restore":
                    revision_id = request.POST.get("revision", "")
                    if not revision_id.isdecimal() or len(revision_id) >= 19:
                        raise ValueError("Выберите версию для восстановления.")
                    revision = get_object_or_404(page.builder_revisions, pk=revision_id)
                    structure, design = revision.structure, revision.design
                elif action == "publish":
                    if page.page in {"privacy", "offer"}:
                        design = {**(design or {}), "document_blocks": True}
                    page.published_structure = copy.deepcopy(structure)
                    page.published_design = copy.deepcopy(design)
                    fields.extend(["published_structure", "published_design"])
                else:
                    rows = {row["path"]: row for row in _block_rows(structure)}
                    if action == "add" and not structure and not page.published_structure:
                        design = {**(design or {}), "append_to_page": True}
                    selected = _block_action(structure, rows, request.POST)
                page.draft_structure, page.draft_design = structure, design
                page.save(update_fields=fields)
                label = {"publish": "Опубликованная версия", "restore": "Восстановленная версия"}.get(action, "Черновик")
                BuilderRevision.objects.create(page=page, structure=structure, design=design,
                                               label=label, created_by=request.user)
                log_change(request, page, CHANGE, label)
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Блоки опубликованы." if action == "publish" else "Черновик сохранён.")
            if selected:
                url += f"?block={selected}"
        return redirect(url)

    page = get_object_or_404(PageContent, pk=page_id)
    structure, design = _working_blocks(page)
    rows = {row["path"]: row for row in _block_rows(structure)}
    selected = rows.get(request.GET.get("block"))
    kind = selected["node"].get("type") if selected else None
    move_targets = [
        row for row in rows.values()
        if selected and row["node"].get("type") in BLOCK_GROUPS
        and row["path"] != selected["path"] and not row["path"].startswith(selected["path"] + ".")
    ]
    fields, styles = [], []
    if kind in BLOCK_LABELS:
        node = selected["node"]
        content = node.get("content") if isinstance(node.get("content"), dict) else {}
        style_values = node.get("styles") if isinstance(node.get("styles"), dict) else {}
        for key in BLOCK_FIELDS.get(kind, ("text",)):
            fields.append((key, BLOCK_FIELD_LABELS[key], content.get(key, "")))
        styles = [(key, label, style_values.get(key, "")) for key, label in BLOCK_STYLES.items()]
    preview = _page_preview_url(page)
    return render(request, "store/management/page_blocks.html", {
        "section": "pages", "content_section": "blocks", "page": page, "rows": rows.values(),
        "selected": selected, "block_version": page.updated_at.isoformat(),
        "block_fields": fields, "block_styles": styles, "placeholder_block": kind in PLACEHOLDER_BLOCKS,
        "block_types": [(key, label) for key, label in BLOCK_LABELS.items() if key in CREATABLE_BLOCKS],
        "can_add_child": kind in BLOCK_GROUPS, "move_targets": move_targets,
        "has_draft": (structure, design) != (page.published_structure, page.published_design),
        "preview_url": preview,
        "draft_preview_url": preview + ("&" if "?" in preview else "?") + "preview_builder=1" if preview else "",
        "revisions": page.builder_revisions.all()[:30],
    })


@management_required
@require_POST
def page_builder_save(request, page_id):
    page = get_object_or_404(PageContent, pk=page_id)
    if len(request.body) > 1024 * 1024:
        return HttpResponseBadRequest("Структура страницы не должна превышать 1 МБ.")
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("Некорректный JSON.")
    if not isinstance(payload, dict) or not isinstance(payload.get("structure"), list):
        return HttpResponseBadRequest("Ожидалась структура страницы.")
    action = payload.get("action", "draft")
    if action not in {"draft", "publish"}:
        return HttpResponseBadRequest("Неизвестное действие конструктора.")
    structure = sanitize_builder_structure(payload["structure"])
    design = payload.get("design", {})
    if not isinstance(design, dict):
        design = {}
    with transaction.atomic():
        page.draft_structure = structure
        page.draft_design = design
        if action == "publish":
            page.published_structure = copy.deepcopy(structure)
            page.published_design = copy.deepcopy(design)
            page.is_visible = True
            revision = BuilderRevision.objects.create(
                page=page,
                structure=copy.deepcopy(structure),
                design=copy.deepcopy(design),
                label="Опубликованная версия",
                created_by=request.user,
            )
        else:
            revision = BuilderRevision.objects.create(
                page=page,
                structure=copy.deepcopy(structure),
                design=copy.deepcopy(design),
                label="Черновик",
                created_by=request.user,
            )
        page.save(update_fields=["draft_structure", "draft_design", "published_structure", "published_design", "is_visible", "updated_at"])
        log_change(request, page, CHANGE, "Опубликована версия конструктора" if action == "publish" else "Черновик конструктора сохранён")
    return JsonResponse({"saved": True, "revision_id": revision.pk, "published": action == "publish"})


@management_required
@require_POST
def page_builder_restore(request, page_id, revision_id):
    page = get_object_or_404(PageContent, pk=page_id)
    revision = get_object_or_404(BuilderRevision, pk=revision_id, page=page)
    structure = sanitize_builder_structure(revision.structure)
    design = revision.design if isinstance(revision.design, dict) else {}
    page.draft_structure = copy.deepcopy(structure)
    page.draft_design = copy.deepcopy(design)
    page.save(update_fields=["draft_structure", "draft_design", "updated_at"])
    log_change(request, page, CHANGE, f"Восстановлена версия конструктора от {revision.created_at:%Y-%m-%d %H:%M}")
    return JsonResponse({"saved": True, "structure": structure, "design": design})

@management_required
def field_form(request, field_id=None):
    if field_id is None and request.GET.get("editor") == "rows" and request.method == "GET":
        return product_attribute_rows(request)
    if request.GET.get("editor") == "product":
        return product_attribute_definition(request, field_id)
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


def product_attribute_rows(request):
    from store.cms_forms import DynamicProductFieldsForm

    product_id = request.GET.get("product")
    ids = request.GET.getlist("field")
    if any(not key.isascii() or not key.isdecimal() or len(key) > 18
           for key in [*ids, *([product_id] if product_id else [])]):
        return JsonResponse({"error": "Некорректный идентификатор."}, status=400)
    product = get_object_or_404(Product, pk=product_id) if product_id else None
    dynamic = DynamicProductFieldsForm(
        product=product, definitions=AttributeDefinition.objects.filter(pk__in=ids),
    )
    return JsonResponse({"rows": {
        field.name[6:]: render_to_string("store/management/product_attribute.html", {"field": field}, request=request)
        for field in dynamic
    }})


@transaction.atomic
def product_attribute_definition(request, field_id):
    from store.cms_forms import DynamicProductFieldsForm

    field = get_object_or_404(AttributeDefinition.objects.select_for_update(), pk=field_id) if field_id else None
    product_id = request.GET.get("product")
    if product_id and (not product_id.isascii() or not product_id.isdecimal() or len(product_id) > 18):
        return JsonResponse({"error": "Некорректный идентификатор товара."}, status=400)
    product = get_object_or_404(Product, pk=product_id) if product_id else None
    if request.method == "GET":
        form = AttributeDefinitionForm(prefix="definition", instance=field)
    elif request.method == "POST":
        form = AttributeDefinitionForm(request.POST, prefix="definition", instance=field)
        same_type = field.value_type if field else None
        valid = form.is_valid()
        if field_id and request.POST.get("confirm_global") != "1":
            form.add_error(None, "Подтвердите изменение для всех товаров.")
        draft_values = request.POST.getlist("draft_value")
        if draft_values and valid:
            if form.cleaned_data["value_type"] != same_type:
                form.add_error("value_type", "Сначала очистите черновое значение поля в форме товара.")
            elif same_type == AttributeDefinition.TYPE_CHOICE:
                choices = {choice.strip() for choice in form.cleaned_data["choices_text"].splitlines()}
                if any(value not in choices for value in draft_values):
                    form.add_error("choices_text", "Сохраните варианты, выбранные в текущей форме товара.")
                if len(draft_values) > 1 and form.cleaned_data["filter_type"] != AttributeDefinition.FILTER_MULTIPLE:
                    form.add_error("filter_type", "Оставьте один выбранный вариант в форме товара.")
        if not form.errors:
            try:
                with transaction.atomic():
                    field = form.save()
            except IntegrityError:
                logger.warning("Attribute definition could not be saved from product editor", exc_info=True)
                form.add_error("name", "Не удалось сохранить поле. Проверьте, свободно ли название.")
            else:
                log_change(request, field, CHANGE if field_id else ADDITION, "Поле сохранено из карточки товара")
                dynamic = DynamicProductFieldsForm(
                    product=product, definitions=AttributeDefinition.objects.filter(pk=field.pk),
                )
                html = render_to_string(
                    "store/management/product_attribute.html", {"field": dynamic[f"field_{field.pk}"]}, request=request,
                )
                return JsonResponse({"id": field.pk, "name": field.name, "html": html})
    else:
        return JsonResponse({"error": "Метод запроса не поддерживается."}, status=405)
    html = render_to_string(
        "store/management/product_attribute_definition.html", {"field": field, "form": form}, request=request,
    )
    return JsonResponse({"html": html}, status=400 if form.is_bound else 200)
