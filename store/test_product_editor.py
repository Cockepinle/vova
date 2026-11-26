import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import AttributeDefinition, Category, CustomerPrice, Product, VariantGroup


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

    def test_inline_fields_create_edit_and_unlink_without_affecting_other_products(self):
        definition = {
            "definition-name": "Покрытие", "definition-value_type": "text",
            "definition-is_visible": "on", "definition-table_settings": "1",
        }
        create = reverse("management_field_new") + "?editor=product"
        self.assertContains(self.client.get(create), "definition-name")
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.staff)
        self.assertEqual(strict.post(create, definition).status_code, 403)
        response = self.client.post(create, definition)
        self.assertEqual(response.status_code, 200, response.content)
        field = AttributeDefinition.objects.get(pk=response.json()["id"])
        key = f"field_{field.pk}"
        self.assertIn(key, response.json()["html"])
        self.other.attributes.create(attribute=field, value_text="Глянец")
        edit = reverse("management_field_edit", args=[field.pk]) + f"?editor=product&product={self.other.pk}"
        self.assertEqual(self.client.post(edit, definition).status_code, 400)
        response = self.client.post(edit, {**definition, "definition-name": "Отделка", "confirm_global": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Глянец", response.json()["html"])
        self.assertIn("Отделка", response.json()["html"])

        another = AttributeDefinition.objects.create(name="Плотность")
        save = reverse("management_product_new")
        self.assertEqual(self.client.post(save, self.product_data(
            name="Новая коробка", remove_attribute=[field.pk], **{f"field_{another.pk}": "250"},
        )).status_code, 302)
        product = Product.objects.get(name="Новая коробка")
        self.assertTrue(product.excluded_attribute_definitions.filter(pk=field.pk).exists())
        self.assertEqual(product.attributes.get(attribute=another).value_text, "250")
        self.assertNotContains(self.client.get(reverse("management_product_edit", args=[product.pk])), f'name="{key}"')

        self.other.attributes.create(attribute=another, value_text="100")
        existing = reverse("management_product_edit", args=[self.other.pk])
        self.assertEqual(self.client.post(existing, self.product_data(
            name=self.other.name, remove_attribute=[another.pk], **{key: "Глянец"},
        )).status_code, 302)
        self.assertEqual(self.other.attributes.get(attribute=field).value_text, "Глянец")
        self.assertTrue(self.other.excluded_attribute_definitions.filter(pk=another.pk).exists())
        self.assertFalse(self.other.attributes.filter(attribute=another).exists())
        self.assertEqual(product.attributes.get(attribute=another).value_text, "250")

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

    def test_explicit_attribute_selection_keeps_empty_fields_and_supports_reattaching(self):
        material = AttributeDefinition.objects.create(name="Материал")
        finish = AttributeDefinition.objects.create(name="Покрытие")
        self.other.attributes.create(attribute=material, value_text="Бумага")
        url = reverse("management_product_new")
        self.assertNotContains(self.client.get(url), f'name="field_{material.pk}"')
        response = self.client.get(reverse("management_field_new"), {
            "editor": "rows", "field": [material.pk, finish.pk],
        })
        self.assertEqual(set(response.json()["rows"]), {str(material.pk), str(finish.pk)})
        key = f"field_{material.pk}"
        payload = self.product_data(name="Выбор полей", attribute_selection="1")
        self.assertEqual(self.client.post(url, {
            **payload, "select_attribute": [material.pk, finish.pk], key: "Картон",
        }).status_code, 302)
        product = Product.objects.get(name=payload["name"])
        edit = reverse("management_product_edit", args=[product.pk])
        self.assertContains(self.client.get(edit), f'name="field_{finish.pk}"')
        self.assertFalse(product.attributes.filter(attribute=finish).exists())
        self.assertRedirects(self.client.post(edit, {
            **payload, "remove_attribute": [material.pk, finish.pk],
        }), edit)
        self.assertFalse(product.selected_attribute_definitions.exists())
        self.assertFalse(product.attributes.exists())
        self.assertTrue(product.excluded_attribute_definitions.filter(pk=material.pk).exists())
        self.assertRedirects(self.client.post(edit, {
            **payload, "select_attribute": [material.pk], key: "Пластик",
        }), edit)
        self.assertFalse(product.excluded_attribute_definitions.filter(pk=material.pk).exists())
        self.assertEqual(product.attributes.get(attribute=material).value_text, "Пластик")
        self.assertEqual(self.other.attributes.get(attribute=material).value_text, "Бумага")

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
