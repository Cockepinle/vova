import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, CustomerPrice, Product, VariantGroup


class ProductEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user("product-editor", is_staff=True)
        cls.category = Category.objects.create(name="Упаковка")
        cls.other = Product.objects.create(category=cls.category, name="Товар", price=10, status="published")

    def setUp(self):
        self.client.force_login(self.staff)

    def product_data(self, **changes):
        return {
            "category": self.category.pk,
            "name": "Товар",
            "price": "10",
            "unit": "шт.",
            "min_quantity": "1",
            "stock_quantity": "0",
            "availability": Product.AVAILABILITY_IN_STOCK,
            "status": Product.STATUS_PUBLISHED,
            **changes,
        }

    def test_group_fragment_validates_creates_and_updates_existing_group(self):
        url = reverse("management_variant_group_new")
        headers = {"X-Variant-Dialog": "1"}
        response = self.client.get(url, headers=headers)
        self.assertContains(response, 'class="mgmt-form-grid mgmt-form variant-group-form"')
        self.assertNotContains(response, "<!doctype html>")
        data = {"parameters-TOTAL_FORMS": "0", "parameters-INITIAL_FORMS": "0"}
        invalid = self.client.post(url, data, headers=headers)
        self.assertEqual(invalid.status_code, 422)
        self.assertContains(invalid, "errorlist", status_code=422)
        response = self.client.post(url, {**data, "name": "Размеры"}, headers=headers)
        group = VariantGroup.objects.get(pk=response.json()["id"])
        self.assertTrue(response.json()["created"])
        product = self.client.post(reverse("management_product_new"), self.product_data(variant_group=group.pk))
        self.assertEqual(product.status_code, 302)
        saved = Product.objects.get(slug="tovar-2")
        self.assertEqual(saved.variant_group, group)
        url = reverse("management_variant_group_edit", args=[group.pk])
        response = self.client.post(url, {
            **data, "name": "Цвета", "products": [self.other.pk], f"variant_order_{self.other.pk}": "12",
        }, headers=headers)
        self.assertEqual(response.json()["removed"], [saved.pk])
        self.assertEqual(list(group.products.all()), [self.other])
        self.other.refresh_from_db()
        self.assertEqual(self.other.variant_sort_order, 12)

    def test_automatic_slug_collision_and_manual_titles(self):
        response = self.client.post(reverse("management_product_new"), self.product_data(
            slug="tovar", auto_slug="1", seo_title="Ручной заголовок",
        ))
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(slug="tovar-2")
        self.assertEqual(product.h1, "Товар")
        self.assertEqual(product.seo_title, "Ручной заголовок")
        url = reverse("management_product_edit", args=[product.pk])
        response = self.client.post(url, self.product_data(name="Новое название", recommended_products=[self.other.pk] * 2))
        self.assertRedirects(response, url)
        product.refresh_from_db()
        self.assertEqual(product.slug, "tovar-2")
        self.assertEqual(product.seo_title, "Ручной заголовок")
        self.assertEqual(list(product.recommended_products.all()), [self.other])
        response = self.client.post(url, self.product_data(recommended_products=[product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("recommended_products", response.context["form"].errors)
        self.assertEqual(list(product.recommended_products.all()), [self.other])

    def test_cyrillic_slug_matches_editor_transliteration(self):
        title = "Архивный короб 330 × 250 × 350 мм"
        response = self.client.post(reverse("management_product_new"), self.product_data(name=title))
        product = Product.objects.get(slug="arhivnyy-korob-330-250-350-mm")
        self.assertRedirects(response, reverse("management_product_edit", args=[product.pk]))
        self.assertEqual(product.h1, title)
        self.assertEqual(product.seo_title, title)

    def test_product_save_includes_staged_price_changes_without_removing_others(self):
        buyer = get_user_model().objects.create_user("buyer")
        hidden_buyer = get_user_model().objects.create_user("hidden-buyer")
        hidden_price = CustomerPrice.objects.create(product=self.other, user=hidden_buyer, price=15)
        url = reverse("management_product_edit", args=[self.other.pk])
        for value, status in [("-1", 200), ("42,50", 302)]:
            with self.subTest(value=value):
                response = self.client.post(url, self.product_data(
                    customer_price_draft=json.dumps({str(buyer.pk): {"value": value, "original": None}}),
                ))
                self.assertEqual(response.status_code, status)
                if status == 200:
                    self.assertIn("Цена должна быть неотрицательной", str(response.context["form"].non_field_errors()))
                    self.assertFalse(CustomerPrice.objects.filter(product=self.other, user=buyer).exists())
        self.assertEqual(CustomerPrice.objects.get(product=self.other, user=buyer).price, Decimal("42.50"))
        hidden_price.refresh_from_db()
        self.assertEqual(hidden_price.price, 15)
