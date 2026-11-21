import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .cms.content import media_usage, sanitize_builder_structure, update_builder_media_references
from .models import PageContent, SiteMedia


class PageBuilderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser(
            "builder-admin",
            "builder@example.test",
            "test-password",
        )

    def setUp(self):
        self.home, _ = PageContent.objects.get_or_create(
            page=PageContent.PAGE_HOME,
            defaults={"title": "Главная", "is_visible": True},
        )
        self.home.is_visible = True
        self.home.save(update_fields=["is_visible"])
        self.client.force_login(self.staff)

    def post_structure(self, structure, action="draft"):
        return self.client.post(
            reverse("management_page_builder_save", args=[self.home.pk]),
            data=json.dumps({"action": action, "structure": structure, "design": {}}),
            content_type="application/json",
        )

    def test_html_and_links_are_sanitized_before_storage_and_rendering(self):
        structure = sanitize_builder_structure(
            [
                {
                    "id": "unsafe",
                    "type": "html",
                    "content": {
                        "html": (
                            '<p onclick="run()">Safe <script>alert(1)</script></p>'
                            '<a href="javascript:alert(1)">link</a>'
                            '<a href="https://example.test/">external</a>'
                        )
                    },
                },
                {
                    "id": "unsafe-link",
                    "type": "button",
                    "content": {"url": "javascript:alert(1)", "text": "Click"},
                },
            ]
        )
        rendered_html = structure[0]["content"]["html"]
        self.assertNotIn("<script", rendered_html)
        self.assertNotIn("onclick", rendered_html)
        self.assertNotIn("javascript:", rendered_html)
        self.assertIn('href="https://example.test/"', rendered_html)
        self.assertEqual(structure[1]["content"]["url"], "")

        duplicate_ids = sanitize_builder_structure(
            [
                {"id": "same", "type": "section", "children": [
                    {"id": "same", "type": "heading", "content": {"text": "Вложенный"}}
                ]},
                {"id": "same", "type": "text", "content": {"text": "Второй"}},
            ]
        )
        self.assertEqual(
            [duplicate_ids[0]["id"], duplicate_ids[0]["children"][0]["id"], duplicate_ids[1]["id"]],
            ["same", "same-1", "same-2"],
        )
        self.assertEqual(
            len(sanitize_builder_structure([{"type": "text"}] * 400)),
            300,
        )

    def test_draft_does_not_change_public_page_until_publish(self):
        structure = [
            {
                "id": "homepage-title",
                "type": "heading",
                "content": {"text": "Черновой заголовок", "level": "h1"},
            }
        ]
        response = self.post_structure(structure)
        self.assertEqual(response.status_code, 200)
        self.home.refresh_from_db()
        self.assertEqual(self.home.published_structure, [])
        self.assertEqual(self.home.draft_structure[0]["content"]["text"], "Черновой заголовок")
        self.assertNotContains(self.client.get(reverse("home")), "Черновой заголовок")

        response = self.post_structure(structure, action="publish")
        self.assertEqual(response.status_code, 200)
        self.home.refresh_from_db()
        self.assertEqual(self.home.published_structure[0]["content"]["text"], "Черновой заголовок")
        self.assertContains(self.client.get(reverse("home")), "Черновой заголовок")
        self.assertContains(self.client.get(reverse("home")), "Категории коробок")
        self.assertContains(self.client.get(reverse("home")), "Популярные коробки")

    def test_hidden_custom_page_can_preview_draft_only_for_staff(self):
        page = PageContent.objects.create(
            page="custom-preview",
            is_custom=True,
            slug="builder-preview",
            title="Скрытая страница",
            is_visible=False,
            draft_structure=[
                {
                    "id": "preview-title",
                    "type": "heading",
                    "content": {"text": "Только в предпросмотре"},
                }
            ],
        )
        preview_url = reverse("custom_page", args=[page.slug])
        self.assertEqual(self.client.get(preview_url).status_code, 404)
        response = self.client.get(preview_url, {"preview": "1", "preview_builder": "1"})
        self.assertContains(response, "Только в предпросмотре")

        self.client.logout()
        self.assertEqual(
            self.client.get(preview_url, {"preview": "1", "preview_builder": "1"}).status_code,
            404,
        )

    def test_unknown_save_action_is_rejected(self):
        response = self.post_structure([], action="delete")
        self.assertEqual(response.status_code, 400)

    def test_explicitly_empty_draft_stays_empty_when_editor_reopens(self):
        response = self.post_structure([])
        self.assertEqual(response.status_code, 200)
        old_url = reverse("management_page_builder", args=[self.home.pk])
        blocks_url = reverse("management_page_blocks", args=[self.home.pk])
        self.assertRedirects(self.client.get(old_url), blocks_url)
        self.assertContains(self.client.get(blocks_url), "Информационные блоки")
        self.home.refresh_from_db()
        self.assertEqual(self.home.draft_structure, [])

    def test_media_in_builder_is_protected_and_replacement_updates_its_url(self):
        media = SiteMedia.objects.create(
            title="Изображение конструктора",
            file="site_media/builder-image.jpg",
        )
        old_url = media.file.url
        self.home.draft_structure = [
            {
                "id": "image",
                "type": "image",
                "content": {
                    "url": old_url,
                    "media_id": media.pk,
                    "alt": "До замены",
                },
            }
        ]
        self.home.save(update_fields=["draft_structure"])

        self.assertTrue(any("Изображение блока страницы" in item for item in media_usage(media)))
        media.file = "site_media/builder-image-new.jpg"
        media.save(update_fields=["file"])
        update_builder_media_references(media, old_url)

        self.home.refresh_from_db()
        self.assertEqual(self.home.draft_structure[0]["content"]["url"], media.file.url)
        self.assertEqual(self.home.draft_structure[0]["content"]["alt"], media.alt)


    def test_structured_edit_publish_and_restore_preserve_nested_content_and_design(self):
        self.home.published_structure = [{
            "id": "group", "type": "section", "extra": {"legacy": [1, 2]},
            "children": [
                {"id": "text", "type": "text", "content": {"text": "До правки", "custom": ["keep"]}},
                {"id": "other", "type": "custom-legacy", "content": {"text": "Сохранённый блок"}},
            ],
        }]
        self.home.published_design = {"theme": {"original": True}}
        self.home.save()
        url = reverse("management_page_blocks", args=[self.home.pk])

        editor = self.client.get(url, {"block": "0.0"})
        self.assertContains(editor, "До правки")
        self.assertNotContains(editor, "page-builder.js")
        self.assertEqual(self.home.builder_revisions.count(), 0)
        initial_version = self.home.updated_at.isoformat()
        self.assertEqual(self.client.post(url, {
            "version": initial_version, "action": "edit", "block": "0.0",
            "content-text": "Новая редакция", "visibility-fields": "1", "hidden_mobile": "on",
        }).status_code, 302)
        self.home.refresh_from_db()
        self.assertEqual(self.home.draft_structure[0]["children"][0]["content"]["custom"], ["keep"])
        self.assertEqual(self.home.draft_design, self.home.published_design)
        self.assertContains(self.client.get(reverse("home")), "До правки")
        self.assertContains(self.client.get(reverse("home"), {"preview_builder": "1"}), "Новая редакция")
        draft_revision = self.home.builder_revisions.get(label="Черновик")
        self.client.post(url, {"version": initial_version, "action": "publish"})
        self.assertContains(self.client.get(reverse("home")), "До правки")
        self.client.post(url, {"version": self.home.updated_at.isoformat(), "action": "publish"})
        self.home.refresh_from_db()
        self.assertEqual(self.home.published_structure[0]["extra"], {"legacy": [1, 2]})
        self.assertContains(self.client.get(reverse("home")), "Новая редакция")
        self.assertContains(self.client.get(reverse("home")), 'data-hidden-mobile="true"')
        self.assertContains(self.client.get(reverse("home")), "Сохранённый блок")
        self.client.post(url, {
            "version": self.home.updated_at.isoformat(), "action": "delete", "block": "0.1",
        })
        self.home.refresh_from_db()
        self.assertEqual(len(self.home.draft_structure[0]["children"]), 1)
        self.client.post(url, {
            "version": self.home.updated_at.isoformat(), "action": "restore", "revision": draft_revision.pk,
        })
        self.home.refresh_from_db()
        self.assertEqual(self.home.draft_structure, self.home.published_structure)

    def test_structured_image_keeps_media_reference_after_publication(self):
        media = SiteMedia.objects.create(title="Обложка", file="site_media/cover.png")
        url = reverse("management_page_blocks", args=[self.home.pk])
        self.client.post(url, {"version": self.home.updated_at.isoformat(), "action": "add", "kind": "image"})
        self.home.refresh_from_db()
        response = self.client.post(url, {
            "version": self.home.updated_at.isoformat(), "action": "edit", "block": "0",
            "replace-image": media.pk, "content-alt": "Новая обложка",
        })
        self.assertEqual(response.status_code, 302)
        self.home.refresh_from_db()
        self.client.post(url, {"version": self.home.updated_at.isoformat(), "action": "publish"})
        self.home.refresh_from_db()
        self.assertEqual(self.home.published_structure[0]["content"]["media_id"], media.pk)
        self.assertContains(self.client.get(reverse("home")), media.file.url)
        self.assertContains(self.client.get(reverse("home")), "Новая обложка")
