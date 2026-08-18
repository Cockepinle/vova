from django.contrib import admin

from .models import AttributeDefinition, CartItem, Category, CustomerProfile, CustomerRequest, EmailVerificationCode, Employee, FavoriteItem, Order, OrderItem, PageContent, Product, ProductAttribute, ProductImage, SiteSettings


admin.site.site_header = "Панель управления PakLine"
admin.site.site_title = "PakLine"
admin.site.index_title = "Управление сайтом"


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
    readonly_fields = ["product", "product_name", "product_sku", "unit", "quantity", "price", "line_total"]
    can_delete = False


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "category", "price", "unit", "stock_quantity", "status", "is_hit", "availability"]
    list_filter = ["category", "status", "is_hit", "is_new", "availability"]
    list_editable = ["price", "stock_quantity", "status", "is_hit", "availability"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name", "sku", "description"]
    autocomplete_fields = ["category"]
    inlines = [ProductImageInline, ProductAttributeInline]
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
                    "image",
                ]
            },
        ),
        (
            "Продажи",
            {
                "fields": [
                    "price",
                    "old_price",
                    "unit",
                    "min_quantity",
                    "stock_quantity",
                    "is_hit",
                    "is_new",
                    "availability",
                    "status",
                ]
            },
        ),
    ]


@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ["name", "value_type", "unit", "is_required", "is_visible", "is_filterable"]
    list_filter = ["value_type", "is_required", "is_visible", "is_filterable"]
    list_editable = ["is_required", "is_visible", "is_filterable"]
    exclude = ["slug", "show_in_table", "sort_order"]
    search_fields = ["name", "slug"]


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ["product", "attribute", "value_text", "value_integer", "value_decimal", "value_boolean", "value_date", "value_choice", "value_file", "value_url"]
    list_filter = ["attribute", "attribute__value_type"]
    search_fields = ["product__name", "product__sku", "attribute__name", "value_text", "value_choice"]
    autocomplete_fields = ["product", "attribute"]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ["product", "image", "image_url", "sort_order"]
    list_filter = ["product__category"]
    list_editable = ["sort_order"]
    search_fields = ["product__name", "product__sku", "alt", "image", "image_url"]
    autocomplete_fields = ["product"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["name", "role", "status", "sort_order", "updated_at"]
    list_filter = ["status"]
    list_editable = ["status", "sort_order"]
    search_fields = ["name", "role", "text", "email", "phone"]


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "phone", "created_at"]
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
    list_display = ["number", "created_at", "full_name", "phone", "total", "status"]
    list_filter = ["status", "created_at"]
    list_editable = ["status"]
    search_fields = ["number", "full_name", "phone", "email", "company", "user__email", "user__username"]
    readonly_fields = ["number", "user", "full_name", "phone", "email", "company", "comment", "total", "created_at", "updated_at"]
    inlines = [OrderItemInline]


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ["email", "code", "is_used", "created_at"]
    list_filter = ["is_used", "created_at"]
    search_fields = ["email", "code"]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ["site_name", "footer_phone", "footer_email", "updated_at"]


@admin.register(PageContent)
class PageContentAdmin(admin.ModelAdmin):
    list_display = ["page_name", "title", "is_visible", "updated_at"]
    list_filter = ["page", "is_visible"]
    list_editable = ["is_visible"]

    @admin.display(description="Страница")
    def page_name(self, obj):
        return obj.get_page_display()
