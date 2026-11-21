from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .cms.common import delete_unreferenced_file
from .models import BuilderRevision, Category, EmailVerificationCode, Employee, PageContent, Product


class ReleaseSecurityTests(TestCase):
    def test_file_cleanup_preserves_legacy_builder_revision(self):
        page = PageContent.objects.get(page="home")
        with TemporaryDirectory() as directory:
            storage = FileSystemStorage(location=directory, base_url="https://media.example.test/")
            name = storage.save("site/legacy.png", ContentFile(b"fixture"))
            BuilderRevision.objects.create(page=page, structure=[{"type": "image", "content": {"url": "/media/" + name}}])
            delete_unreferenced_file(name, storage)
            self.assertTrue(storage.exists(name))

    def test_storefront_mutations_require_same_origin_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("home"))
        token = client.cookies["csrftoken"].value
        for endpoint in (
            "account_login", "account_logout", "account_register", "account_verify",
            "account_password_reset", "account_password_reset_confirm",
            "create_customer_request", "add_to_cart", "update_cart", "clear_cart", "toggle_favorite",
        ):
            with self.subTest(endpoint=endpoint):
                response = client.post(reverse(endpoint), {}, content_type="application/json")
                self.assertEqual(response.status_code, 403)
        unrelated = client.post(
            reverse("clear_cart"), {}, content_type="application/json",
            HTTP_ORIGIN="https://unrelated.example", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(unrelated.status_code, 403)
        self.assertEqual(client.post(
            reverse("clear_cart"), {}, content_type="application/json", HTTP_X_CSRFTOKEN=token,
        ).status_code, 200)

    def test_cms_changes_require_staff_post_and_csrf(self):
        users = get_user_model()
        customer = users.objects.create_user("customer-release")
        staff = users.objects.create_user("staff-release", is_staff=True)
        employee = Employee.objects.create(name="Employee", role="Sales")
        url = reverse("management_employee_duplicate", args=[employee.pk])
        client = Client(enforce_csrf_checks=True)
        client.force_login(customer)
        client.get(reverse("home"))
        headers = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
        self.assertEqual(client.post(url, **headers).status_code, 302)
        self.assertEqual(Employee.objects.count(), 1)
        client.force_login(staff)
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(client.get(reverse("management_logout")).status_code, 405)
        client.get(reverse("management_employees"))
        self.assertEqual(client.post(url, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value).status_code, 302)
        self.assertEqual(Employee.objects.count(), 2)

    def test_registration_hashes_password_and_consumes_verification(self):
        email = "new@example.test"
        password = "test-signup-password"
        with patch("store.views.account.send_account_code", return_value=("123456", "test")):
            response = self.client.post(reverse("account_register"), {
                "email": email, "password": password,
            }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        verification = EmailVerificationCode.objects.get(email=email)
        self.assertNotIn("password", verification.payload)
        self.assertNotEqual(verification.payload["password_hash"], password)
        response = self.client.post(reverse("account_verify"), {
            "email": email, "code": verification.code,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(get_user_model().objects.get(username=email).check_password(password))
        verification.refresh_from_db()
        self.assertTrue(verification.is_used)
        self.assertEqual(verification.payload, {"type": "registration"})

    def test_expired_and_exhausted_codes_cannot_be_used(self):
        email = "unregistered@example.test"
        endpoint = reverse("account_verify")
        reset_code = EmailVerificationCode.objects.create(email=email, code="123456", payload={"type": "password_reset"})
        self.assertEqual(self.client.post(endpoint, {"email": email, "code": reset_code.code}, content_type="application/json").status_code, 400)
        expired = EmailVerificationCode.objects.create(email=email, code="111111", payload={"password": "legacy-test"})
        EmailVerificationCode.objects.filter(pk=expired.pk).update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.client.post(endpoint, {"email": email, "code": expired.code}, content_type="application/json").status_code, 400)
        active = EmailVerificationCode.objects.create(email=email, code="222222", payload={"password": "legacy-test"})
        for code in ["999999"] * 5 + [active.code]:
            self.assertEqual(self.client.post(endpoint, {"email": email, "code": code}, content_type="application/json").status_code, 400)
        active.refresh_from_db()
        self.assertTrue(active.is_used)
        self.assertNotIn("password", active.payload)

    def test_multiple_products_without_a_sku_can_be_saved_and_duplicated(self):
        self.client.force_login(get_user_model().objects.create_user("sku-manager", is_staff=True))
        category = Category.objects.create(name="Release audit")
        for index in range(2):
            product = Product.objects.create(category=category, name=f"Box {index}", price=10)
            response = self.client.post(reverse("management_product_edit", args=[product.pk]), {
                "name": product.name, "slug": product.slug, "category": category.pk, "sku": "",
                "price": "10", "unit": "pcs", "min_quantity": 1, "stock_quantity": 0,
                "status": "draft", "availability": "in_stock", "vat_rate": "22.00",
            })
            self.assertEqual(response.status_code, 302)
            product.refresh_from_db()
            self.assertIsNone(product.sku)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse("management_product_duplicate", args=[product.pk])).status_code, 302)
        self.assertEqual(Product.objects.count(), 4)
