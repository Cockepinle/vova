from decimal import Decimal, InvalidOperation
from datetime import date
from django.contrib import messages
from django.contrib.auth import logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import filepath_to_uri
from django.views.decorators.http import require_POST
from ..cms_forms import (
    AttributeDefinitionForm,
    CategoryForm,
    DeliveryMethodForm,
    DynamicProductFieldsForm,
    EmployeeForm,
    ManagementLoginForm,
    PageContentForm,
    PaymentMethodForm,
    ProductForm,
    PromotionForm,
    ProductExcelImportForm,
    CustomerPriceFormSet,
    SiteSettingsForm,
    SiteMediaForm,
    SiteLinkFormSet,
)
from ..models import AdminLoginAttempt, AttributeDefinition, BuilderRevision, Category, CustomerPrice, CustomerProfile, CustomerRequest, DeliveryMethod, Employee, Order, PageContent, PaymentMethod, Product, ProductAttribute, ProductImage, Promotion, SiteMedia, SiteSettings, VariantGroup
from ..excel import export_products, import_products
from ..order_export import get_order_exporter
from ..payments import apply_provider_result
from ..security import check_admin_login_allowed, record_admin_login_attempt

def can_manage(user):
    return user.is_authenticated and user.is_staff

def delete_unreferenced_file(name, storage, current_settings_id=None):
    if not name:
        return
    if SiteMedia.objects.filter(file=name).exists():
        return
    file_references = [
        (SiteSettings, "logo_image"),
        (PageContent, "hero_image"),
        (Category, "image"),
        (Product, "image"),
        (ProductImage, "image"),
        (Employee, "image"),
        (ProductAttribute, "value_file"),
        (CustomerRequest, "attachment"),
    ]
    for model, field_name in file_references:
        queryset = model.objects.filter(**{field_name: name})
        if model is SiteSettings and current_settings_id:
            queryset = queryset.exclude(pk=current_settings_id)
        if queryset.exists():
            return
    urls = {storage.url(name)}
    if getattr(storage, "is_local_name", lambda path: True)(name):
        urls.add(f"/media/{filepath_to_uri(name)}")
    for url in urls:
        if BuilderRevision.objects.filter(structure__icontains=url).exists() or PageContent.objects.filter(
            Q(draft_structure__icontains=url) | Q(published_structure__icontains=url)
        ).exists():
            return
    for model in (Category, Product, ProductImage, Employee):
        if model.objects.filter(image_url__in=urls).exists():
            return
    if ProductAttribute.objects.filter(value_url__in=urls).exists():
        return
    storage.delete(name)

class ManagementLoginView(LoginView):
    template_name = "store/management/login.html"
    authentication_form = ManagementLoginForm
    redirect_authenticated_user = False
    success_url = reverse_lazy("management_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and can_manage(request.user):
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._login_blocked = False
        username = request.POST.get("username", "")
        remote_address = request.META.get("REMOTE_ADDR", "")
        decision = check_admin_login_allowed(username, remote_address)
        if not decision.allowed:
            self._login_blocked = True
            record_admin_login_attempt(
                username,
                remote_address,
                AdminLoginAttempt.OUTCOME_BLOCKED,
            )
            form = self.get_form()
            minutes = max(1, (decision.retry_after_seconds + 59) // 60)
            form.add_error(None, f"Вход временно ограничен. Попробуйте снова через {minutes} мин.")
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        username = self.request.POST.get("username", "")
        password = self.request.POST.get("password", "")
        if not getattr(self, "_login_blocked", False) and username and password:
            record_admin_login_attempt(
                username,
                self.request.META.get("REMOTE_ADDR", ""),
                AdminLoginAttempt.OUTCOME_FAILURE,
            )
        return super().form_invalid(form)

    def form_valid(self, form):
        record_admin_login_attempt(
            self.request.POST.get("username", ""),
            self.request.META.get("REMOTE_ADDR", ""),
            AdminLoginAttempt.OUTCOME_SUCCESS,
            user=form.get_user(),
        )
        return super().form_valid(form)

    def get_success_url(self):
        return self.success_url

class AdminLoginView(ManagementLoginView):
    success_url = reverse_lazy("admin:index")

@require_POST
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
