import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .deliveries import BaseDeliveryProvider, DeliveryHandoff, _providers as delivery_providers, register_delivery_provider
from .models import CartItem, Category, CustomerProfile, CustomerRequest, DeliveryMethod, Order, Payment, PaymentMethod, Product, SiteSettings
from .payments import BasePaymentProvider, PaymentCallbackResult, PaymentCreationResult, _providers as payment_providers, register_provider


class FakeProvider(BasePaymentProvider):
    code = "fake"

    def create_payment(self, payment, return_url):
        return PaymentCreationResult(external_id=f"fake-{payment.pk}", payment_url="https://pay.example.test/session", data={"return_url": return_url})

    def check_status(self, payment):
        return PaymentCallbackResult(payment.external_id, payment.status)

    def parse_webhook(self, body, headers):
        payload = json.loads(body)
        return PaymentCallbackResult(payload["external_id"], payload["status"], payload)


class FakeDeliveryProvider(BaseDeliveryProvider):
    code = "fake-carrier"

    def prepare_delivery(self, method, request_data):
        return DeliveryHandoff("https://carrier.example.test/calculate", {"request": request_data})


class CheckoutPaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.customer = users.objects.create_user("checkout-owner", "owner@example.test", "password")
        cls.other = users.objects.create_user("checkout-other", "other@example.test", "password")
        CustomerProfile.objects.create(user=cls.customer)
        cls.category = Category.objects.create(name="Заказы")
        cls.product = Product.objects.create(
            category=cls.category, name="Товар для заказа", price=Decimal("125.50"),
            weight_kg=Decimal("2.500"), length_mm=Decimal("500"), width_mm=Decimal("400"), height_mm=Decimal("300"),
            status=Product.STATUS_PUBLISHED,
        )

    def setUp(self):
        self.invoice = PaymentMethod.objects.get(code="invoice")
        self.online = PaymentMethod.objects.get(code="online")
        self.client.force_login(self.customer)
        CartItem.objects.create(user=self.customer, product=self.product, quantity=2)

    def payload(self, method="invoice"):
        return {"full_name": "Покупатель", "phone": "+79990000000", "email": self.customer.email, "payment_method": method}

    def post_checkout(self, method="invoice"):
        return self.client.post(reverse("checkout_order"), json.dumps(self.payload(method)), content_type="application/json")

    def start_checkout(self, method="invoice", order_id=""):
        return self.client.post(reverse("start_checkout"), json.dumps({"payment_method": method, "checkout_order_id": order_id}), content_type="application/json")

    def test_started_checkout_is_saved_once_and_visible_to_owner(self):
        first = self.start_checkout().json()
        second = self.start_checkout().json()
        self.assertEqual(first["checkout_order_id"], second["checkout_order_id"])
        self.assertEqual(Order.objects.filter(user=self.customer).count(), 1)
        order = Order.objects.get(user=self.customer)
        self.assertEqual(order.status, Order.STATUS_CHECKOUT_STARTED)
        self.assertEqual(order.payment_method.code, "invoice")
        self.assertEqual(order.items.get().price, Decimal("125.50"))
        self.assertTrue(CartItem.objects.filter(user=self.customer).exists())
        listed = self.client.get(reverse("account_orders")).json()["orders"]
        self.assertEqual([item["id"] for item in listed], [str(order.pk)])

    def test_invoice_saves_all_snapshots_and_payment(self):
        draft_id = self.start_checkout().json()["checkout_order_id"]
        response = self.client.post(reverse("checkout_order"), json.dumps({**self.payload(), "checkout_order_id": draft_id}), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(user=self.customer)
        item = order.items.get()
        self.assertEqual(item.price, Decimal("125.50"))
        self.assertEqual(order.total, Decimal("251.00"))
        self.assertEqual(order.total_weight_kg, Decimal("5.000"))
        self.assertEqual(order.total_volume_m3, Decimal("0.120"))
        self.assertEqual(order.payment_method, self.invoice)
        self.assertEqual(order.payment_method_name, "Получить счёт")
        self.assertEqual(order.payment_status, Order.PAYMENT_PENDING)
        self.assertEqual(order.status, Order.STATUS_AWAITING_INVOICE)
        self.assertEqual(Order.objects.filter(user=self.customer).count(), 1)
        self.assertEqual(order.payments.get().amount, order.total)
        Product.objects.filter(pk=self.product.pk).update(price=999, weight_kg=9)
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("251.00"))
        self.assertEqual(order.total_weight_kg, Decimal("5.000"))

    def test_invoice_notifies_manager_separately_and_remains_visible_to_customer(self):
        with patch("store.notifications.notify_manager") as notify:
            response = self.post_checkout("invoice")
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(user=self.customer)
        notify.assert_called_once()
        self.assertIn("запросил счёт", notify.call_args.args[0])
        self.assertIn(order.number, notify.call_args.args[0])
        self.assertEqual(self.client.get(reverse("account_orders")).json()["orders"][0]["id"], str(order.pk))

        manager = get_user_model().objects.create_user("invoice-manager", is_staff=True)
        self.client.force_login(manager)
        self.assertContains(self.client.get(reverse("management_orders")), order.number)

    def test_disabled_own_delivery_is_rejected_server_side(self):
        own = DeliveryMethod.objects.get(code="own-delivery")
        own_response = self.client.post(
            reverse("checkout_order"),
            json.dumps({**self.payload(), "delivery_method": own.code}),
            content_type="application/json",
        )
        self.assertEqual(own_response.status_code, 400, own_response.content)
        self.assertFalse(Order.objects.filter(user=self.customer).exists())
        self.assertTrue(CartItem.objects.filter(user=self.customer).exists())

    def test_checkout_ui_shows_all_delivery_choices_and_pickup_location(self):
        shop_settings = SiteSettings.get_solo()
        shop_settings.pickup_address = "Москва, ул. Самовывозная, 10"
        shop_settings.save(update_fields=["pickup_address"])
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Транспортная компания")
        self.assertContains(response, "Собственная доставка")
        self.assertContains(response, "Скоро будет доступно")
        self.assertContains(response, "Самовывоз")
        self.assertContains(response, shop_settings.pickup_address)
        self.assertContains(response, 'value="pickup" required checked')
        self.assertContains(response, 'value="online" disabled')

    def test_pickup_uses_shop_setting_instead_of_carrier(self):
        settings = SiteSettings.get_solo()
        settings.pickup_address = "Москва, ул. Самовывозная, 10"
        settings.save(update_fields=["pickup_address"])
        response = self.client.post(
            reverse("checkout_order"),
            json.dumps({**self.payload(), "delivery_method": "pickup"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(user=self.customer)
        self.assertEqual(order.delivery_method_kind, DeliveryMethod.KIND_PICKUP)
        self.assertEqual(order.delivery_address, settings.pickup_address)
        self.assertFalse(order.delivery_handoff_url)

    def test_disabled_carrier_is_rejected_without_running_provider(self):
        register_delivery_provider(FakeDeliveryProvider())
        self.addCleanup(lambda: delivery_providers.pop("fake-carrier", None))
        carrier = DeliveryMethod.objects.get(code="delivery")
        carrier.provider_code = "fake-carrier"
        carrier.save(update_fields=["provider_code"])
        response = self.client.post(
            reverse("checkout_order"),
            json.dumps({**self.payload(), "delivery_method": carrier.code, "delivery_address": "Казань, ул. Тестовая, 7"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(Order.objects.filter(user=self.customer).exists())
        self.assertTrue(CartItem.objects.filter(user=self.customer).exists())

    def test_checkout_draft_delivery_totals_follow_backend_cart_changes(self):
        draft = self.start_checkout().json()["checkout_order_id"]
        CartItem.objects.filter(user=self.customer, product=self.product).update(quantity=3)
        response = self.client.post(
            reverse("start_checkout"),
            json.dumps({"checkout_order_id": draft, "delivery_method": "pickup", "payment_method": "invoice"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(pk=draft)
        self.assertEqual(order.total_weight_kg, Decimal("7.500"))
        self.assertEqual(order.total_volume_m3, Decimal("0.180"))
        self.assertEqual(order.items.get().quantity, 3)

    def test_online_payment_is_disabled_until_provider_is_configured(self):
        register_provider(FakeProvider())
        self.addCleanup(lambda: payment_providers.pop("fake", None))
        self.online.provider_code = "fake"
        self.online.save(update_fields=["provider_code"])
        response = self.post_checkout("online")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.filter(user=self.customer).exists())
        self.assertFalse(Payment.objects.exists())

    def test_unfinished_checkout_remains_visible_in_customer_and_manager_views(self):
        draft_id = self.start_checkout().json()["checkout_order_id"]
        order = Order.objects.get(pk=draft_id)
        self.assertEqual(order.status, Order.STATUS_CHECKOUT_STARTED)
        self.assertEqual(self.client.get(reverse("account_orders")).json()["orders"][0]["id"], str(order.pk))
        manager = get_user_model().objects.create_user("pending-manager", is_staff=True)
        self.client.force_login(manager)
        self.assertContains(self.client.get(reverse("management_orders")), order.number)

    def test_checkout_submission_is_idempotent_for_started_order(self):
        draft_id = self.start_checkout().json()["checkout_order_id"]
        payload = {**self.payload(), "delivery_method": "pickup", "checkout_order_id": draft_id}
        first = self.client.post(
            reverse("checkout_order"), json.dumps(payload), content_type="application/json",
        )
        second = self.client.post(
            reverse("checkout_order"), json.dumps(payload), content_type="application/json",
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()["order_number"], second.json()["order_number"])
        self.assertEqual(Order.objects.filter(user=self.customer).count(), 1)
        self.assertEqual(Payment.objects.filter(order__user=self.customer).count(), 1)

    def test_cart_totals_sum_multiple_products_and_keep_unknown_metrics_unknown(self):
        second_product = Product.objects.create(
            category=self.category, name="Второй товар", price=10,
            weight_kg=Decimal("0.750"), length_mm=1000, width_mm=1000,
            height_mm=1000, status=Product.STATUS_PUBLISHED,
        )
        CartItem.objects.create(user=self.customer, product=second_product, quantity=3)
        response = self.client.get(reverse("api_cart"))
        self.assertEqual(response.json()["total_weight_kg"], "7.250")
        self.assertEqual(Decimal(response.json()["total_volume_m3"]), Decimal("3.120"))

        unknown_product = Product.objects.create(
            category=self.category, name="Товар без характеристик", price=5,
            status=Product.STATUS_PUBLISHED,
        )
        CartItem.objects.create(user=self.customer, product=unknown_product, quantity=2)
        response = self.client.get(reverse("api_cart"))
        self.assertIsNone(response.json()["total_weight_kg"])
        self.assertIsNone(response.json()["total_volume_m3"])
        unknown_item = next(item for item in response.json()["items"] if item["name"] == unknown_product.name)
        self.assertIsNone(unknown_item["line_weight_kg"])
        self.assertIsNone(unknown_item["line_volume_m3"])

    def test_checkout_requires_csrf_and_preserves_form_token_flow(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customer)
        home = client.get(reverse("home"))
        self.assertEqual(home.status_code, 200)
        csrf_token = client.cookies["csrftoken"].value
        payload = {"payment_method": "invoice", "delivery_method": "pickup"}
        rejected = client.post(
            reverse("start_checkout"), json.dumps(payload), content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 403)
        accepted = client.post(
            reverse("start_checkout"),
            json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 200, accepted.content)

    def test_existing_checkout_methods_are_safely_deactivated(self):
        self.invoice.refresh_from_db()
        self.online.refresh_from_db()
        self.assertTrue(self.invoice.is_active)
        self.assertFalse(self.online.is_active)
        self.assertTrue(DeliveryMethod.objects.get(code="pickup").is_active)
        self.assertFalse(DeliveryMethod.objects.get(code="delivery").is_active)
        self.assertFalse(DeliveryMethod.objects.get(code="own-delivery").is_active)

    def test_quote_request_is_separate_from_order_and_payment(self):
        with patch("store.notifications.notify_manager") as notify:
            response = self.client.post(
                reverse("create_customer_request"),
                json.dumps({
                    "name": "Покупатель КП",
                    "email": self.customer.email,
                    "phone": "+79990000000",
                    "text": "Нужен расчёт для партии товара",
                }),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200, response.content)
        quote = CustomerRequest.objects.get(email=self.customer.email)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[0], "Новый запрос на КП")
        self.assertIn(quote.text, notify.call_args.args[1])
        self.assertFalse(Order.objects.filter(user=self.customer).exists())
        self.assertFalse(Payment.objects.exists())

    def test_quote_request_is_saved_when_manager_notification_fails(self):
        with patch("store.notifications.notify_manager", side_effect=RuntimeError("mail unavailable")):
            with self.assertLogs("store.notifications", level="ERROR"):
                response = self.client.post(
                    reverse("create_customer_request"),
                    json.dumps({
                        "name": "Покупатель КП",
                        "email": self.customer.email,
                        "text": "Нужен расчёт для партии товара",
                    }),
                    content_type="application/json",
                )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(CustomerRequest.objects.filter(email=self.customer.email).exists())
        self.assertFalse(Order.objects.filter(user=self.customer).exists())

    def test_account_api_never_exposes_another_customers_order(self):
        self.post_checkout()
        order = Order.objects.get(user=self.customer)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("account_order_detail", args=[order.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("account_orders")).json()["orders"], [])

    def test_notification_failure_does_not_cancel_order(self):
        with patch("store.notifications.notify_manager", side_effect=RuntimeError("mail unavailable")):
            response = self.post_checkout()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Order.objects.filter(user=self.customer).exists())

    def test_manager_can_mark_unfinished_order_abandoned(self):
        order_id = self.start_checkout().json()["checkout_order_id"]
        staff = get_user_model().objects.create_user("order-manager", is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse("management_order_detail", args=[order_id]), {"status": Order.STATUS_ABANDONED})
        self.assertRedirects(response, reverse("management_order_detail", args=[order_id]))
        self.assertEqual(Order.objects.get(pk=order_id).status, Order.STATUS_ABANDONED)

    def test_management_delivery_filters_and_bulk_order_status(self):
        order_id = self.start_checkout().json()["checkout_order_id"]
        order = Order.objects.get(pk=order_id)
        staff = get_user_model().objects.create_user("delivery-manager", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("management_delivery_methods")).status_code, 200)
        response = self.client.get(reverse("management_orders"), {"delivery_method": order.delivery_method_id})
        self.assertContains(response, order.number)
        response = self.client.post(
            reverse("management_order_bulk"),
            {"ids": [order.pk], "action": "update_status", "status_action": Order.STATUS_PROCESSING},
        )
        self.assertRedirects(response, reverse("management_orders"))
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.STATUS_PROCESSING)
