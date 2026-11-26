from io import BytesIO
from unittest.mock import patch
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Category, Employee, PageContent, Product, ProductImage, SiteMedia, SiteSettings


def image_file(name, image_format="PNG"):
    buffer = BytesIO()
    Image.new("RGB", (24, 24), "navy").save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")


class MediaUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user("media-manager", is_staff=True)

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=directory.name))
        self.client.force_login(self.staff)
        self.upload_url = reverse("management_media_upload_api")
        self.library_url = reverse("management_media")

    def upload(self, file):
        return self.client.post(self.upload_url, {"title": "Изображение", "file": file, "kind": "image"})

    def test_supported_formats_remain_available_after_reopening(self):
        for extension, image_format in [("png", "PNG"), ("jpg", "JPEG"), ("webp", "WEBP"), ("gif", "GIF"), ("ico", "ICO")]:
            with self.subTest(extension=extension):
                upload = image_file(f"photo.{extension}", image_format)
                original = upload.read()
                upload.seek(0)
                response = self.upload(upload)
                self.assertEqual(response.status_code, 200, response.content)
                item = response.json()
                stored = SiteMedia.objects.get(pk=item["id"])
                self.assertEqual(stored.original_filename, f"photo.{extension}")
                with stored.file.open("rb") as saved:
                    self.assertEqual(saved.read(), original)
                self.assertContains(self.client.get(self.library_url), f'href="{item["url"]}"')

    def test_library_upload_returns_card_and_persists_filename_separately_from_title(self):
        response = self.client.post(self.upload_url, {
            "file": image_file("original.png"), "title": "Другое название", "library": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-file-name="original.png"', response.json()["html"])
        self.assertContains(self.client.get(self.library_url), 'data-file-name="original.png"')

    def test_rejects_svg_wrong_extension_corrupt_images_and_large_files(self):
        for upload in (
            SimpleUploadedFile("image.svg", b"<svg/>"),
            image_file("image.webp"),
            SimpleUploadedFile("corrupt.png", b"invalid"),
        ):
            with self.subTest(name=upload.name):
                self.assertEqual(self.upload(upload).status_code, 400)
        with override_settings(CMS_UPLOAD_MAX_BYTES=64):
            self.assertEqual(self.upload(image_file("large.png")).status_code, 400)
        self.assertFalse(SiteMedia.objects.exists())

    def test_picker_reports_session_permissions_csrf_and_storage_errors(self):
        anonymous = Client(enforce_csrf_checks=True)
        self.assertEqual(anonymous.post(self.upload_url).status_code, 401)
        customer = get_user_model().objects.create_user("media-customer")
        anonymous.force_login(customer)
        self.assertEqual(anonymous.post(self.upload_url).status_code, 403)
        anonymous.force_login(self.staff)
        csrf_failure = anonymous.post(self.upload_url)
        self.assertEqual(csrf_failure.status_code, 403)
        self.assertIn("подтвердить сессию", csrf_failure.json()["error"])
        with patch("store.models.SiteMedia.save", side_effect=OSError("private storage detail")):
            with self.assertLogs("store.cms.content", level="ERROR"):
                response = self.upload(image_file("photo.png"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "Не удалось сохранить файл на сервере")
        self.assertFalse(SiteMedia.objects.exists())

    def test_cloudinary_upload_preserves_link_and_exposes_safe_provider_errors(self):
        from cloudinary.exceptions import AuthorizationRequired
        from django.conf import settings
        from django.core.files.storage import storages

        cloud = "cloudinary://fake-key:fake-secret@test-cloud"
        storage_settings = {
            **settings.STORAGES, "default": {"BACKEND": "store.media_storage.StoreCloudinaryStorage"},
        }
        with patch.dict("os.environ", CLOUDINARY_URL=cloud):
            from cloudinary import config
            with patch.object(config(), "cloud_name", "test-cloud"), override_settings(
                CLOUDINARY_STORAGE={"PREFIX": "media/"}, STORAGES=storage_settings,
            ):
                with patch("store.media_storage.uploader.upload") as provider:
                    provider.side_effect = AuthorizationRequired("technical detail")
                    with self.assertLogs("store.cms.content", level="ERROR") as logs:
                        rejected = self.upload(image_file("pngtree-empty-box-open-box-png-image_20409962.png"))
                    self.assertEqual(rejected.status_code, 503)
                    self.assertIn("CLOUDINARY_URL", rejected.json()["error"])
                    self.assertNotIn("technical detail", rejected.json()["error"])
                    self.assertIn("technical detail", "\n".join(logs.output))

                    def save_on_provider(content, **options):
                        self.assertEqual(content.read(8), b"\x89PNG\r\n\x1a\n")
                        self.assertEqual(options["resource_type"], "image")
                        self.assertTrue(options["filename"].endswith(".png"))
                        return {"public_id": options["public_id"], "format": "png"}

                    provider.side_effect = save_on_provider
                    accepted = self.upload(image_file("pngtree-empty-box-open-box-png-image_20409962.png"))
                    self.assertEqual(accepted.status_code, 200, accepted.content)
                    media = SiteMedia.objects.get(pk=accepted.json()["id"])
                    self.assertTrue(media.file.name.startswith("media/site_media/"))
                    self.assertEqual(type(storages["default"])().url(media.file.name), accepted.json()["url"])
                    self.assertContains(self.client.get(self.library_url), accepted.json()["url"])

    def test_attachment_rejects_content_disguised_by_extension(self):
        for extension in ("pdf", "mp4", "webm"):
            with self.subTest(extension=extension):
                response = self.client.post(self.upload_url, {
                    "title": "Invalid attachment", "kind": "attachment",
                    "file": SimpleUploadedFile(f"fake.{extension}", b"<html>Invalid</html>"),
                })
                self.assertEqual(response.status_code, 400)
        self.assertFalse(SiteMedia.objects.exists())

    def test_missing_file_has_placeholder_and_can_be_replaced_without_losing_links(self):
        media = SiteMedia.objects.create(title="Отсутствующий файл", file="site_media/missing.png")
        category = Category.objects.create(name="Медиа")
        product = Product.objects.create(category=category, name="Коробка", price=100, status=Product.STATUS_PUBLISHED)
        ProductImage.objects.create(product=product, media=media, is_primary=True)
        employee = Employee.objects.create(name="Менеджер", role="Продажи", image=media.file.name, status=Employee.STATUS_PUBLISHED)
        site = SiteSettings.get_solo()
        site.logo_media = media
        site.save()
        page = PageContent.objects.get(page=PageContent.PAGE_HOME)
        page.is_visible = True
        page.hero_media = media
        page.hero_image_alt = "Главное изображение"
        page.published_structure = [{"id": "test-banner", "type": "banner", "content": {"src": media.file.url}}]
        page.published_design = {"append_to_page": True}
        page.save()
        response = self.client.get(self.library_url)
        self.assertContains(response, "store/images/no-photo.svg")
        self.assertNotContains(response, 'href="/media/site_media/missing.png"')
        self.assertEqual(self.client.get(reverse("management_media_api")).json()["items"], [])

        replace_url = reverse("management_media_replace", args=[media.pk])
        invalid = self.client.post(replace_url, {"title": "Изменённое название", "file": image_file("wrong.webp")})
        self.assertContains(invalid, 'value="Изменённое название"')
        self.assertContains(invalid, "не соответствует расширению")
        response = self.client.post(replace_url, {
            "title": "Изменённое название", "alt": "Баннер", "file": image_file("new.webp", "WEBP"),
        })
        self.assertRedirects(response, self.library_url)
        media.refresh_from_db()
        employee.refresh_from_db()
        page.refresh_from_db()
        self.assertEqual(product.display_image_url, media.file.url)
        self.assertEqual(employee.display_image_url, media.file.url)
        self.assertEqual(SiteSettings.get_solo().logo_url, media.file.url)
        self.assertEqual(page.hero_url, media.file.url)
        self.assertEqual(page.published_structure[0]["content"]["src"], media.file.url)
        self.assertContains(self.client.get(reverse("team")), media.file.url)
        self.assertContains(self.client.get(reverse("product_detail", args=[product.slug])), media.file.url)
        home = self.client.get(reverse("home"))
        self.assertContains(home, f'<img class="brand-image" src="{media.file.url}"')
        self.assertContains(home, f'<img src="{media.file.url}" alt="Баннер">')
        self.assertContains(home, f'<picture class="page-hero-media"><img src="{media.file.url}"')
