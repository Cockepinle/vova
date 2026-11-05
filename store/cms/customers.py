from .common import CustomerProfile, CustomerRequest, Paginator, Q, get_user_model, management_required, messages, redirect, render, require_POST

@management_required
def customer_list(request):
    customers = get_user_model().objects.filter(is_staff=False).select_related("customer_profile").order_by("email", "username")
    if request.method == "POST":
        valid_levels = dict(CustomerProfile.PRICE_LEVEL_CHOICES)
        updated = 0
        for customer in customers:
            level = request.POST.get(f"price_level_{customer.pk}")
            if level in valid_levels:
                profile, _ = CustomerProfile.objects.get_or_create(user=customer)
                if profile.price_level != level:
                    profile.price_level = level
                    profile.save(update_fields=["price_level"])
                    updated += 1
        messages.success(request, f"Уровни цен сохранены. Изменено: {updated}.")
        return redirect("management_customers")
    rows = []
    for customer in customers:
        try:
            profile = customer.customer_profile
        except CustomerProfile.DoesNotExist:
            profile = None
        rows.append({"user": customer, "profile": profile, "price_level": profile.price_level if profile else CustomerProfile.PRICE_RETAIL})
    return render(request, "store/management/customer_list.html", {
        "section": "customers", "customers": rows, "price_levels": CustomerProfile.PRICE_LEVEL_CHOICES,
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
