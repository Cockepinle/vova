from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Category, PageContent, Product, Promotion, SiteMedia
from .uploads import MediaProviderError


class ContentWorkflowsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser("cms", "cms@example.test", "test-password")

    def setUp(self):
        self.client.force_login(self.staff)

    @staticmethod
    def png():
        stream = BytesIO()
        Image.new("RGB", (3, 3)).save(stream, "PNG")
        return SimpleUploadedFile("box.png", stream.getvalue(), content_type="image/png")

    def test_category_seo_defaults_collision_and_existing_manual_values(self):
        Category.objects.create(name="Existing", slug="shchit")
        url = reverse("management_category_new")
        preview = self.client.get(url, {"seo_preview": 1, "name": "Щит", "description": "Описание"}).json()
        self.assertEqual(preview["slug"], "shchit-2")
        self.assertTrue(preview["canonical"].endswith("/catalog/?category=shchit-2"))
        self.assertEqual(self.client.post(url, {"name": "Щит", "description": "Описание", "is_active": "on"}).status_code, 302)
        category = Category.objects.get(name="Щит")
        self.assertEqual(category.slug, "shchit-2")
        public_url = reverse("catalog") + "?category=" + category.slug
        response = self.client.get(public_url)
        self.assertContains(response, "<title>Щит</title>", html=True)
        self.assertEqual(response.context["seo"]["h1"], "Щит")
        self.assertEqual(response.context["seo"]["description"], "Описание")
        self.assertEqual(response.context["seo"]["canonical"], preview["canonical"])
        edit = reverse("management_category_edit", args=[category.pk])
        self.assertEqual(self.client.post(edit, {
            "name": "Другой щит", "seo_title": "Ручной SEO", "h1": "Ручной H1", "is_active": "on",
            "canonical": "https://example.test/catalog/?category=original",
        }).status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.slug, "shchit-2")
        response = self.client.get(public_url)
        self.assertContains(response, "<title>Ручной SEO</title>", html=True)
        self.assertEqual(response.context["seo"]["h1"], "Ручной H1")
        self.assertEqual(response.context["seo"]["canonical"], "https://example.test/catalog/?category=original")

    def test_category_upload_library_remote_url_removal_and_failed_upload(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            create = reverse("management_category_new")
            response = self.client.post(create, {"name": "С изображением", "image": self.png(), "is_active": "on"})
            self.assertEqual(response.status_code, 302)
            category = Category.objects.get(name="С изображением")
            self.assertTrue(category.display_image_url.endswith("box.png"))
            storefront = reverse("catalog") + "?category=" + category.slug
            self.assertContains(self.client.get(storefront), category.display_image_url)
            self.assertEqual(
                self.client.get(reverse("api_products"), {"category": category.slug}).json()["category_image"],
                category.display_image_url,
            )
            edit = reverse("management_category_edit", args=[category.pk])
            media = SiteMedia.objects.create(title="Общий файл", file=self.png())
            other = Category.objects.create(name="Ещё категория", image_media=media)
            self.assertEqual(self.client.post(edit, {"name": category.name, "image_media": media.pk}).status_code, 302)
            category.refresh_from_db()
            self.assertEqual(category.display_image_url, media.file.url)
            self.assertEqual(self.client.post(edit, {"name": category.name, "remove_image": "1"}).status_code, 302)
            category.refresh_from_db()
            self.assertEqual(category.display_image_url, "")
            other.refresh_from_db()
            self.assertEqual(other.display_image_url, media.file.url)
            remote = "https://example.test/box.png"
            self.assertEqual(self.client.post(edit, {"name": category.name, "image_url": remote}).status_code, 302)
            category.refresh_from_db()
            self.assertEqual(category.display_image_url, remote)
            with patch("django.core.files.storage.FileSystemStorage._save", side_effect=MediaProviderError("Проверочное сообщение")):
                response = self.client.post(edit, {"name": "Несохранённое название", "image": self.png()})
            self.assertContains(response, "Проверочное сообщение")
            self.assertContains(response, "Несохранённое название")
            category.refresh_from_db()
            self.assertEqual(category.display_image_url, remote)

    def test_product_editor_saves_existing_promotion_relationship(self):
        category = Category.objects.create(name="Товары для акций")
        first = Promotion.objects.create(title="Первая акция")
        second = Promotion.objects.create(title="Вторая акция")
        data = {"category": category.pk, "name": "Коробка", "price": "42", "unit": "шт",
                "min_quantity": 1, "stock_quantity": 10, "availability": "in_stock", "status": "published",
                "promotion_selection": "1", "promotions": [first.pk, second.pk]}
        response = self.client.post(reverse("management_product_new"), data)
        self.assertEqual(response.status_code, 302, getattr(response.context, "form", None))
        product = Product.objects.get(name="Коробка")
        self.assertEqual(set(product.promotions.all()), {first, second})
        first.products.remove(product)
        edit = reverse("management_product_edit", args=[product.pk])
        form = self.client.get(edit).context["form"]
        self.assertEqual(form.initial["promotions"], [second.pk])
        data.pop("promotions")
        self.assertEqual(self.client.post(edit, data).status_code, 302)
        self.assertFalse(product.promotions.exists())
        self.assertEqual(Promotion.objects.filter(pk__in=[first.pk, second.pk]).count(), 2)
        product.refresh_from_db()
        self.assertEqual(product.price, 42)

    def test_promotion_reuses_products_without_changing_price(self):
        category = Category.objects.create(name="Акционные коробки")
        product = Product.objects.create(category=category, name="Коробка", sku="PROMO-42", price=42, status=Product.STATUS_PUBLISHED)
        hidden = Product.objects.create(category=category, name="Черновик", price=20)
        response = self.client.post(reverse("management_promotion_new"), {
            "title": "Акция", "conditions": "Условия поставки", "is_active": "on", "sort_order": 0,
            "products": [product.pk, hidden.pk],
        })
        self.assertEqual(response.status_code, 302)
        promotion = Promotion.objects.get(title="Акция")
        self.assertEqual(promotion.products.count(), 2)
        other = Promotion.objects.create(title="Вторая акция")
        other.products.add(product)
        self.assertEqual(product.promotions.count(), 2)
        self.client.logout()
        detail = reverse("promotion_detail", args=[promotion.pk])
        response = self.client.get(detail)
        self.assertContains(response, "Условия поставки")
        self.assertContains(response, "PROMO-42")
        self.assertNotContains(response, "Черновик")
        self.assertContains(response, "42.00")
        future = Promotion.objects.create(title="Будущая", starts_at=timezone.now() + timedelta(days=1))
        expired = Promotion.objects.create(title="Завершённая", ends_at=timezone.now() - timedelta(days=1))
        for inactive in (future, expired):
            self.assertEqual(self.client.get(reverse("promotion_detail", args=[inactive.pk])).status_code, 404)
        product.refresh_from_db()
        self.assertEqual(product.price, 42)

    def test_legal_preview_and_publish_use_sanitized_content(self):
        page, _ = PageContent.objects.update_or_create(
            page="privacy", defaults={"is_visible": True, "content_text": "Старое дополнение", "document_html": ""},
        )
        public = reverse("document_page", args=["privacy"])
        self.assertContains(self.client.get(public), "Какие данные мы собираем")
        edit = reverse("management_page_edit", args=[page.pk])
        initial = self.client.get(edit).context["form"]["document_html"].value()
        self.assertIn("Какие данные мы собираем", initial)
        self.assertIn("Старое дополнение", initial)
        data = {
            "page": "privacy", "is_visible": "on", "title": "Текст владельца",
            "footer_label": "Политика магазина", "seo_title": "Заголовок поиска", "meta_description": "Описание документа",
            "content_text": "Старое дополнение",
            "document_html": (
                '<h2>Обновление</h2><ul><li><a href="/contacts/">Контакты</a></li></ul>'
                '<a href="https://[invalid">Ссылка</a><script>alert(1)</script>'
                '<p style="text-align:center;position:fixed">Текст</p>'
                '<ol start="3"><li>Первый<ol><li>Вложенный</li></ol></li></ol>'
                '<table><tr><td colspan="2" onclick="alert(1)">Данные</td></tr></table>'
            ),
        }
        response = self.client.post(edit, {**data, "preview_document": "1"})
        self.assertContains(response, "<h2>Обновление</h2>", html=True)
        self.assertContains(response, 'class="document-preview-banner"')
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        page.refresh_from_db()
        self.assertEqual(page.document_html, "")
        self.assertEqual(self.client.post(edit, data).status_code, 302)
        response = self.client.get(public)
        self.assertContains(response, "<h1>Текст владельца</h1>", html=True)
        self.assertContains(response, "<h2>Обновление</h2>", html=True)
        self.assertNotContains(response, "alert(1)")
        self.assertNotContains(response, "position:fixed")
        self.assertContains(response, 'style="text-align: center"')
        self.assertContains(response, '<ol start="3">')
        self.assertContains(response, '<td colspan="2">Данные</td>', html=True)
        self.assertContains(response, "<title>Заголовок поиска</title>", html=True)
        self.assertContains(response, "Политика магазина")
        self.assertNotContains(response, "Какие данные мы собираем")
        page.refresh_from_db()
        self.assertEqual(page.content_text, "Старое дополнение")

    def test_legal_permissions_and_draft_visibility(self):
        page = PageContent.objects.get(page="offer")
        url = reverse("document_page", args=["offer"])
        edit = reverse("management_page_edit", args=[page.pk])
        listing = reverse("management_pages") + "?section=legal"
        self.assertContains(self.client.get(listing), "Политика конфиденциальности")
        data = {"title": "Оферта", "footer_label": "Оферта магазина", "document_html": "<p>Черновик</p>"}
        self.assertRedirects(self.client.post(edit, {**data, "action": "continue"}), edit)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("home")), 'href="' + url + '"')
        self.assertEqual(self.client.post(edit, data).status_code, 302)
        staff = get_user_model().objects.create_user("viewer", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(listing).status_code, 403)
        self.assertEqual(self.client.post(edit, {**data, "preview_document": "1"}).status_code, 403)
        page.refresh_from_db()
        self.assertEqual(page.document_html, "<p>Черновик</p>")
