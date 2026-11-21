from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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
                with stored.file.open("rb") as saved:
                    self.assertEqual(saved.read(), original)
                self.assertContains(self.client.get(self.library_url), f'href="{item["url"]}"')

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
