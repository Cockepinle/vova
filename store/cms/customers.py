import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from ..cms_forms import COEFFICIENT_FIELDS, COEFFICIENT_HELP, CustomerDetailsForm, CustomerIdentityForm, CustomerPricingForm, parse_individual_price
from ..pricing import customer_price_level, resolve_product_price
from ..services.catalog import product_search
from .common import CustomerPrice, CustomerProfile, CustomerRequest, Paginator, Product, Q, get_object_or_404, get_user_model, management_required, messages, redirect, render, require_POST


@management_required
def customer_list(request):
    customers = get_user_model().objects.filter(is_staff=False).select_related("customer_profile").order_by("email", "username")
    query = request.GET.get("q", "").strip()[:120]
    level_filter = request.GET.get("level", "")
    level_labels = dict(CustomerProfile.PRICE_LEVEL_CHOICES)
    if query:
        words = query.split()
        fields = ("first_name", "last_name", "email", "username", "customer_profile__company", "customer_profile__phone")
        if connection.vendor == "sqlite":
            def matches(values):
                searchable = " ".join(value or "" for value in values).casefold()
                return all(word.casefold() in searchable for word in words)

            ids = [pk for pk, *values in customers.values_list("pk", *fields).iterator() if matches(values)]
            customers = customers.filter(pk__in=ids)
        else:
            for word in words:
                matches = Q()
                for field in fields:
                    matches |= Q(**{f"{field}__icontains": word})
                customers = customers.filter(matches)
    if level_filter in level_labels:
        levels = Q(customer_profile__price_level=level_filter)
        if level_filter == CustomerProfile.PRICE_RETAIL:
            levels |= Q(customer_profile__isnull=True)
        customers = customers.filter(levels)
    page = Paginator(customers, 25).get_page(request.GET.get("page"))
    rows = [
        {"user": customer, "profile": getattr(customer, "customer_profile", None), "price_level": customer_price_level(customer)}
        for customer in page
    ]

    if request.method == "POST":
        errors = []
        with transaction.atomic():
            changes = []
            ids = [row["user"].pk for row in rows]
            users = get_user_model().objects.select_for_update().filter(pk__in=ids, is_staff=False).order_by("pk")
            for customer in users:
                level = request.POST.get(f"price_level_{customer.pk}")
                if level is None or level == customer_price_level(customer):
                    continue
                profile = getattr(customer, "customer_profile", None) or CustomerProfile(user=customer)
                data = {"price_level": level, **{name: getattr(profile, name) for name in COEFFICIENT_FIELDS}}
                form = CustomerPricingForm(data, instance=profile)
                if form.is_valid():
                    changes.append(form)
                else:
                    errors.extend(f"{customer.email or customer.username}: {error}" for values in form.errors.values() for error in values)
            if not errors:
                for form in changes:
                    form.save()
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(request, f"Уровни цен сохранены. Изменено: {len(changes)}.")
        return redirect(request.get_full_path())

    return render(request, "store/management/customer_list.html", {
        "section": "customers", "customers": rows, "price_levels": CustomerProfile.PRICE_LEVEL_CHOICES,
        "page": page, "query": query, "level_filter": level_filter,
    })


def customer_product_price_row(customer, product, value="", error=""):
    return {
        "id": product.pk, "name": product.name, "sku": product.sku,
        "level_price": format(resolve_product_price(product, customer, individual_prices={}), "f"),
        "value": value, "error": error,
        "status_label": product.get_status_display() if product.status != Product.STATUS_PUBLISHED else "",
    }


@management_required
@require_GET
@never_cache
def customer_product_search(request, customer_id):
    customer = get_object_or_404(get_user_model().objects.select_related("customer_profile"), pk=customer_id, is_staff=False)
    query = " ".join(request.GET.get("q", "")[:120].split())
    if len(query) < 2:
        return JsonResponse({"items": []})
    products = product_search(Product.objects.filter(status=Product.STATUS_PUBLISHED), query)
    return JsonResponse({"items": [
        customer_product_price_row(customer, product) for product in products.order_by("name", "pk")[:15]
    ]})


@management_required
@transaction.atomic
def customer_detail(request, customer_id):
    users = get_user_model().objects
    if request.method == "POST":
        users = users.select_for_update()
    customer = get_object_or_404(users, pk=customer_id, is_staff=False)
    profile = getattr(customer, "customer_profile", None) or CustomerProfile(user=customer)
    prices = dict(customer.individual_prices.values_list("product_id", "price"))
    price_inputs = prices.copy()
    price_errors = {}
    if request.method == "POST":
        data = request.POST.copy()
        for name in ("first_name", "last_name", "email"):
            data.setdefault(name, getattr(customer, name))
        for name in ("price_level", *COEFFICIENT_FIELDS, *CustomerDetailsForm.Meta.fields):
            value = getattr(profile, name)
            if name == "delivery_addresses":
                value = "\n".join(str(address) for address in (value or []))
            data.setdefault(name, "" if value is None else str(value))
        identity_form = CustomerIdentityForm(data, customer=customer)
        details_form = CustomerDetailsForm(data, instance=profile)
        pricing_form = CustomerPricingForm(data, instance=profile)
        forms_valid = all([identity_form.is_valid(), details_form.is_valid(), pricing_form.is_valid()])

        submitted = {}
        for key in request.POST:
            match = re.fullmatch(r"individual_price_([1-9][0-9]{0,17})", key)
            if match:
                submitted[int(match[1])] = request.POST[key].strip()
        allowed = set(Product.objects.filter(pk__in=submitted).filter(
            Q(status=Product.STATUS_PUBLISHED) | Q(pk__in=prices)
        ).values_list("pk", flat=True))
        unknown_products = submitted.keys() - allowed
        updates = {}
        for product_id in allowed:
            raw = price_inputs[product_id] = submitted[product_id]
            try:
                updates[product_id] = parse_individual_price(raw) if raw else None
            except ValidationError as error:
                price_errors[product_id] = error.messages[0]
        if forms_valid and not price_errors and not unknown_products:
            try:
                with transaction.atomic():
                    identity_form.save()
                    profile = pricing_form.save(commit=False)
                    details_form.save(commit=False)
                    profile.save()
                    for product_id, price in updates.items():
                        if price is None:
                            CustomerPrice.objects.filter(user=customer, product_id=product_id).delete()
                        else:
                            CustomerPrice.objects.update_or_create(user=customer, product_id=product_id, defaults={"price": price})
            except IntegrityError:
                messages.error(request, "Не удалось сохранить карточку. Проверьте доступность товаров и уникальность email.")
            else:
                messages.success(request, "Данные клиента сохранены.")
                return redirect("management_customer_detail", customer_id=customer.pk)
        if price_errors:
            messages.error(request, "Укажите индивидуальную цену с точностью до копеек.")
        if unknown_products:
            messages.error(request, "Один из выбранных товаров больше недоступен для назначения цены.")
        if not forms_valid:
            messages.error(request, "Проверьте отмеченные поля карточки клиента.")
    else:
        identity_form = CustomerIdentityForm(customer=customer)
        details_form = CustomerDetailsForm(instance=profile)
        pricing_form = CustomerPricingForm(instance=profile)

    price_customer = customer
    if request.method == "POST" and price_inputs:
        price_customer = get_user_model().objects.select_related("customer_profile").get(pk=customer.pk)
    products = Product.objects.filter(pk__in=price_inputs).order_by("name", "pk")
    orders = Paginator(customer.orders.order_by("-created_at", "-pk"), 15).get_page(request.GET.get("orders"))
    return render(request, "store/management/customer_detail.html", {
        "section": "customers", "customer": customer, "profile": profile,
        "identity_form": identity_form, "details_form": details_form, "pricing_form": pricing_form,
        "coefficient_help": COEFFICIENT_HELP, "orders": orders,
        "product_price_rows": [
            customer_product_price_row(price_customer, product, price_inputs[product.pk], price_errors.get(product.pk, ""))
            for product in products
        ],
    })

@management_required
@require_POST
def request_bulk_action(request):
    ids = request.POST.getlist("ids")
    action = request.POST.get("action")
    requests = CustomerRequest.objects.filter(id__in=ids)

    if not ids:
        messages.error(request, "Выберите хотя бы одну заявку.")
        return redirect("management_requests")

    if action in [CustomerRequest.STATUS_NEW, CustomerRequest.STATUS_PROCESSING, CustomerRequest.STATUS_DONE]:
        requests.update(status=action)
        messages.success(request, "Статусы заявок обновлены.")
    elif action == "delete":
        requests.delete()
        messages.success(request, "Выбранные заявки удалены.")
    else:
        messages.error(request, "Неизвестное массовое действие.")

    return redirect("management_requests")

@management_required
def request_list(request):
    requests = CustomerRequest.objects.select_related("user").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")

    if query:
        requests = requests.filter(Q(name__icontains=query) | Q(email__icontains=query) | Q(company__icontains=query) | Q(phone__icontains=query) | Q(text__icontains=query))
    if status:
        requests = requests.filter(status=status)

    paginator = Paginator(requests, 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "store/management/request_list.html",
        {
            "section": "requests",
            "page": page,
            "query": query,
            "status": status,
            "status_choices": CustomerRequest.STATUS_CHOICES,
        },
    )

@management_required
def request_detail(request, request_id):
    customer_request = get_object_or_404(CustomerRequest.objects.select_related("user"), pk=request_id)
    if request.method == "POST":
        customer_request.status = request.POST.get("status", customer_request.status)
        customer_request.admin_comment = request.POST.get("admin_comment", "").strip()
        customer_request.save(update_fields=["status", "admin_comment", "updated_at"])
        messages.success(request, "Запрос обновлён.")
        return redirect("management_request_detail", request_id=customer_request.pk)
    return render(request, "store/management/request_detail.html", {
        "section": "requests",
        "customer_request": customer_request,
        "status_choices": CustomerRequest.STATUS_CHOICES,
    })
