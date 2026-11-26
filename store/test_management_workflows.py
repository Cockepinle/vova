import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse

from .models import Category, CustomerPrice, CustomerProfile, Product


class ManagementWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.staff = users.create_user("workflow-staff", is_staff=True)
        cls.buyer = users.create_user("buyer", email="mail@example.test", first_name="Иван", last_name="Петров")
        CustomerProfile.objects.update_or_create(user=cls.buyer, defaults={"company": "Русская компания", "price_level": "wholesale"})
        cls.second_buyer = users.create_user("another-buyer")
        cls.root = Category.objects.create(name="Короба")
        cls.leaf = Category.objects.create(name="Малые", parent=cls.root)
        cls.other = Category.objects.create(name="Другая", parent=cls.leaf)
        cls.product = Product.objects.create(category=cls.leaf, name="Мой короб", price=100, status="published", sku="PACK-001")
        CustomerPrice.objects.create(product=cls.product, user=cls.buyer, price=20)
        CustomerPrice.objects.create(product=cls.product, user=cls.second_buyer, price=30)

    def setUp(self):
        self.client.force_login(self.staff)

    def test_prices_page_search_filters_and_delete_only_changed_buyer(self):
        url = reverse("management_product_prices", args=[self.product.pk])
        for term in ("Иван Петров", "mail@", "Русская компания"):
            response = self.client.get(url, {"q": term, "level": "wholesale", "priced": "1"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row["id"] for row in response.json()["rows"]], [self.buyer.pk])
        users = get_user_model()
        users.objects.bulk_create([users(username=f"page-buyer-{index:03d}") for index in range(1050)])
        first = self.client.get(url).json()
        second = self.client.get(url, {"page": 2}).json()
        self.assertEqual(first["total"], 1052)
        self.assertEqual(len(second["rows"]), 25)
        self.assertFalse({row["id"] for row in first["rows"]} & {row["id"] for row in second["rows"]})
        updated = self.client.post(url, {"edits": json.dumps({str(self.buyer.pk): None})})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(list(CustomerPrice.objects.filter(product=self.product).values_list("user_id", flat=True)), [self.second_buyer.pk])

    def test_category_tree_counts_and_atomic_move(self):
        root_page = self.client.get(reverse("management_categories"))
        self.assertEqual([(row.pk, row.descendant_count) for row in root_page.context["tree"]], [
            (self.root.pk, 1), (self.leaf.pk, 0), (self.other.pk, 0),
        ])
        url = reverse("management_category_products", args=[self.leaf.pk])
        rows = self.client.get(url, {"q": "PACK-001"}).json()["rows"]
        self.assertEqual([row["id"] for row in rows], [self.product.pk])
        payload = {"id": self.product.pk, "source": self.leaf.pk, "destination": self.other.pk}
        response = self.client.post(url, {"moves": json.dumps([payload])})
        self.assertEqual(response.json()["counts"], {str(self.leaf.pk): 0, str(self.other.pk): 1})
        self.product.refresh_from_db()
        self.assertEqual(self.product.category, self.other)
        self.assertEqual(self.product.price, 100)
        self.assertEqual(self.product.individual_prices.count(), 2)
        self.assertEqual(self.client.post(url, {"moves": json.dumps([payload])}).status_code, 409)
        self.assertEqual(self.client.get(url, {"mode": "available"}).json()["rows"][0]["id"], self.product.pk)

    def test_category_move_requires_destination_and_permissions(self):
        url = reverse("management_category_products", args=[self.leaf.pk])
        move = {"id": self.product.pk, "source": self.leaf.pk, "destination": self.other.pk}
        for moves in [[{**move, "destination": None}], [move, move]]:
            self.assertEqual(self.client.post(url, {"moves": json.dumps(moves)}).status_code, 400)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(url, {"moves": json.dumps([move])}).status_code, 403)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.post(url, {"moves": json.dumps([move])}).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.category_id, self.leaf.pk)

    def test_cannot_move_category_under_its_descendant(self):
        url = reverse("management_category_edit", args=[self.root.pk])
        response = self.client.post(url, {
            "name": self.root.name, "parent": self.other.pk, "sort_order": "0", "is_active": "on",
        })
        self.assertIn("parent", response.context["form"].errors)
        self.root.refresh_from_db()
        self.assertIsNone(self.root.parent_id)

    def test_draft_acknowledgement_requires_successful_save(self):
        url = reverse("management_category_new")
        token = "a" * 32
        cookie = "mgmt_saved_" + token
        invalid = self.client.post(url, {"_draft_token": token, "name": ""})
        self.assertNotIn(cookie, invalid.cookies)
        valid = self.client.post(url, {"_draft_token": token, "name": "Новая категория", "sort_order": 0, "is_active": "on"})
        self.assertEqual(valid.status_code, 302)
        self.assertIn(cookie, valid.cookies)

    @patch.dict(os.environ, {"CLOUDINARY_URL": "cloudinary://test:test@placeholder"})
    def test_cloudinary_upload_uses_explicit_safe_public_id(self):
        from store.media_storage import StoreCloudinaryStorage

        storage = StoreCloudinaryStorage()
        with patch.object(storage, "_get_prefix", return_value="media/"), patch(
            "store.media_storage.uploader.upload",
            side_effect=lambda data, **kwargs: {"public_id": kwargs["public_id"], "format": "png"},
        ) as upload:
            name = storage.save("site_media/фото # короб.png", ContentFile(b"content"), max_length=100)
        self.assertRegex(name, r"^media/site_media/[a-f0-9]{32}\.png$")
        self.assertEqual(upload.call_args.kwargs["public_id"], name.removesuffix(".png"))
        self.assertFalse(upload.call_args.kwargs["overwrite"])
