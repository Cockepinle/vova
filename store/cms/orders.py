from .common import CHANGE, DeliveryMethod, HttpResponse, Order, Paginator, PaymentMethod, Q, apply_provider_result, date, get_object_or_404
from .common import get_order_exporter, log_change, management_required, messages, redirect, render, require_POST, transaction

@management_required
def order_list(request):
    orders = Order.objects.select_related("user", "payment_method", "delivery_method").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    payment_status = request.GET.get("payment_status", "")
    payment_method = request.GET.get("payment_method", "")
    delivery_method = request.GET.get("delivery_method", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    if query:
        orders = orders.filter(
            Q(number__icontains=query)
            | Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(company__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
        )

    if status:
        orders = orders.filter(status=status)
    if payment_status in dict(Order.PAYMENT_STATUS_CHOICES):
        orders = orders.filter(payment_status=payment_status)
    if payment_method.isdigit():
        orders = orders.filter(payment_method_id=payment_method)
    if delivery_method.isdigit():
        orders = orders.filter(delivery_method_id=delivery_method)
    for value, lookup in ((date_from, "created_at__date__gte"), (date_to, "created_at__date__lte")):
        try:
            if value:
                orders = orders.filter(**{lookup: date.fromisoformat(value)})
        except ValueError:
            pass

    paginator = Paginator(orders, 12)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "store/management/order_list.html",
        {
            "section": "orders",
            "page": page,
            "query": query,
            "status": status,
            "status_choices": Order.STATUS_CHOICES,
            "payment_status": payment_status,
            "payment_method": payment_method,
            "delivery_method": delivery_method,
            "payment_status_choices": Order.PAYMENT_STATUS_CHOICES,
            "payment_methods": PaymentMethod.objects.all(),
            "delivery_methods": DeliveryMethod.objects.all(),
            "date_from": date_from,
            "date_to": date_to,
        },
    )

@management_required
def order_export(request, order_id=None):
    orders = Order.objects.select_related("user", "payment_method", "delivery_method").prefetch_related("items")
    if order_id is not None:
        order = get_object_or_404(orders, pk=order_id)
        orders = Order.objects.filter(pk=order.pk).select_related("user", "payment_method", "delivery_method").prefetch_related("items")
    elif request.method == "POST":
        ids = request.POST.getlist("ids")
        if not ids:
            messages.error(request, "Выберите хотя бы один заказ для выгрузки.")
            return redirect("management_orders")
        orders = orders.filter(pk__in=ids)
    elif request.GET.get("scope") != "all":
        messages.error(request, "Не указан состав выгрузки.")
        return redirect("management_orders")
    orders = orders.order_by("-created_at", "id")
    exporter = get_order_exporter("xlsx")
    response = HttpResponse(exporter.export(orders), content_type=exporter.content_type)
    suffix = order.number if order_id is not None else "orders"
    response["Content-Disposition"] = f'attachment; filename="pakline-{suffix}.{exporter.extension}"'
    return response

@management_required
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.select_related("user", "payment_method", "delivery_method").prefetch_related("items", "payments", "status_history"), pk=order_id)

    if request.method == "POST":
        if "payment_status" in request.POST:
            new_payment_status = request.POST.get("payment_status")
            payment = order.payments.first()
            if order.payment_method and order.payment_method.kind == PaymentMethod.KIND_INVOICE and payment and new_payment_status in dict(Order.PAYMENT_STATUS_CHOICES):
                apply_provider_result(payment, payment.external_id, new_payment_status)
                messages.success(request, "Статус оплаты сохранён.")
                return redirect("management_order_detail", order_id=order.pk)
            messages.error(request, "Статус онлайн-оплаты меняется только после подтверждения провайдера.")
            return redirect("management_order_detail", order_id=order.pk)
        new_status = request.POST.get("status")

        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save(update_fields=["status", "updated_at"])
            log_change(request, order, CHANGE, "Статус заказа изменён через CMS")
            messages.success(request, "Статус заказа сохранён.")
            return redirect("management_order_detail", order_id=order.pk)

        messages.error(request, "Некорректный статус заказа.")

    return render(
        request,
        "store/management/order_detail.html",
        {
            "section": "orders",
            "order": order,
            "status_choices": Order.STATUS_CHOICES,
            "payment_status_choices": Order.PAYMENT_STATUS_CHOICES,
        },
    )

@management_required
@require_POST
@transaction.atomic
def order_bulk_action(request):
    action = request.POST.get("action")
    if action == "export_xlsx":
        return order_export(request)

    ids = request.POST.getlist("ids")
    if not ids:
        messages.error(request, "Выберите хотя бы один заказ.")
        return redirect("management_orders")
    if action != "update_status" or request.POST.get("status_action") not in dict(Order.STATUS_CHOICES):
        messages.error(request, "Выберите корректное массовое действие и статус.")
        return redirect("management_orders")

    status = request.POST["status_action"]
    updated_count = 0
    for order in Order.objects.filter(pk__in=ids):
        if order.status != status:
            order.status = status
            order.save(update_fields=["status", "updated_at"])
            log_change(request, order, CHANGE, "Статус заказа изменён массовым действием через CMS")
            updated_count += 1
    messages.success(request, f"Статус обновлён. Изменено заказов: {updated_count}.")
    return redirect("management_orders")
