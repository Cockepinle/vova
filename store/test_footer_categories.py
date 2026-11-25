from urllib.parse import quote

from django.test import TestCase
from django.urls import reverse

from .models import Category


class FooterCategoriesTests(TestCase):
    def test_published_tree_is_nested_and_updates_when_categories_change(self):
        root = Category.objects.create(name="Основная ветка")
        child = Category.objects.create(name="Подкатегория", parent=root)
        leaf = Category.objects.create(name="Третий уровень", parent=child)
        hidden = Category.objects.create(name="Скрытая ветка", is_active=False)
        hidden_child = Category.objects.create(name="В скрытой ветке", parent=hidden)
        url = reverse("contacts")

        response = self.client.get(url)
        roots = response.context["footer_categories"]
        self.assertEqual([node["category"] for node in roots], [root])
        self.assertEqual(roots[0]["children"][0]["children"][0]["category"], leaf)
        self.assertContains(response, f'aria-controls="footer-category-{root.pk}"')
        self.assertContains(response, f'?category={quote(leaf.slug)}')
        self.assertNotContains(response, hidden_child.name)

        hidden.is_active = True
        hidden.save(update_fields=["is_active"])
        response = self.client.get(url)
        self.assertContains(response, hidden_child.name)
        self.assertContains(response, f'aria-controls="footer-category-{hidden.pk}"')
