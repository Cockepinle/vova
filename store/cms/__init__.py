"""Compatibility facade for the modularized view functions."""

from .common import AdminLoginView, ManagementLoginView, can_manage, delete_unreferenced_file, log_change, management_logout, management_required
from .products import product_bulk_action, product_delete, product_duplicate, product_excel_export, product_excel_import, product_form, product_list
from .categories import category_bulk_action, category_delete, category_duplicate, category_form, category_list
from .orders import order_bulk_action, order_detail, order_export, order_list
from .customers import customer_list, request_bulk_action, request_list
from .content import field_delete, field_form, field_list, media_library, media_usage, page_content_delete, page_content_form, page_content_list, site_media_delete, site_media_replace, site_media_upload, site_settings
from .management import dashboard, delivery_method_form, delivery_method_list, employee_bulk_action, employee_delete, employee_duplicate, employee_form, employee_list, payment_method_form, payment_method_list, promotion_delete, promotion_form, promotion_list
from .variant_groups import variant_group_delete, variant_group_form, variant_group_list
