from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .cms_forms import DynamicProductFieldsForm
from .models import AttributeDefinition, Category, Product, ProductAttribute, VariantGroup


class CatalogConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user("catalog-manager", is_staff=True)
        cls.category = Category.objects.create(name="Упаковка для теста")
        cls.product = Product.objects.create(category=cls.category, name="Белая коробка", sku="WHITE-01", price=15, status=Product.STATUS_PUBLISHED)
        cls.other = Product.objects.create(category=cls.category, name="Крафтовая коробка", sku="KRAFT-01", price=16, status=Product.STATUS_PUBLISHED)

    def setUp(self):
        self.client.force_login(self.staff)

    def field_data(self, **changes):
        return {
            "name": "Оттенок", "value_type": AttributeDefinition.TYPE_CHOICE,
            "filter_type": AttributeDefinition.FILTER_SINGLE, "choices_text": "Белый\nКрафт",
            "sort_order": "2", "is_required": "on", "is_visible": "on",
            "is_filterable": "on", "show_in_table": "on", "table_settings": "1",
            **changes,
        }

    def test_field_settings_catalog_filter_and_safe_edits(self):
        result = self.client.post(reverse("management_field_new"), self.field_data())
        self.assertRedirects(result, reverse("management_fields"))
        field = AttributeDefinition.objects.get(name="Оттенок")
        first = AttributeDefinition.objects.create(name="Материал", sort_order=1)
        key = f"field_{field.pk}"
        self.assertFalse(DynamicProductFieldsForm(product=self.product).fields)

        for product, choice in ((self.product, "Белый"), (self.other, "Крафт")):
            product_url = reverse("management_product_edit", args=[product.pk])
            payload = {
                "category": self.category.pk, "name": product.name, "slug": product.slug, "sku": product.sku,
                "price": str(product.price), "unit": "шт", "min_quantity": 1, "stock_quantity": 10,
                "availability": "in_stock", "status": Product.STATUS_PUBLISHED, "vat_rate": "22.00",
                "attribute_selection": "1", "select_attribute": [first.pk, field.pk],
            }
            invalid = self.client.post(product_url, payload)
            self.assertIn(key, invalid.context["dynamic_form"].errors)
            self.assertFalse(product.attributes.filter(attribute=field).exists())
            saved = self.client.post(product_url, {**payload, key: choice})
            if saved.status_code == 200:
                self.fail(f"Product form errors: {saved.context['form'].errors}; dynamic fields: {saved.context['dynamic_form'].errors}")
            self.assertRedirects(saved, product_url)
        self.category.filter_attributes.add(field)
        original_slug = field.slug
        original_values = list(field.product_values.order_by("pk").values_list("pk", "value_choice"))
        self.assertContains(self.client.get(reverse("management_products")), "<th>Оттенок</th>", html=True)
        self.assertContains(self.client.get(reverse("management_product_edit", args=[self.product.pk])), "Оттенок")
        self.assertContains(self.client.get(reverse("product_detail", args=[self.product.slug])), "Белый")
        listing = self.client.get(reverse("catalog"), {"category": self.category.slug, f"filter_{field.pk}": "Белый"})
        self.assertEqual([item["id"] for item in listing.context["products"]], [str(self.product.pk)])

        edit_url = reverse("management_field_edit", args=[field.pk])
        edited = self.field_data(name="Цвет упаковки", sort_order="0")
        edited.pop("show_in_table")
        self.assertRedirects(self.client.post(edit_url, edited), reverse("management_fields"))
        field.refresh_from_db()
        self.assertFalse(field.show_in_table)
        self.assertEqual(field.slug, original_slug)
        self.assertEqual(list(DynamicProductFieldsForm(product=self.product).fields), [key, f"field_{first.pk}"])
        self.assertNotContains(self.client.get(reverse("management_products")), "<th>Цвет упаковки</th>", html=True)
        self.assertContains(self.client.get(reverse("management_product_edit", args=[self.product.pk])), "Цвет упаковки")
        result = self.client.post(edit_url, {**edited, "value_type": AttributeDefinition.TYPE_INTEGER})
        self.assertContains(result, "У поля есть сохранённые значения.")
        self.assertEqual(list(field.product_values.order_by("pk").values_list("pk", "value_choice")), original_values)

    def test_deleting_group_keeps_values_and_deleting_field_removes_only_its_values(self):
        field = AttributeDefinition.objects.create(name="Отделка")
        other_field = AttributeDefinition.objects.create(name="Плотность")
        group = VariantGroup.objects.create(name="Группа коробок")
        group.attributes.add(field)
        group.products.add(self.product)
        self.category.filter_attributes.add(field)
        value = ProductAttribute.objects.create(product=self.product, attribute=field, value_text="Матовая")
        unrelated = ProductAttribute.objects.create(product=self.product, attribute=other_field, value_text="250")
        group_edit = reverse("management_variant_group_edit", args=[group.pk])
        listing = self.client.get(reverse("management_variant_groups"))
        self.assertContains(listing, group_edit)
        self.assertEqual(listing.context["groups"][0].product_count, 1)
        self.assertContains(self.client.get(group_edit), "Отделка: Матовая")
        delete_url = reverse("management_variant_group_delete", args=[group.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        self.assertRedirects(self.client.post(delete_url), reverse("management_variant_groups"))
        self.product.refresh_from_db()
        self.assertIsNone(self.product.variant_group_id)
        self.assertTrue(ProductAttribute.objects.filter(pk=value.pk).exists())

        field_list = self.client.get(reverse("management_fields"))
        self.assertContains(field_list, "безвозвратно удалены сохранённые значения (1)")
        self.assertRedirects(self.client.post(reverse("management_field_delete", args=[field.pk])), reverse("management_fields"))
        self.assertFalse(AttributeDefinition.objects.filter(pk=field.pk).exists())
        self.assertFalse(ProductAttribute.objects.filter(pk=value.pk).exists())
        self.assertTrue(ProductAttribute.objects.filter(pk=unrelated.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_single_value_survives_changing_choice_mode(self):
        field = AttributeDefinition.objects.create(
            name="Оттенок", value_type=AttributeDefinition.TYPE_CHOICE, choices=["Белый", "Крафт"],
            filter_type=AttributeDefinition.FILTER_MULTIPLE,
        )
        saved = ProductAttribute.objects.create(product=self.product, attribute=field, value_choices=["Белый", "Крафт"])
        edit_url = reverse("management_field_edit", args=[field.pk])
        self.assertContains(self.client.post(edit_url, self.field_data()), "У товаров выбрано несколько значений.")
        saved.value_choices = ["Белый"]
        saved.save(update_fields=["value_choices"])
        self.assertRedirects(self.client.post(edit_url, self.field_data()), reverse("management_fields"))
        key = f"field_{field.pk}"
        form = DynamicProductFieldsForm({key: "Белый"}, product=self.product)
        self.assertEqual(form[key].initial, "Белый")
        self.assertTrue(form.is_valid(), form.errors)
        form.save(self.product)
        saved.refresh_from_db()
        self.assertEqual(saved.display_value(), "Белый")
