from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import CartItem, Category, DeliveryMethod, Order, OrderItem, Product


class OrderExportRepeatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user("history-owner", "owner-history@example.test", "password")
        cls.other = users.objects.create_user("history-other", "other-history@example.test", "password")
        cls.staff = users.objects.create_user("export-manager", "manager@example.test", "password", is_staff=True)
        cls.category = Category.objects.create(name="История заказов")
        cls.product = Product.objects.create(
            category=cls.category, name="Коробка из истории", sku="OLD-1", price=Decimal("190.00"),
            weight_kg=Decimal("1.250"), length_mm=100, width_mm=200, height_mm=300,
            status=Product.STATUS_PUBLISHED,
        )
        cls.order = Order.objects.create(
            user=cls.owner, full_name="Иван Покупатель", phone="+79990000000",
            email=cls.owner.email, total=Decimal("200.00"), status=Order.STATUS_DONE,
            delivery_method=DeliveryMethod.objects.get(code="delivery"), delivery_method_name="Доставка",
        )
        OrderItem.objects.create(
            order=cls.order, product=cls.product, product_name="Старое название", product_sku="OLD-1",
            unit="шт.", quantity=2, price=Decimal("100.00"), line_total=Decimal("200.00"),
            weight_kg=Decimal("1.250"), volume_m3=Decimal("0.006"),
        )

    def test_repeat_merges_cart_and_uses_current_product_price(self):
        CartItem.objects.create(user=self.owner, product=self.product, quantity=1)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("repeat_order", args=[self.order.pk]), data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(CartItem.objects.get(user=self.owner, product=self.product).quantity, 3)
        self.assertEqual(response.json()["cart"]["items"][0]["price"], "190.00")
        self.order.refresh_from_db()
        self.assertEqual(self.order.total, Decimal("200.00"))

    def test_repeat_and_detail_do_not_expose_another_users_order(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse("repeat_order", args=[self.order.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("account_order_detail", args=[self.order.pk])).status_code, 404)

    def test_hidden_product_is_reported_without_changing_cart(self):
        self.product.status = Product.STATUS_HIDDEN
        self.product.save(update_fields=["status"])
        self.client.force_login(self.owner)
        response = self.client.post(reverse("repeat_order", args=[self.order.pk]))
        self.assertEqual(response.status_code, 409)
        self.assertIn("Старое название", response.json()["skipped"])
        self.assertFalse(CartItem.objects.filter(user=self.owner).exists())

    def test_manager_exports_selected_order_as_one_row_per_item(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("management_orders_export"), {"ids": [self.order.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        sheet = load_workbook(BytesIO(response.content), data_only=True).active
        self.assertEqual(sheet["A2"].value, self.order.number)
        self.assertEqual(sheet["N2"].value, "Старое название")
        self.assertEqual(sheet["O2"].value, "OLD-1")
        self.assertEqual(sheet["M2"].value, "Доставка")

    def test_non_staff_cannot_export(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("management_order_export", args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
