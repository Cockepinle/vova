from django.contrib import admin
from django.http import HttpResponse

from .models import AdminLoginAttempt, CustomerPrice, DeliveryMethod, ExternalIdentity, OrderStatusHistory, SiteMedia, AttributeDefinition, CartItem, Category, CustomerProfile, CustomerRequest, EmailVerificationCode, Employee, FavoriteItem, Order, OrderItem, PageContent, Payment, PaymentMethod, Product, ProductAttribute, ProductImage, Promotion, SiteSettings, VariantGroup
from .order_export import get_order_exporter


admin.site.site_header = "Панель управления PakLine"
admin.site.site_title = "PakLine"
admin.site.index_title = "Управление сайтом"


@admin.register(AdminLoginAttempt)
class AdminLoginAttemptAdmin(admin.ModelAdmin):
    list_display = ["created_at", "username", "remote_address", "outcome", "user"]
    list_filter = ["outcome", "created_at"]
    search_fields = ["username", "remote_address", "user__username", "user__email"]
    readonly_fields = ["username", "remote_address", "outcome", "user", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CustomerPriceInline(admin.TabularInline):
    model = CustomerPrice
    extra = 1
    autocomplete_fields = ["user"]


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ["status", "created_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1
    autocomplete_fields = ["attribute"]
    fields = [
        "attribute",
        "value_text",
        "value_integer",
        "value_decimal",
        "value_boolean",
        "value_date",
        "value_choice",
        "value_file",
        "value_url",
    ]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "product_sku", "unit", "quantity", "price", "line_total", "vat_rate", "weight_kg", "volume_m3", "length_mm", "width_mm", "height_mm"]
    can_delete = False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ["payment_method", "provider_code", "external_id", "idempotency_key", "amount", "currency", "status", "payment_url", "provider_data", "created_at", "updated_at"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "slug", "is_active"]
    autocomplete_fields = ["parent", "image_media"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]
    filter_horizontal = ["filter_attributes"]


@admin.register(VariantGroup)
class VariantGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "product_count"]
    search_fields = ["name", "products__name", "products__sku"]
    filter_horizontal = ["attributes"]

    @admin.display(description="Товаров")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "category", "cost_price", "retail_price_display", "wholesale_price_display", "special_price_display", "unit", "stock_quantity", "status", "is_hit", "is_new", "is_special", "availability"]
    list_filter = ["category", "variant_group", "status", "is_hit", "is_new", "is_special", "availability"]
    list_editable = ["stock_quantity", "status", "is_hit", "is_new", "is_special", "availability"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name", "sku", "description", "keywords"]
    autocomplete_fields = ["category", "variant_group"]
    inlines = [ProductImageInline, ProductAttributeInline, CustomerPriceInline]
    readonly_fields = ["volume_m3", "retail_price_display", "wholesale_price_display", "special_price_display"]

    @admin.display(description="Розница")
    def retail_price_display(self, obj):
        from .pricing import price_for_level
        return price_for_level(obj, CustomerProfile.PRICE_RETAIL)

    @admin.display(description="Опт")
    def wholesale_price_display(self, obj):
        from .pricing import price_for_level
        return price_for_level(obj, CustomerProfile.PRICE_WHOLESALE)

    @admin.display(description="Спеццена")
    def special_price_display(self, obj):
        from .pricing import price_for_level
        return price_for_level(obj, CustomerProfile.PRICE_SPECIAL)

    @admin.display(description="Объём, м³ (автоматически)")
    def volume_m3(self, obj):
        return obj.volume_m3

    filter_horizontal = ["media"]
    fieldsets = [
        (
            "Основное",
            {
                "fields": [
                    "category",
                    "name",
                    "slug",
                    "sku",
                    "description",
                    "keywords",
                    "variant_group",
                    "image", "image_url", "media",
                ]
            },
        ),
        (
            "Продажи",
            {
                "fields": [
                    "cost_price", "price", "retail_coefficient", "retail_price_display", "wholesale_coefficient", "wholesale_price_display", "special_coefficient", "special_price_display", "old_price", "vat_rate",
                    "unit",
                    "min_quantity",
                    "stock_quantity",
                    "is_hit",
                    "is_new", "is_special",
                    "availability",
                    "status",
                ]
            },
        ),
    ]

    fieldsets += [
        ("Габариты и вес", {"fields": ["length_mm", "width_mm", "height_mm", "weight_kg", "volume_m3"]}),
        ("SEO", {"fields": ["h1", "seo_title", "meta_description", "canonical", "og_title", "og_description", "og_media"]}),
    ]


@admin.register(CustomerPrice)
class CustomerPriceAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "price"]
    list_editable = ["price"]
    search_fields = ["user__username", "user__email", "product__name", "product__sku"]
    autocomplete_fields = ["user", "product"]


@admin.register(SiteMedia)
class SiteMediaAdmin(admin.ModelAdmin):
    from .cms_forms import SiteMediaForm
    form = SiteMediaForm
    list_display = ["title", "media_type", "file", "created_at"]
    list_filter = ["media_type", "created_at"]
    search_fields = ["title", "alt", "description"]


@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ["name", "value_type", "filter_type", "unit", "is_required", "is_visible", "is_filterable"]
    list_filter = ["value_type", "filter_type", "is_required", "is_visible", "is_filterable"]
    list_editable = ["is_required", "is_visible", "is_filterable"]
    exclude = ["slug", "show_in_table", "sort_order"]
    search_fields = ["name", "slug"]


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ["product", "attribute", "value_text", "value_integer", "value_decimal", "value_boolean", "value_date", "value_choice", "value_choices", "value_file", "value_url"]
    list_filter = ["attribute", "attribute__value_type"]
    search_fields = ["product__name", "product__sku", "attribute__name", "value_text", "value_choice"]
    autocomplete_fields = ["product", "attribute"]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ["product", "media", "image", "image_url", "is_primary", "sort_order"]
    list_filter = ["product__category"]
    list_editable = ["is_primary", "sort_order"]
    search_fields = ["product__name", "product__sku", "alt", "image", "image_url"]
    autocomplete_fields = ["product", "media"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["name", "role", "status", "sort_order", "updated_at"]
    list_filter = ["status"]
    list_editable = ["status", "sort_order"]
    search_fields = ["name", "role", "text", "email", "phone"]


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "phone", "price_level", "created_at"]
    list_filter = ["price_level"]
    list_editable = ["price_level"]
    search_fields = ["user__username", "user__email", "company", "phone"]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "quantity", "updated_at"]
    search_fields = ["user__username", "user__email", "product__name", "product__sku"]
    autocomplete_fields = ["user", "product"]


@admin.register(FavoriteItem)
class FavoriteItemAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "created_at"]
    search_fields = ["user__username", "user__email", "product__name", "product__sku"]
    autocomplete_fields = ["user", "product"]


@admin.register(CustomerRequest)
class CustomerRequestAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "company", "phone", "status", "created_at"]
    list_filter = ["status", "created_at"]
    list_editable = ["status"]
    search_fields = ["name", "email", "company", "phone", "text"]
    autocomplete_fields = ["user"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "created_at", "full_name", "phone", "total", "payment_method", "delivery_method", "payment_status", "status"]
    list_filter = ["status", "payment_status", "payment_method", "delivery_method", "created_at"]
    list_editable = ["status"]
    search_fields = ["number", "full_name", "phone", "email", "company", "user__email", "user__username"]
    readonly_fields = ["number", "user", "full_name", "phone", "email", "company", "comment", "total", "stored_total_weight_kg", "stored_total_volume_m3", "payment_method", "payment_method_name", "delivery_method", "delivery_method_name", "delivery_method_kind", "delivery_provider_code", "delivery_origin_address", "delivery_address", "delivery_handoff_url", "delivery_provider_data", "payment_status", "created_at", "updated_at"]
    inlines = [OrderItemInline, PaymentInline, OrderStatusHistoryInline]
    actions = ["export_xlsx"]

    @admin.action(description="Выгрузить выбранные заказы в Excel")
    def export_xlsx(self, request, queryset):
        exporter = get_order_exporter("xlsx")
        queryset = queryset.select_related("user", "payment_method", "delivery_method").prefetch_related("items")
        response = HttpResponse(exporter.export(queryset), content_type=exporter.content_type)
        response["Content-Disposition"] = 'attachment; filename="pakline-orders.xlsx"'
        return response


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "kind", "provider_code", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name", "code", "provider_code"]


@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "code", "provider_code", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name", "code", "provider_code"]


@admin.register(ExternalIdentity)
class ExternalIdentityAdmin(admin.ModelAdmin):
    list_display = ["user", "provider", "subject", "email", "created_at"]
    list_filter = ["provider", "created_at"]
    search_fields = ["user__email", "user__username", "subject", "email"]
    autocomplete_fields = ["user"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["order", "payment_method", "provider_code", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "payment_method", "provider_code", "created_at"]
    search_fields = ["order__number", "external_id", "idempotency_key"]
    readonly_fields = ["order", "payment_method", "provider_code", "external_id", "idempotency_key", "amount", "currency", "status", "payment_url", "provider_data", "created_at", "updated_at"]


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ["email", "code", "is_used", "created_at"]
    list_filter = ["is_used", "created_at"]
    search_fields = ["email", "code"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ["site_name", "footer_phone", "footer_email", "updated_at"]


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ["title", "starts_at", "ends_at", "is_active", "sort_order", "updated_at"]
    list_filter = ["is_active", "starts_at", "ends_at"]
    list_editable = ["is_active", "sort_order"]
    search_fields = ["title", "description"]
    filter_horizontal = ["media"]


@admin.register(PageContent)
class PageContentAdmin(admin.ModelAdmin):
    list_display = ["page_name", "title", "is_visible", "updated_at"]
    list_filter = ["page", "is_visible"]
    list_editable = ["is_visible"]

    @admin.display(description="Страница")
    def page_name(self, obj):
        return obj.get_page_display()
