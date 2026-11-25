from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, VariantGroup


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
        response = self.client.post(url, {**data, "name": "Цвета", "products": [self.other.pk]}, headers=headers)
        self.assertEqual(response.json()["removed"], [saved.pk])
        self.assertEqual(list(group.products.all()), [self.other])

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
