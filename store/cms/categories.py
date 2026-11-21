from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef

from ..cms_forms import CategoryFilterForm
from ..models import AttributeDefinition
from .common import ADDITION, CHANGE, Category, CategoryForm, Count, DELETION, Paginator, Q, get_object_or_404, log_change
from .common import management_required, messages, redirect, render, require_POST


def render_category_form(request, category, form=None, *, create_filter=None, edit_filter=None, image_preview_url=None):
    form = form if form is not None else CategoryForm(instance=category)
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
    if request.method != "POST":
        initial = {"parent": request.GET.get("parent")} if request.GET.get("parent", "").isdigit() else None
        return render_category_form(request, category, CategoryForm(instance=category, initial=initial), image_preview_url=image_preview_url)

    is_new = category is None
    form = CategoryForm(request.POST, request.FILES, instance=category)
    if form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save()
                log_change(request, saved, ADDITION if is_new else CHANGE, "Категория сохранена через CMS")
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
    categories = Category.objects.select_related("parent").annotate(product_count=Count("products", distinct=True)).order_by("sort_order", "name")
    query = request.GET.get("q", "").strip()

    if query:
        categories = categories.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(products__name__icontains=query)
            | Q(products__sku__icontains=query)
        ).distinct()

    paginator = Paginator(categories, 12)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "store/management/category_list.html",
        {
            "section": "categories",
            "page": page,
            "query": query,
        },
    )

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
