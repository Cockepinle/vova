from .common import ADDITION, CHANGE, Category, CategoryForm, Count, DELETION, Paginator, Q, get_object_or_404, log_change
from .common import management_required, messages, redirect, render, require_POST

@management_required
def category_form(request, category_id=None):
    category = get_object_or_404(Category, pk=category_id) if category_id else None

    if request.method == "POST":
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            is_new = category is None
            category = form.save()
            log_change(request, category, ADDITION if is_new else CHANGE, "Категория сохранена через CMS")
            messages.success(request, "Категория сохранена.")
            return redirect("management_categories")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        initial = {"parent": request.GET.get("parent")} if request.GET.get("parent", "").isdigit() else None
        form = CategoryForm(instance=category, initial=initial)

    return render(
        request,
        "store/management/category_form.html",
        {
            "section": "categories",
            "category": category,
            "form": form,
        },
    )

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
    category = get_object_or_404(Category, pk=category_id)
    if category.products.exists() or category.children.exists():
        messages.error(request, "Нельзя удалить категорию, в которой есть товары или подкатегории.")
        return redirect("management_categories")

    log_change(request, category, DELETION, "Категория удалена через CMS")
    category.delete()
    messages.success(request, "Категория удалена.")
    return redirect("management_categories")

@management_required
def category_duplicate(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    category.pk = None
    category.name = f"{category.name} — копия"
    category.slug = ""
    category.is_active = False
    category.save()
    log_change(request, category, ADDITION, "Создана копия категории")
    messages.success(request, "Категория продублирована.")
    return redirect("management_category_edit", category_id=category.pk)
