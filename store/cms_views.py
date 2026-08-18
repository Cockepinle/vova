from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .cms_forms import (
    AttributeDefinitionForm,
    CategoryForm,
    DynamicProductFieldsForm,
    EmployeeForm,
    ManagementLoginForm,
    PageContentForm,
    ProductForm,
    SiteSettingsForm,
)
from .models import AttributeDefinition, Category, CustomerRequest, Employee, Order, PageContent, Product, ProductAttribute, ProductImage, SiteSettings


def can_manage(user):
    return user.is_authenticated and user.is_staff


class ManagementLoginView(LoginView):
    template_name = "store/management/login.html"
    authentication_form = ManagementLoginForm
    redirect_authenticated_user = True
    success_url = reverse_lazy("management_dashboard")

    def get_success_url(self):
        return self.success_url


def management_logout(request):
    logout(request)
    messages.success(request, "Вы вышли из панели управления.")
    return redirect("management_login")


def management_required(view_func):
    return login_required(user_passes_test(can_manage, login_url="management_login")(view_func), login_url="management_login")


def log_change(request, obj, action_flag, message):
    LogEntry.objects.log_action(
        user_id=request.user.pk,
        content_type_id=ContentType.objects.get_for_model(obj).pk,
        object_id=obj.pk,
        object_repr=str(obj),
        action_flag=action_flag,
        change_message=message,
    )


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
def product_list(request):
    products = Product.objects.select_related("category").prefetch_related("attributes__attribute")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
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
            "categories": Category.objects.order_by("name"),
            "status_choices": Product.STATUS_CHOICES,
            "table_fields": table_fields,
        },
    )


@management_required
def category_list(request):
    categories = Category.objects.annotate(product_count=Count("products", distinct=True)).order_by("sort_order", "name")
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
        form = CategoryForm(instance=category)

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


@management_required
@require_POST
def category_delete(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if category.products.exists():
        messages.error(request, "Нельзя удалить категорию, в которой есть товары.")
        return redirect("management_categories")

    log_change(request, category, DELETION, "Категория удалена через CMS")
    category.delete()
    messages.success(request, "Категория удалена.")
    return redirect("management_categories")


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
@require_POST
def employee_delete(request, employee_id):
    employee = get_object_or_404(Employee, pk=employee_id)
    log_change(request, employee, DELETION, "Сотрудник удалён через CMS")
    employee.delete()
    messages.success(request, "Сотрудник удалён.")
    return redirect("management_employees")


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
def product_form(request, product_id=None):
    product = get_object_or_404(Product, pk=product_id) if product_id else None

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        dynamic_form = DynamicProductFieldsForm(request.POST, request.FILES, product=product)

        if form.is_valid() and dynamic_form.is_valid():
            is_new = product is None
            product = form.save()
            dynamic_form.save(product)
            ProductImage.objects.filter(product=product, id__in=request.POST.getlist("delete_images")).delete()
            next_order = product.images.count()

            for image in request.FILES.getlist("gallery_images"):
                ProductImage.objects.create(product=product, image=image, sort_order=next_order)
                next_order += 1

            for image_url in request.POST.get("gallery_image_urls", "").splitlines():
                image_url = image_url.strip()

                if image_url:
                    ProductImage.objects.create(product=product, image_url=image_url, sort_order=next_order)
                    next_order += 1

            log_change(request, product, ADDITION if is_new else CHANGE, "Сохранено через CMS")
            messages.success(request, "Товар сохранён.")
            return redirect("management_product_edit", product_id=product.pk)
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = ProductForm(instance=product)
        dynamic_form = DynamicProductFieldsForm(product=product)

    return render(
        request,
        "store/management/product_form.html",
        {
            "section": "products",
            "product": product,
            "form": form,
            "dynamic_form": dynamic_form,
        },
    )


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
def order_list(request):
    orders = Order.objects.select_related("user").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")

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
        },
    )


@management_required
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("items"), pk=order_id)

    if request.method == "POST":
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
        },
    )


@management_required
def field_list(request):
    fields = AttributeDefinition.objects.order_by("sort_order", "name")

    return render(
        request,
        "store/management/field_list.html",
        {
            "section": "fields",
            "fields": fields,
        },
    )


@management_required
def field_form(request, field_id=None):
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


@management_required
@require_POST
def field_delete(request, field_id):
    field = get_object_or_404(AttributeDefinition, pk=field_id)
    ProductAttribute.objects.filter(attribute=field).delete()
    log_change(request, field, DELETION, "Поле удалено через CMS")
    field.delete()
    messages.success(request, "Поле удалено.")
    return redirect("management_fields")


@management_required
def site_settings(request):
    settings = SiteSettings.get_solo()

    if request.method == "POST":
        form = SiteSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            settings = form.save()
            log_change(request, settings, CHANGE, "Настройки сайта обновлены")
            messages.success(request, "Настройки сайта сохранены.")
            return redirect("management_settings")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = SiteSettingsForm(instance=settings)

    return render(
        request,
        "store/management/site_settings.html",
        {
            "section": "settings",
            "form": form,
        },
    )


@management_required
def page_content_list(request):
    pages = PageContent.objects.order_by("page")

    return render(
        request,
        "store/management/page_content_list.html",
        {
            "section": "settings",
            "pages": pages,
        },
    )


@management_required
def page_content_form(request, page_id=None):
    page = get_object_or_404(PageContent, pk=page_id) if page_id else None

    if request.method == "POST":
        form = PageContentForm(request.POST, instance=page)
        if form.is_valid():
            is_new = page is None
            page = form.save()
            log_change(request, page, ADDITION if is_new else CHANGE, "Текст страницы сохранён")
            messages.success(request, "Текст страницы сохранён.")
            return redirect("management_pages")
        messages.error(request, "Проверьте ошибки в форме.")
    else:
        form = PageContentForm(instance=page)

    return render(
        request,
        "store/management/page_content_form.html",
        {
            "section": "settings",
            "page_content": page,
            "form": form,
        },
    )


@management_required
@require_POST
def page_content_delete(request, page_id):
    page = get_object_or_404(PageContent, pk=page_id)
    log_change(request, page, DELETION, "Текст страницы удалён")
    page.delete()
    messages.success(request, "Текст страницы удалён.")
    return redirect("management_pages")


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
