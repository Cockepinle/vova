import json
import logging
import random
import smtplib
from uuid import uuid4
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from ..data import ADVANTAGES
from ..models import AttributeDefinition, CartItem, Category, CustomerProfile, CustomerRequest, DeliveryMethod, EmailVerificationCode, Employee, FavoriteItem, Order, OrderItem, PageContent, Payment, PaymentMethod, Product, ProductAttribute, Promotion, SiteSettings
from ..deliveries import prepare_delivery_handoff
from ..payments import PaymentProviderError, create_order_payment, process_webhook
from ..pricing import individual_price_map, resolve_product_price
from ..notifications import notify_manager, notify_manager_safely

from ..services.catalog import attribute_lookup, category_filter_context, customer_prices, decimal_value, format_price, get_home_stats, get_product, get_store_categories, get_store_categories_queryset, get_store_products, get_store_products_queryset, image_url, money, product_badge, product_badges, product_image_url, product_search, product_specs, product_variants, safe_site_setting, safe_site_settings, serialize_category, serialize_product, sort_products
from ..services.cart import cart_payload, clear_cart_storage, clear_user_cart, get_cart_context, get_cart_items, get_checkout_initial, get_session_cart, locked_checkout_snapshot, merge_session_cart_to_user, normalize_quantity, save_session_cart, serialize_cart_item
from ..services.orders import current_checkout_order, refresh_delivery_handoff, replace_order_snapshot, serialize_order, serialize_order_item, set_order_delivery
from ..services.accounts import auth_required_payload, get_favorite_ids, get_favorites_context, send_account_code
from ..services.site import apply_common_context
