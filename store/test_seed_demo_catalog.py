from django.core.management import call_command
from django.test import TestCase

from .models import Category, Product


class DemoCatalogCommandTests(TestCase):
    def test_seed_is_repeatable_and_creates_box_hierarchy(self):
        call_command("seed_demo_catalog", verbosity=0)
        call_command("seed_demo_catalog", verbosity=0)

        self.assertEqual(Category.objects.filter(parent__isnull=True).count(), 5)
        self.assertEqual(Category.objects.filter(parent__isnull=False).count(), 10)
        self.assertEqual(Product.objects.filter(sku__startswith="DEMO-").count(), 15)
        self.assertEqual(
            Product.objects.filter(
                sku__startswith="DEMO-",
                status=Product.STATUS_PUBLISHED,
                availability=Product.AVAILABILITY_PREORDER,
                stock_quantity=0,
            ).count(),
            15,
        )
        self.assertTrue(
            Category.objects.get(slug="corrugated-boxes")
            .children.filter(slug="three-layer-boxes")
            .exists()
        )
