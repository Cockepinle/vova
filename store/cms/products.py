from .common import ADDITION, AttributeDefinition, CHANGE, Category, CustomerPrice, CustomerPriceFormSet, CustomerProfile, DELETION, Decimal, DynamicProductFieldsForm
from .common import HttpResponse, InvalidOperation, Paginator, Product, ProductExcelImportForm, ProductForm, ProductImage, Q, SiteMedia, export_products
from .common import get_object_or_404, get_user_model, import_products, log_change, management_required, messages, redirect, render, require_POST, transaction

@management_required
def product_duplicate(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    attributes = list(product.attributes.all())
    product.pk = None
    product.name = f"{product.name} — копия"
    product.sku = f"{product.sku}-copy"
    product.slug = ""
    product.status = Product.STATUS_DRAFT
    product.save()
    log_change(request, product, ADDITION, "Создана копия товара")

    for attribute in attributes:
        attribute.pk = None
        attribute.product = product
        attribute.save()

    messages.success(request, "Товар продублирован как черновик.")
    return redirect("management_product_edit", product_id=product.pk)

@management_required
def product_list(request):
    products = Product.objects.select_related("category").prefetch_related("attributes__attribute")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    payment_status = request.GET.get("payment_status", "")
    payment_method = request.GET.get("payment_method", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    category = request.GET.get("category", "")
    sort = request.GET.get("sort", "name")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )
    if status:
        products = products.filter(status=status)
    if category:
        products = products.filter(category_id=category)

    allowed_sorts = {
        "name": "name",
        "-name": "-name",
        "price": "price",
        "-price": "-price",
        "stock": "stock_quantity",
        "-stock": "-stock_quantity",
        "updated": "-updated_at",
    }
    products = products.order_by(allowed_sorts.get(sort, "name"))
    table_fields = AttributeDefinition.objects.filter(show_in_table=True, is_visible=True).order_by("sort_order", "name")

    paginator = Paginator(products, 10)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "store/management/product_list.html",
        {
            "section": "products",
            "page": page,
            "query": query,
            "status": status,
            "category": category,
            "sort": sort,
            "categories": Category.tree_rows(),
            "status_choices": Product.STATUS_CHOICES,
            "table_fields": table_fields,
        },
    )

@management_required
def product_excel_export(request):
    response = HttpResponse(export_products(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="pakline-products.xlsx"'
    return response

@management_required
def product_form(request, product_id=None):
    product = get_object_or_404(Product, pk=product_id) if product_id else None

    if request.method == "POST" and "save_customer_prices" in request.POST:
        if not product:
            messages.error(request, "Сначала сохраните товар, затем назначайте индивидуальные цены.")
            return redirect("management_product_new")
        customers = get_user_model().objects.filter(is_staff=False, is_active=True)
        selected_ids = {int(value) for value in request.POST.getlist("price_customers") if value.isdigit()}
        errors = []
        for customer in customers:
            if customer.pk not in selected_ids:
                CustomerPrice.objects.filter(product=product, user=customer).delete()
                continue
            raw_price = request.POST.get(f"customer_price_{customer.pk}", "").strip().replace(",", ".")
            try:
                price = Decimal(raw_price)
                if price < 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                errors.append(customer.email or customer.username)
                continue
            CustomerPrice.objects.update_or_create(product=product, user=customer, defaults={"price": price})
        if errors:
            messages.error(request, "Не сохранены цены для покупателей: " + ", ".join(errors))
        else:
            messages.success(request, "Индивидуальные цены сохранены. Можно продолжать редактирование товара.")
        return redirect("management_product_edit", product_id=product.pk)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        dynamic_form = DynamicProductFieldsForm(request.POST, request.FILES, product=product)

        price_formset = CustomerPriceFormSet(request.POST if "prices-TOTAL_FORMS" in request.POST else None, instance=form.instance, prefix="prices")
        if form.is_valid() and dynamic_form.is_valid() and (not price_formset.is_bound or price_formset.is_valid()):
            is_new = product is None
            product = form.save()
            dynamic_form.save(product)
            if price_formset.is_bound:
                price_formset.instance = product
                price_formset.save()
            ProductImage.objects.filter(product=product, id__in=request.POST.getlist("delete_images")).delete()
            primary_id = request.POST.get("primary_image")
            if primary_id:
                product.images.update(is_primary=False)
            for product_image in product.images.select_related("media"):
                product_image.alt = request.POST.get(f"image_alt_{product_image.pk}", product_image.alt).strip()
                try:
                    product_image.sort_order = max(0, int(request.POST.get(f"image_order_{product_image.pk}", product_image.sort_order)))
                except (TypeError, ValueError):
                    pass
                if primary_id:
                    product_image.is_primary = str(product_image.pk) == primary_id
                product_image.save(update_fields=["alt", "sort_order", "is_primary"])
            next_order = product.images.count()

            for image in request.FILES.getlist("gallery_images"):
                media = SiteMedia.objects.create(title=image.name.rsplit(".", 1)[0], file=image, alt=product.name)
                ProductImage.objects.create(product=product, media=media, alt=product.name, sort_order=next_order, is_primary=not product.display_image_url)
                next_order += 1

            for media in SiteMedia.objects.filter(pk__in=request.POST.getlist("gallery_media")):
                if not ProductImage.objects.filter(product=product, media=media).exists():
                    ProductImage.objects.create(product=product, media=media, alt=media.alt, sort_order=next_order, is_primary=media.is_image and not product.display_image_url)
                    next_order += 1

            for image_url in request.POST.get("gallery_image_urls", "").splitlines():
                image_url = image_url.strip()

                if image_url:
                    ProductImage.objects.create(product=product, image_url=image_url, alt=product.name, sort_order=next_order, is_primary=not product.display_image_url)
                    next_order += 1

            log_change(request, product, ADDITION if is_new else CHANGE, "Сохранено через CMS")
            messages.success(request, "Товар сохранён.")
            return redirect("management_product_edit", product_id=product.pk)
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = ProductForm(instance=product)
        dynamic_form = DynamicProductFieldsForm(product=product)
        price_formset = CustomerPriceFormSet(instance=form.instance, prefix="prices")

    saved_prices = {price.user_id: price.price for price in CustomerPrice.objects.filter(product=product)} if product else {}
    customer_price_rows = []
    if product:
        for user in get_user_model().objects.filter(is_staff=False, is_active=True).select_related("customer_profile").order_by("email", "username"):
            try:
                level_label = user.customer_profile.get_price_level_display()
            except CustomerProfile.DoesNotExist:
                level_label = dict(CustomerProfile.PRICE_LEVEL_CHOICES)[CustomerProfile.PRICE_RETAIL]
            customer_price_rows.append({"user": user, "price": saved_prices.get(user.pk), "selected": user.pk in saved_prices, "level_label": level_label})

    return render(
        request,
        "store/management/product_form.html",
        {
            "section": "products",
            "product": product,
            "form": form,
            "dynamic_form": dynamic_form,
            "price_formset": price_formset,
            "media_library": SiteMedia.objects.all(),
            "customer_price_rows": customer_price_rows,
        },
    )

@management_required
@require_POST
def product_delete(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    log_change(request, product, DELETION, "Удалено через CMS")
    product.delete()
    messages.success(request, "Товар удалён.")
    return redirect("management_products")

@management_required
@require_POST
def product_bulk_action(request):
    ids = request.POST.getlist("ids")
    action = request.POST.get("action")
    products = Product.objects.filter(id__in=ids)

    if action == "save_statuses":
        product_ids = request.POST.getlist("product_ids")
        updated_count = 0

        for product in Product.objects.filter(id__in=product_ids):
            new_status = request.POST.get(f"status_{product.id}")

            if new_status in [Product.STATUS_PUBLISHED, Product.STATUS_DRAFT, Product.STATUS_HIDDEN] and product.status != new_status:
                product.status = new_status
                product.save(update_fields=["status"])
                log_change(request, product, CHANGE, "Статус товара изменён через CMS")
                updated_count += 1

        if updated_count:
            messages.success(request, f"Статусы товаров сохранены. Изменено: {updated_count}.")
        else:
            messages.success(request, "Статусы товаров сохранены. Изменений не было.")

        return redirect("management_products")

    if not ids:
        messages.error(request, "Выберите хотя бы одну запись.")
        return redirect("management_products")

    if action in [Product.STATUS_PUBLISHED, Product.STATUS_DRAFT, Product.STATUS_HIDDEN]:
        products.update(status=action)
        messages.success(request, "Статусы обновлены.")
    elif action == "delete":
        for product in products:
            log_change(request, product, DELETION, "Удалено массовым действием")
        products.delete()
        messages.success(request, "Выбранные товары удалены.")
    else:
        messages.error(request, "Неизвестное массовое действие.")

    return redirect("management_products")

@management_required
def product_excel_import(request):
    result = None
    if request.method == "POST":
        form = ProductExcelImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = import_products(form.cleaned_data["file"])
                messages.success(request, f"Импорт завершён: создано {result['created']}, обновлено {result['updated']}, пропущено {result['skipped']}.")
            except ValueError as error:
                form.add_error("file", str(error))
                messages.error(request, "Файл не импортирован: проверьте структуру.")
    else:
        form = ProductExcelImportForm()
    return render(request, "store/management/product_import.html", {"section": "products", "form": form, "result": result})
