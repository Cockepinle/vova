import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CartItem, Category, CustomerPrice, CustomerProfile, Product, Promotion
from .pricing import resolve_product_price


class PromotionsPricingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.staff = users.objects.create_superuser("admin", "admin@example.test", "password")
        cls.customer = users.objects.create_user("buyer", "buyer@example.test", "password")
        cls.profile = CustomerProfile.objects.create(user=cls.customer, price_level=CustomerProfile.PRICE_WHOLESALE)
        cls.category = Category.objects.create(name="Упаковка")
        cls.product = Product.objects.create(
            category=cls.category, name="Коробка", price=Decimal("180"), cost_price=Decimal("100"),
            retail_coefficient=Decimal("1.5000"), wholesale_coefficient=Decimal("1.2000"), special_coefficient=Decimal("1.1000"),
            weight_kg=Decimal("0.500"), length_mm=Decimal("1000"), width_mm=Decimal("500"), height_mm=Decimal("200"),
            status=Product.STATUS_PUBLISHED,
        )

    def test_price_priority_and_guest_retail(self):
        self.assertEqual(resolve_product_price(self.product), Decimal("150.00"))
        self.assertEqual(resolve_product_price(self.product, self.customer), Decimal("120.00"))
        CustomerPrice.objects.create(user=self.customer, product=self.product, price=Decimal("87.25"))
        self.assertEqual(resolve_product_price(self.product, self.customer), Decimal("87.25"))

    def test_cart_totals_are_calculated_on_backend(self):
        CartItem.objects.create(user=self.customer, product=self.product, quantity=3)
        self.client.force_login(self.customer)
        data = self.client.get(reverse("api_cart")).json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(data["total"], "360.00")
        self.assertEqual(Decimal(data["total_weight_kg"]), Decimal("1.500"))
        self.assertEqual(Decimal(data["total_volume_m3"]), Decimal("0.300"))
        self.assertEqual(data["items"][0]["price"], "120.00")

    def test_checkout_uses_server_price_and_delivery_values(self):
        CartItem.objects.create(user=self.customer, product=self.product, quantity=2)
        self.client.force_login(self.customer)
        response = self.client.post(reverse("checkout_order"), json.dumps({
            "full_name": "Иван Иванов", "phone": "+79990000000", "email": "buyer@example.test",
            "price": "0.01", "weight_kg": "0", "volume_m3": "0",
        }), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        order = self.customer.orders.get()
        item = order.items.get()
        self.assertEqual(order.total, Decimal("240.00"))
        self.assertEqual(item.price, Decimal("120.00"))
        self.assertEqual(item.weight_kg, Decimal("0.500"))
        self.assertEqual(item.volume_m3, Decimal("0.100"))

    def test_only_current_active_promotions_are_public(self):
        now = timezone.now()
        current = Promotion.objects.create(title="Действует", starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=1))
        Promotion.objects.create(title="Будущая", starts_at=now + timedelta(days=1))
        Promotion.objects.create(title="Завершена", ends_at=now - timedelta(seconds=1))
        Promotion.objects.create(title="Выключена", is_active=False)
        response = self.client.get(reverse("promotions"))
        self.assertContains(response, current.title)
        self.assertNotContains(response, "Будущая")
        self.assertNotContains(response, "Завершена")
        self.assertNotContains(response, "Выключена")

    def test_management_changes_customer_level(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("management_customers"), {f"price_level_{self.customer.pk}": "special"})
        self.assertRedirects(response, reverse("management_customers"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.price_level, "special")
