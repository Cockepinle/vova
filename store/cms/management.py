from .common import ADDITION, AttributeDefinition, CHANGE, Category, Count, CustomerRequest, DELETION, DeliveryMethod, DeliveryMethodForm, Employee
from .common import EmployeeForm, LogEntry, Order, Paginator, PaymentMethod, PaymentMethodForm, Product, Promotion, PromotionForm, Q
from .common import get_object_or_404, log_change, management_required, messages, redirect, render, require_POST

@management_required
def employee_form(request, employee_id=None):
    employee = get_object_or_404(Employee, pk=employee_id) if employee_id else None

    if request.method == "POST":
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            is_new = employee is None
            employee = form.save()
            log_change(request, employee, ADDITION if is_new else CHANGE, "Сотрудник сохранён через CMS")
            messages.success(request, "Сотрудник сохранён.")
            return redirect("management_employees")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = EmployeeForm(instance=employee)

    return render(
        request,
        "store/management/employee_form.html",
        {
            "section": "employees",
            "employee": employee,
            "form": form,
        },
    )

@management_required
def employee_list(request):
    employees = Employee.objects.order_by("sort_order", "name")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")

    if query:
        employees = employees.filter(
            Q(name__icontains=query)
            | Q(role__icontains=query)
            | Q(text__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
        )
    if status:
        employees = employees.filter(status=status)

    paginator = Paginator(employees, 12)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "store/management/employee_list.html",
        {
            "section": "employees",
            "page": page,
            "query": query,
            "status": status,
            "status_choices": Employee.STATUS_CHOICES,
        },
    )

@management_required
def delivery_method_form(request, method_id=None):
    method = get_object_or_404(DeliveryMethod, pk=method_id) if method_id else None
    form = DeliveryMethodForm(request.POST or None, instance=method)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Способ доставки сохранён.")
        return redirect("management_delivery_methods")
    return render(
        request,
        "store/management/delivery_method_form.html",
        {"section": "delivery_methods", "method": method, "form": form},
    )

@management_required
def payment_method_form(request, method_id=None):
    method = get_object_or_404(PaymentMethod, pk=method_id) if method_id else None
    form = PaymentMethodForm(request.POST or None, instance=method)
    if request.method == "POST" and form.is_valid():
        method = form.save()
        messages.success(request, "Способ оплаты сохранён.")
        return redirect("management_payment_methods")
    return render(request, "store/management/payment_method_form.html", {"section": "payment_methods", "method": method, "form": form})

@management_required
def employee_duplicate(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    employee.pk = None
    employee.name = f"{employee.name} — копия"
    employee.status = Employee.STATUS_DRAFT
    employee.save()
    log_change(request, employee, ADDITION, "Создана копия сотрудника")
    messages.success(request, "Сотрудник продублирован как черновик.")
    return redirect("management_employee_edit", employee_id=employee.pk)

@management_required
def payment_method_list(request):
    return render(request, "store/management/payment_method_list.html", {"section": "payment_methods", "payment_methods": PaymentMethod.objects.all()})

@management_required
@require_POST
def employee_delete(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    log_change(request, employee, DELETION, "Сотрудник удалён через CMS")
    employee.delete()
    messages.success(request, "Сотрудник удалён.")
    return redirect("management_employees")

@management_required
@require_POST
def promotion_delete(request, promotion_id):
    promotion = get_object_or_404(Promotion, pk=promotion_id)
    log_change(request, promotion, DELETION, "Акция удалена через CMS")
    promotion.delete()
    messages.success(request, "Акция удалена.")
    return redirect("management_promotions")

@management_required
def delivery_method_list(request):
    return render(
        request,
        "store/management/delivery_method_list.html",
        {"section": "delivery_methods", "delivery_methods": DeliveryMethod.objects.all()},
    )

@management_required
@require_POST
def employee_bulk_action(request):
    ids = request.POST.getlist("ids")
    action = request.POST.get("action")
    employees = Employee.objects.filter(id__in=ids)

    if action == "save_statuses":
        employee_ids = request.POST.getlist("employee_ids")
        updated_count = 0

        for employee in Employee.objects.filter(id__in=employee_ids):
            new_status = request.POST.get(f"status_{employee.id}")

            if new_status in [Employee.STATUS_PUBLISHED, Employee.STATUS_DRAFT, Employee.STATUS_HIDDEN] and employee.status != new_status:
                employee.status = new_status
                employee.save(update_fields=["status"])
                log_change(request, employee, CHANGE, "Статус сотрудника изменён через CMS")
                updated_count += 1

        if updated_count:
            messages.success(request, f"Статусы сотрудников сохранены. Изменено: {updated_count}.")
        else:
            messages.success(request, "Статусы сотрудников сохранены. Изменений не было.")

        return redirect("management_employees")

    if not ids:
        messages.error(request, "Выберите хотя бы одного сотрудника.")
        return redirect("management_employees")

    if action in [Employee.STATUS_PUBLISHED, Employee.STATUS_DRAFT, Employee.STATUS_HIDDEN]:
        employees.update(status=action)
        messages.success(request, "Статусы сотрудников обновлены.")
    elif action == "delete":
        for employee in employees:
            log_change(request, employee, DELETION, "Сотрудник удалён массовым действием")
        employees.delete()
        messages.success(request, "Выбранные сотрудники удалены.")
    else:
        messages.error(request, "Неизвестное массовое действие.")

    return redirect("management_employees")

@management_required
def dashboard(request):
    stats = {
        "products": Product.objects.count(),
        "published": Product.objects.filter(status=Product.STATUS_PUBLISHED).count(),
        "drafts": Product.objects.filter(status=Product.STATUS_DRAFT).count(),
        "fields": AttributeDefinition.objects.count(),
        "categories": Category.objects.count(),
        "employees": Employee.objects.count(),
        "requests": CustomerRequest.objects.count(),
        "orders": Order.objects.count(),
    }
    recent_products = Product.objects.select_related("category").order_by("-updated_at")[:8]
    categories = Category.objects.annotate(product_count=Count("products")).order_by("name")[:8]
    history = LogEntry.objects.select_related("user", "content_type").order_by("-action_time")[:10]

    return render(
        request,
        "store/management/dashboard.html",
        {
            "section": "dashboard",
            "stats": stats,
            "recent_products": recent_products,
            "categories": categories,
            "history": history,
        },
    )

@management_required
def promotion_form(request, promotion_id=None):
    promotion = get_object_or_404(Promotion, pk=promotion_id) if promotion_id else None
    form = PromotionForm(request.POST or None, instance=promotion)
    if request.method == "POST" and form.is_valid():
        is_new = promotion is None
        promotion = form.save()
        log_change(request, promotion, ADDITION if is_new else CHANGE, "Акция сохранена через CMS")
        messages.success(request, "Акция сохранена.")
        return redirect("management_promotions")
    if request.method == "POST":
        messages.error(request, "Проверьте ошибки в форме.")
    return render(request, "store/management/promotion_form.html", {"section": "promotions", "promotion": promotion, "form": form})

@management_required
def promotion_list(request):
    promotions = Promotion.objects.prefetch_related("media")
    return render(request, "store/management/promotion_list.html", {"section": "promotions", "promotions": promotions})
