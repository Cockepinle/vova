import json
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count, FilteredRelation, Value
from django.db.models.functions import Coalesce, Concat
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .common import ADDITION, AttributeDefinition, CHANGE, Category, CustomerPrice, CustomerPriceFormSet, CustomerProfile, DELETION, DynamicProductFieldsForm
from .common import HttpResponse, Paginator, Product, ProductExcelImportForm, ProductForm, ProductImage, Q, SiteMedia, export_products
from .common import get_object_or_404, get_user_model, import_products, log_change, management_required, messages, redirect, render, require_POST, transaction
from ..pricing import PRICE_LEVELS, price_for_level, quote_for_level
from ..cms_forms import COEFFICIENT_HELP, parse_individual_price
from ..models.catalog import PRODUCT_SLUG_TRANSLITERATION
from ..uploads import validate_upload
from .product_gallery import gallery_rows, initial_gallery, parse_gallery, public_gallery, save_gallery

@management_required
@require_POST
@transaction.atomic
def product_duplicate(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    attributes = list(product.attributes.all())
    excluded_definitions = list(product.excluded_attribute_definitions.all())
    suffix = uuid4().hex
    product.pk = None
    product.name = f"{product.name[:212]} — копия"
    product.sku = f"{product.sku[:42]}-copy-{suffix}" if product.sku else None
    product.slug = f"{product.slug[:202]}-copy-{suffix}"
    product.status = Product.STATUS_DRAFT
    product.save()
    product.excluded_attribute_definitions.set(excluded_definitions)
    log_change(request, product, ADDITION, "Создана копия товара")

    for attribute in attributes:
        attribute.pk = None
        attribute.product = product
        attribute.save()

    messages.success(request, "Товар продублирован как черновик.")
    return redirect("management_product_edit", product_id=product.pk)

@management_required
def product_list(request):
    products = Product.objects.select_related("category").prefetch_related("attributes__attribute").annotate(
        individual_price_count=Count("individual_prices", distinct=True)
    )
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
    for product in page.object_list:
        product.retail_price_display = price_for_level(product, CustomerProfile.PRICE_RETAIL)
        product.wholesale_price_display = price_for_level(product, CustomerProfile.PRICE_WHOLESALE)
        product.special_price_display = price_for_level(product, CustomerProfile.PRICE_SPECIAL)

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
@transaction.atomic
def product_form(request, product_id=None):
    products = Product.objects.select_for_update() if request.method == "POST" else Product.objects.all()
    product = get_object_or_404(products, pk=product_id) if product_id else None
    preview_slug = product.slug if product else ""
    published_url = bool(product and product.status == Product.STATUS_PUBLISHED)

    if request.method == "POST" and "save_customer_prices" in request.POST:
        if not product:
            messages.error(request, "Сначала сохраните товар, затем назначайте индивидуальные цены.")
            return redirect("management_product_new")
        customers = get_user_model().objects.filter(is_staff=False, is_active=True)
        selected_ids = {int(value) for value in request.POST.getlist("price_customers") if value.isdigit()}
        errors, prices = [], {}
        for customer in customers.filter(pk__in=selected_ids):
            try:
                prices[customer.pk] = parse_individual_price(request.POST.get(f"customer_price_{customer.pk}", ""))
            except ValidationError:
                errors.append(customer.email or customer.username)
        if errors:
            messages.error(request, "Укажите цены с точностью до копеек для покупателей: " + ", ".join(errors))
        else:
            CustomerPrice.objects.filter(product=product, user__in=customers).exclude(user_id__in=prices).delete()
            for user_id, price in prices.items():
                CustomerPrice.objects.update_or_create(product=product, user_id=user_id, defaults={"price": price})
            messages.success(request, "Индивидуальные цены сохранены. Можно продолжать редактирование товара.")
        return redirect("management_product_edit", product_id=product.pk)

    current_gallery = gallery_rows(product)
    gallery = initial_gallery(current_gallery)
    gallery_revision = product.updated_at.isoformat() if product else ""
    gallery_error = ""
    customer_price_draft = ""
    price_edits = {}
    if request.method == "POST":
        has_gallery = "gallery_manifest" in request.POST
        has_editor = "gallery_revision" in request.POST
        existing_media_photos = []
        if product and has_editor and not has_gallery:
            existing_media_photos = [media.pk for media in product.media.filter(media_type=SiteMedia.TYPE_IMAGE) if media.is_image]
        if has_gallery:
            try:
                if request.POST.get("gallery_revision") != gallery_revision:
                    raise ValidationError("Галерея уже изменилась. Обновите страницу перед сохранением.")
                rows, primary = parse_gallery(request.POST["gallery_manifest"], current_gallery)
                gallery = public_gallery(rows, primary)
            except ValidationError as error:
                gallery_error = error.messages[0]
        form = ProductForm(request.POST, request.FILES, instance=product, gallery_editor=has_editor or has_gallery)
        if not has_gallery:
            for image in request.FILES.getlist("gallery_images"):
                try:
                    validate_upload(image)
                except ValidationError as error:
                    form.add_error(None, ValidationError("%(name)s — %(error)s", params={"name": image.name, "error": error.messages[0]}))
        dynamic_form = DynamicProductFieldsForm(request.POST, request.FILES, product=product)
        price_formset = CustomerPriceFormSet(
            request.POST if "prices-TOTAL_FORMS" in request.POST else None,
            instance=form.instance, prefix="prices",
        )
        if product and (customer_price_draft := request.POST.get("customer_price_draft", "")):
            try:
                staged = json.loads(customer_price_draft)
                if not isinstance(staged, dict) or len(staged) > 5000:
                    raise ValueError
                price_edits = validate_price_edits({key: change["value"] for key, change in staged.items()})
            except (KeyError, TypeError, ValueError, ValidationError):
                form.add_error(None, PRICE_EDIT_ERROR)
        if form.is_valid() and dynamic_form.is_valid() and (not price_formset.is_bound or price_formset.is_valid()) and not gallery_error:
            is_new = product is None
            try:
                with transaction.atomic():
                    saved = form.save()
                    dynamic_form.save(saved)
                    if price_formset.is_bound:
                        price_formset.instance = saved
                        price_formset.save()
                    save_price_edits(saved, price_edits)
                    if has_gallery:
                        save_gallery(saved, current_gallery, rows, primary)
                    else:
                        if existing_media_photos:
                            saved.media.add(*existing_media_photos)
                        save_legacy_gallery(saved, request.POST, request.FILES)
                    log_change(request, saved, ADDITION if is_new else CHANGE, "Сохранено через CMS")
            except (IntegrityError, ValidationError, OSError):
                form.add_error(None, "Не удалось сохранить товар. Проверьте, что выбранные файлы и связи доступны.")
            else:
                messages.success(request, "Товар сохранён.")
                return redirect("management_product_edit", product_id=saved.pk)
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = ProductForm(instance=product, gallery_editor=True)
        dynamic_form = DynamicProductFieldsForm(product=product)
        price_formset = CustomerPriceFormSet(instance=form.instance, prefix="prices")

    price_rows = [
        {
            "level": level, "label": label, "field": form[f"{level}_coefficient"],
            "quote": quote_for_level(form.instance, level) if form.instance.price is not None else None,
        }
        for level, label in CustomerProfile.PRICE_LEVEL_CHOICES
    ]

    return render(
        request,
        "store/management/product_form.html",
        {
            "section": "products",
            "product": product,
            "form": form,
            "dynamic_form": dynamic_form,
            "removed_attributes": dynamic_form.removed_definitions,
            "price_formset": price_formset,
            "product_gallery": gallery,
            "gallery_revision": gallery_revision,
            "gallery_error": gallery_error,
            "price_levels": CustomerProfile.PRICE_LEVEL_CHOICES,
            "price_rows": price_rows,
            "coefficient_help": COEFFICIENT_HELP,
            "preview_slug": preview_slug,
            "published_url": published_url,
            "slug_transliteration": PRODUCT_SLUG_TRANSLITERATION,
            "seo_modes": {name: form.data.get(f"draft_seo_{name}", "") for name in ("slug", "h1", "seo_title")},
            "customer_price_draft": customer_price_draft,
        },
    )


def save_legacy_gallery(product, data, files):
    ProductImage.objects.filter(product=product, id__in=data.getlist("delete_images")).delete()
    primary_id = data.get("primary_image")
    if primary_id:
        product.images.update(is_primary=False)
    for product_image in product.images.select_related("media"):
        product_image.alt = data.get(f"image_alt_{product_image.pk}", product_image.alt).strip()
        try:
            product_image.sort_order = max(0, int(data.get(f"image_order_{product_image.pk}", product_image.sort_order)))
        except (TypeError, ValueError):
            pass
        if primary_id:
            product_image.is_primary = str(product_image.pk) == primary_id
        product_image.save(update_fields=["alt", "sort_order", "is_primary"])
    next_order = product.images.count()

    for image in files.getlist("gallery_images"):
        media = SiteMedia.objects.create(title=image.name.rsplit(".", 1)[0], file=image, alt=product.name)
        ProductImage.objects.create(product=product, media=media, alt=product.name, sort_order=next_order, is_primary=not product.display_image_url)
        next_order += 1

    for media in SiteMedia.objects.filter(pk__in=data.getlist("gallery_media")):
        if not ProductImage.objects.filter(product=product, media=media).exists():
            ProductImage.objects.create(product=product, media=media, alt=media.alt, sort_order=next_order, is_primary=media.is_image and not product.display_image_url)
            next_order += 1

    for image_url in data.get("gallery_image_urls", "").splitlines():
        image_url = image_url.strip()

        if image_url:
            ProductImage.objects.create(product=product, image_url=image_url, alt=product.name, sort_order=next_order, is_primary=not product.display_image_url)
            next_order += 1

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


PRICE_EDIT_ERROR = "Проверьте покупателей и цены. Цена должна быть неотрицательной, с точностью до копеек."


def validate_price_edits(edits):
    if not isinstance(edits, dict) or len(edits) > 5000:
        raise ValueError
    entries = {}
    for key, value in edits.items():
        if not key.isascii() or not key.isdecimal() or len(key) > 18:
            raise ValueError
        if value is not None and not isinstance(value, str):
            raise ValueError
        entries[int(key)] = None if value is None else parse_individual_price(value)
    customers = get_user_model().objects.filter(is_staff=False, is_active=True, pk__in=entries)
    if customers.count() != len(entries):
        raise ValueError
    return entries


def save_price_edits(product, entries):
    for buyer, price in entries.items():
        if price is None:
            CustomerPrice.objects.filter(product=product, user_id=buyer).delete()
        else:
            CustomerPrice.objects.update_or_create(product=product, user_id=buyer, defaults={"price": price})


@management_required
@require_http_methods(["GET", "POST"])
def product_customer_prices(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    customers = get_user_model().objects.filter(is_staff=False, is_active=True)
    prices = CustomerPrice.objects.filter(product=product, user__in=customers)
    if request.method == "POST":
        try:
            entries = validate_price_edits(json.loads(request.POST["edits"]))
        except (KeyError, ValueError, ValidationError):
            return JsonResponse({"error": PRICE_EDIT_ERROR}, status=400)
        with transaction.atomic():
            Product.objects.select_for_update().get(pk=product.pk)
            save_price_edits(product, entries)
        return JsonResponse({"saved": True})

    total_selected = prices.count()
    customers = customers.select_related("customer_profile").annotate(
        product_price=FilteredRelation("individual_prices", condition=Q(individual_prices__product=product)),
        level=Coalesce("customer_profile__price_level", Value(CustomerProfile.PRICE_RETAIL)),
        full_name=Concat("first_name", Value(" "), "last_name"),
    )
    if query := request.GET.get("q", "").strip()[:180]:
        customers = customers.filter(
            Q(full_name__icontains=query) | Q(email__icontains=query) | Q(username__icontains=query)
            | Q(customer_profile__company__icontains=query) | Q(customer_profile__phone__icontains=query)
            | (Q(pk=int(query)) if query.isascii() and query.isdecimal() and len(query) < 18 else Q())
        )
    if request.GET.get("level") in PRICE_LEVELS:
        customers = customers.filter(level=request.GET["level"])
    if request.GET.get("selected") == "1":
        added, removed = [], []
        for token in request.GET.get("selection", "").split(",")[:1000]:
            if len(token) < 20 and token[1:].isascii() and token[1:].isdecimal():
                (removed if token[0] == "-" else added).append(int(token[1:]))
        customers = customers.filter(Q(product_price__isnull=False) | Q(pk__in=added)).exclude(pk__in=removed)
    if request.GET.get("priced") == "1":
        customers = customers.filter(product_price__isnull=False)
    page = Paginator(customers.order_by("last_name", "first_name", "email", "pk").values(
        "pk", "full_name", "email", "username", "customer_profile__company",
        "level", "product_price__price", "customer_profile__retail_coefficient",
        "customer_profile__wholesale_coefficient", "customer_profile__special_coefficient",
    ), 25).get_page(request.GET.get("page"))
    rows = [{
        "id": row["pk"], "name": row["full_name"].strip() or row["username"],
        "email": row["email"], "company": row["customer_profile__company"], "level": row["level"],
        "price": row["product_price__price"],
        "coefficient": row.get(f"customer_profile__{row['level']}_coefficient"),
    } for row in page]
    return JsonResponse({"rows": rows, "total": page.paginator.count, "selected": total_selected,
                         "page": page.number, "pages": page.paginator.num_pages})
