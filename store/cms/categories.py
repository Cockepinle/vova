import json
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from ..cms_forms import CategoryFilterForm
from ..models import AttributeDefinition, Product, SiteSettings
from ..seo import category_seo_defaults
from ..uploads import MediaProviderError, MediaStorageUnavailable, local_media_missing
from .common import ADDITION, CHANGE, Category, CategoryForm, Count, DELETION, Paginator, Q, get_object_or_404, log_change
from .common import management_required, messages, redirect, render, require_POST


def render_category_form(request, category, form=None, *, create_filter=None, edit_filter=None, image_preview_url=None):
    form = form if form is not None else CategoryForm(instance=category)
    values = {name: (form[name].value() or "") for name in ("name", "slug", "description")}
    candidate = values["slug"] or form.instance.slug or form.instance.available_slug(values["name"])
    defaults = category_seo_defaults(request, SiteSettings.get_solo(), values["name"], candidate, values["description"])
    for name, value in defaults.items():
        form.fields[name].widget.attrs["placeholder"] = value
    attached_filters = []
    available_filters = AttributeDefinition.objects.none()
    if category:
        attached_filters = list(
            category.filter_attributes.annotate(
                has_values=Exists(AttributeDefinition.objects.filter(pk=OuterRef("pk"), product_values__isnull=False)),
                has_groups=Exists(AttributeDefinition.objects.filter(pk=OuterRef("pk"), variant_groups__isnull=False)),
            ).order_by("sort_order", "name")
        )
        # The category's M2M join already limits the reverse category relation.
        memberships = dict(
            Category.filter_attributes.through.objects.filter(
                attributedefinition_id__in=[field.pk for field in attached_filters],
            ).values("attributedefinition_id").annotate(total=Count("category_id"))
            .values_list("attributedefinition_id", "total")
        )
        available_filters = AttributeDefinition.objects.filter(is_filterable=True).exclude(
            pk__in=memberships,
        ).order_by("sort_order", "name")
    return render(request, "store/management/category_form.html", {
        "section": "categories",
        "category": category,
        "form": form,
        "available_filters": available_filters,
        "filter_limit_reached": len(attached_filters) >= 5,
        "attached_filter_rows": [
            {
                "field": field,
                "edit_form": edit_filter if edit_filter is not None and edit_filter.instance.pk == field.pk
                else CategoryFilterForm(instance=field, prefix=f"filter-{field.pk}"),
                "category_count": memberships[field.pk],
                "can_delete": memberships[field.pk] == 1 and not field.has_values and not field.has_groups,
            }
            for field in attached_filters
        ],
        "create_filter_form": create_filter if create_filter is not None else CategoryFilterForm(prefix="new-filter"),
        "category_image_preview_url": (
            category.display_image_url if category else ""
        ) if image_preview_url is None else image_preview_url,
    })


@management_required
def category_form(request, category_id=None):
    category = get_object_or_404(Category, pk=category_id) if category_id else None
    image_preview_url = category.display_image_url if category else ""
    if request.method == "GET" and request.GET.get("seo_preview") == "1":
        instance = category or Category()
        name = request.GET.get("name", "")[:160].strip()
        slug = request.GET.get("slug", "")[:180].strip() or instance.slug or instance.available_slug(name)
        description = request.GET.get("description", "")[:320]
        return JsonResponse(category_seo_defaults(request, SiteSettings.get_solo(), name, slug, description))
    if request.method != "POST":
        initial = {"parent": request.GET.get("parent")} if request.GET.get("parent", "").isdigit() else None
        return render_category_form(request, category, CategoryForm(instance=category, initial=initial), image_preview_url=image_preview_url)

    is_new = category is None
    form = CategoryForm(request.POST, request.FILES, instance=category)
    if form.is_valid():
        try:
            with transaction.atomic():
                if category and "parent" in form.changed_data:
                    list(Category.objects.order_by("pk").select_for_update().values_list("pk", flat=True))
                saved = form.save()
                log_change(request, saved, ADDITION if is_new else CHANGE, "Категория сохранена через CMS")
        except MediaProviderError as error:
            form.add_error("image", error.public_message)
        except MediaStorageUnavailable:
            form.add_error("image", "Хранилище изображений недоступно. Обратитесь к администратору сайта.")
        except (IntegrityError, ValidationError, OSError):
            form.add_error(None, "Не удалось сохранить категорию. Проверьте имя, адрес и изображение.")
        else:
            messages.success(request, "Категория сохранена.")
            return redirect("management_category_edit", category_id=saved.pk)

    if form.cleaned_data.get("remove_image"):
        image_preview_url = ""
    elif form.cleaned_data.get("image_media"):
        image_preview_url = form.cleaned_data["image_media"].file.url
    elif form.cleaned_data.get("image_url"):
        image_preview_url = form.cleaned_data["image_url"]
    if request.FILES.get("image"):
        form.add_error("image", "После исправления ошибок выберите файл повторно.")
    messages.error(request, "Проверьте ошибки в форме категории.")
    return render_category_form(request, category, form, image_preview_url=image_preview_url)


def category_filter_form(request, field=None):
    prefix = f"filter-{field.pk}" if field else "new-filter"
    return CategoryFilterForm(
        request.POST, instance=field,
        prefix=prefix if any(key.startswith(f"{prefix}-") for key in request.POST) else None,
    )


@management_required
@require_POST
@transaction.atomic
def category_filter_attach(request, category_id):
    category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
    field_id = request.POST.get("field_id", "")
    field = None
    if field_id.isascii() and field_id.isdecimal() and len(field_id) <= 18:
        field = AttributeDefinition.objects.select_for_update().filter(pk=field_id, is_filterable=True).first()
    if field is None:
        messages.error(request, "Фильтр недоступен для привязки.")
    elif category.filter_attributes.filter(pk=field.pk).exists():
        messages.info(request, f"Фильтр «{field.name}» уже привязан.")
    elif category.filter_attributes.count() >= 5:
        messages.error(request, "Для категории можно привязать не более пяти фильтров.")
    else:
        category.filter_attributes.add(field)
        log_change(request, category, CHANGE, f"К категории привязан фильтр «{field.name}»")
        messages.success(request, f"Фильтр «{field.name}» привязан.")
    return redirect("management_category_edit", category_id=category.pk)


@management_required
@require_POST
@transaction.atomic
def category_filter_unlink(request, category_id, field_id):
    category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
    field = get_object_or_404(AttributeDefinition.objects.select_for_update(), pk=field_id)
    if category.filter_attributes.filter(pk=field.pk).exists():
        category.filter_attributes.remove(field)
        log_change(request, category, CHANGE, f"От категории отвязан фильтр «{field.name}»")
        messages.success(request, f"Фильтр «{field.name}» отвязан от категории.")
    else:
        messages.info(request, "Фильтр уже отвязан от этой категории.")
    return redirect("management_category_edit", category_id=category.pk)


@management_required
@require_POST
def category_filter_create(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    form = category_filter_form(request)
    if form.is_valid():
        try:
            with transaction.atomic():
                category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
                if category.filter_attributes.count() >= 5:
                    messages.error(request, "Для категории можно привязать не более пяти фильтров.")
                    return redirect("management_category_edit", category_id=category.pk)
                field = form.save()
                category.filter_attributes.add(field)
                log_change(request, field, ADDITION, f"Создан и привязан фильтр «{field.name}»")
        except IntegrityError:
            form.add_error("name", "Такое название или адрес фильтра уже используется.")
        else:
            messages.success(request, f"Фильтр «{field.name}» создан и привязан.")
            return redirect("management_category_edit", category_id=category.pk)
    messages.error(request, "Проверьте параметры нового фильтра.")
    return render_category_form(request, category, create_filter=form)


@management_required
@require_POST
@transaction.atomic
def category_filter_edit(request, category_id, field_id):
    category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
    field = get_object_or_404(AttributeDefinition.objects.select_for_update(), pk=field_id)
    if not category.filter_attributes.filter(pk=field.pk).exists():
        messages.error(request, "Этот фильтр не привязан к категории.")
        return redirect("management_category_edit", category_id=category.pk)
    form = category_filter_form(request, field)
    if form.is_valid():
        try:
            with transaction.atomic():
                field = form.save()
                log_change(request, field, CHANGE, f"Изменён фильтр «{field.name}» категории «{category.name}»")
        except IntegrityError:
            form.add_error("name", "Такое название или адрес фильтра уже используется.")
        else:
            messages.success(request, f"Фильтр «{field.name}» сохранён.")
            return redirect("management_category_edit", category_id=category.pk)
    messages.error(request, "Проверьте параметры фильтра.")
    return render_category_form(request, category, edit_filter=form)


@management_required
@require_POST
def category_filter_delete(request, category_id, field_id):
    try:
        with transaction.atomic():
            category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
            field = get_object_or_404(AttributeDefinition.objects.select_for_update(), pk=field_id)
            if not category.filter_attributes.filter(pk=field.pk).exists():
                messages.error(request, "Этот фильтр не привязан к категории.")
            elif field.filter_categories.count() > 1 or field.product_values.exists() or field.variant_groups.exists():
                messages.error(request, "Фильтр используется в других категориях, товарах или модификациях. Его можно отвязать от этой категории.")
            else:
                name = field.name
                log_change(request, field, DELETION, f"Удалён фильтр «{name}» категории «{category.name}»")
                field.delete()
                messages.success(request, f"Фильтр «{name}» удалён.")
    except IntegrityError:
        messages.error(request, "Фильтр используется и не может быть удалён.")
    return redirect("management_category_edit", category_id=category_id)


@management_required
@require_POST
def category_bulk_action(request):
    ids = request.POST.getlist("ids")
    action = request.POST.get("action")
    categories = Category.objects.filter(id__in=ids)

    if action == "save_statuses":
        category_ids = request.POST.getlist("category_ids")
        updated_count = 0

        for category in Category.objects.filter(id__in=category_ids):
            new_status = request.POST.get(f"status_{category.id}")
            if new_status not in {"published", "hidden"}:
                continue
            is_active = new_status == "published"

            if category.is_active != is_active:
                category.is_active = is_active
                category.save(update_fields=["is_active"])
                log_change(request, category, CHANGE, "Статус категории изменён через CMS")
                updated_count += 1

        if updated_count:
            messages.success(request, f"Статусы сохранены. Изменено: {updated_count}.")
        else:
            messages.success(request, "Статусы сохранены. Изменений не было.")

        return redirect("management_categories")

    if not ids:
        messages.error(request, "Выберите хотя бы одну категорию.")
        return redirect("management_categories")

    if action == "show":
        categories.update(is_active=True)
        messages.success(request, "Категории включены.")
    elif action == "hide":
        categories.update(is_active=False)
        messages.success(request, "Категории скрыты.")
    else:
        messages.error(request, "Неизвестное массовое действие.")

    return redirect("management_categories")

@management_required
def category_list(request):
    rows = Category.tree_rows(with_images=True)
    by_id = {row.pk: row for row in rows}
    counts = dict(Product.objects.values("category_id").annotate(total=Count("pk")).values_list("category_id", "total"))
    for row in rows:
        media_file = row.image_media.file if row.image_media_id else None
        row.tree_image = next((file.url for file in (media_file, row.image)
                               if file and not local_media_missing(file)), row.image_url)
        row.product_count = counts.get(row.pk, 0)
        row.descendant_count = 0
        row.subcategory_count = 0
        row.has_children = False
    for row in reversed(rows):
        if parent := by_id.get(row.parent_id):
            parent.has_children = True
            parent.subcategory_count += 1 + row.subcategory_count
            parent.descendant_count += row.product_count + row.descendant_count
    return render(request, "store/management/category_list.html", {"section": "categories", "tree": rows})


@management_required
@require_http_methods(["GET", "POST"])
def category_products(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if request.method == "POST":
        try:
            moves = json.loads(request.POST["moves"])
            if not isinstance(moves, list) or not 1 <= len(moves) <= 1000:
                raise ValueError
            changes = {}
            for move in moves:
                values = [str(move[key]) for key in ("id", "source", "destination")]
                if not all(value.isascii() and value.isdecimal() and len(value) <= 18 for value in values):
                    raise ValueError
                pk, source, destination = map(int, values)
                if min(pk, source, destination) <= 0 or max(pk, source, destination) >= 10**18:
                    raise ValueError
                if source == destination or category.pk not in (source, destination) or pk in changes:
                    raise ValueError
                changes[pk] = (source, destination)
        except (KeyError, TypeError, ValueError, OverflowError):
            return JsonResponse({"error": "Проверьте товары и выберите категорию назначения."}, status=400)
        with transaction.atomic():
            targets = {destination for _, destination in changes.values()}
            existing = set(Category.objects.filter(pk__in=targets).order_by("pk")
                           .select_for_update(no_key=True).values_list("pk", flat=True))
            if existing != targets:
                return JsonResponse({"error": "Категория назначения больше не существует."}, status=409)
            products = list(Product.objects.select_for_update().filter(pk__in=changes).order_by("pk"))
            if len(products) != len(changes) or any(item.category_id != changes[item.pk][0] for item in products):
                return JsonResponse({"error": "Категории товаров изменились. Обновите список и повторите операцию."}, status=409)
            affected = {category.pk}
            for item in products:
                source, item.category_id = changes[item.pk]
                affected.update((source, item.category_id))
                log_change(request, item, CHANGE, f"Категория товара изменена с {source} на {item.category_id}")
            Product.objects.bulk_update(products, ["category_id"])
            totals = dict(Product.objects.filter(category_id__in=affected).values("category_id")
                          .annotate(total=Count("pk")).values_list("category_id", "total"))
        return JsonResponse({"counts": {key: totals.get(key, 0) for key in affected}})

    products = Product.objects.select_related("category").prefetch_related("images__media").order_by("name", "pk")
    if request.GET.get("mode") == "available":
        products = products.exclude(category=category)
    else:
        products = products.filter(category=category)
    if query := request.GET.get("q", "").strip()[:180]:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    page = Paginator(products, 20).get_page(request.GET.get("page"))
    return JsonResponse({
        "rows": [{
            "id": item.pk, "name": item.name, "sku": item.sku, "category": item.category_id,
            "category_name": item.category.name, "image": item.display_image_url,
            "status": item.get_status_display(), "price": str(item.price),
            "url": reverse("management_product_edit", args=[item.pk]),
        } for item in page],
        "page": page.number, "pages": page.paginator.num_pages, "total": page.paginator.count,
    })


@management_required
@require_POST
def category_delete(request, category_id):
    try:
        with transaction.atomic():
            category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
            if category.products.exists() or category.children.exists():
                messages.error(request, "Нельзя удалить категорию, в которой есть товары или подкатегории.")
                return redirect("management_categories")
            log_change(request, category, DELETION, "Категория удалена через CMS")
            category.delete()
    except IntegrityError:
        messages.error(request, "Категория используется и не может быть удалена.")
    else:
        messages.success(request, "Категория удалена.")
    return redirect("management_categories")

@management_required
@require_POST
@transaction.atomic
def category_duplicate(request, category_id):
    category = get_object_or_404(Category.objects.select_for_update(), pk=category_id)
    name = f"{category.name[:152]} — копия"
    suffix = uuid4().hex
    if Category.objects.filter(name=name).exists():
        name = f"{category.name[:143]} — копия {suffix[:8]}"
    category.pk = None
    category.name = name
    category.slug = f"{category.slug[:142]}-copy-{suffix}"
    category.is_active = False
    category.save()
    log_change(request, category, ADDITION, "Создана копия категории")
    messages.success(request, "Категория продублирована.")
    return redirect("management_category_edit", category_id=category.pk)
