from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse

from .models import Product


class CatalogMigrationTests(TransactionTestCase):
    def test_existing_store_data_survives_upgrade(self):
        old_target = [('store', '0022_seed_site_navigation')]
        new_target = [('store', '0023_catalog_hierarchy_pricing_dimensions')]
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        self.addCleanup(self.restore_latest)
        apps = executor.loader.project_state(old_target).apps
        category = apps.get_model('store', 'Category').objects.create(name='Существующая категория', slug='legacy')
        product = apps.get_model('store', 'Product').objects.create(category_id=category.pk, name='Существующий товар', slug='legacy-product', price=Decimal('123.45'), stock_quantity=42, status='published', h1='Старый H1')
        photo = apps.get_model('store', 'ProductImage').objects.create(product_id=product.pk, image_url='https://example.test/legacy.jpg')
        user = apps.get_model('auth', 'User').objects.create(username='legacy-buyer')
        cart = apps.get_model('store', 'CartItem').objects.create(user_id=user.pk, product_id=product.pk, quantity=3)
        order = apps.get_model('store', 'Order').objects.create(user_id=user.pk, number='LEGACY-1', full_name='Покупатель', phone='123', email='legacy@example.test', total=Decimal('370.35'))
        item = apps.get_model('store', 'OrderItem').objects.create(order_id=order.pk, product_id=product.pk, product_name=product.name, quantity=3, price=Decimal('123.45'), line_total=Decimal('370.35'))
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        apps = executor.loader.project_state(new_target).apps
        current = apps.get_model('store', 'Product').objects.get(pk=product.pk)
        self.assertEqual(current.price, Decimal('123.45'))
        self.assertEqual(current.stock_quantity, 42)
        self.assertEqual(current.h1, 'Старый H1')
        self.assertEqual(current.status, 'published')
        self.assertEqual(current.vat_rate, Decimal('22.00'))
        self.assertIsNone(current.cost_price)
        self.assertIsNone(current.length_mm)
        self.assertFalse(current.is_special)
        self.assertIsNone(apps.get_model('store', 'Category').objects.get(pk=category.pk).parent_id)
        self.assertEqual(apps.get_model('store', 'CartItem').objects.get(pk=cart.pk).quantity, 3)
        self.assertEqual(apps.get_model('store', 'ProductImage').objects.get(pk=photo.pk).image_url, photo.image_url)
        old_item = apps.get_model('store', 'OrderItem').objects.get(pk=item.pk)
        self.assertEqual(old_item.price, Decimal('123.45'))
        self.assertIsNone(old_item.vat_rate)
        self.assertIsNone(old_item.weight_kg)
        self.assertIsNone(old_item.volume_m3)
        self.assertEqual(apps.get_model('store', 'Order').objects.get(pk=order.pk).total, Decimal('370.35'))

    @staticmethod
    def restore_latest():
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL schema regression")
    def test_variant_sort_order_upgrade_and_schema_repair(self):
        old_target = [("store", "0041_customerprofile_retail_coefficient_and_more")]
        field_target = [("store", "0042_product_variant_sort_order")]
        self.addCleanup(self.restore_latest)
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        apps = executor.loader.project_state(old_target).apps
        category = apps.get_model("store", "Category").objects.create(name="Legacy", slug="legacy")
        legacy_model = apps.get_model("store", "Product")
        product = legacy_model.objects.create(
            category=category, name="Legacy product", slug="legacy-product", price=Decimal("123.45"),
            status="published",
        )
        MigrationExecutor(connection).migrate(field_target)
        self.assertEqual(Product.objects.get(pk=product.pk).variant_sort_order, 0)
        Product.objects.filter(pk=product.pk).update(variant_sort_order=17)
        self.restore_latest()
        self.assertEqual(Product.objects.get(pk=product.pk).variant_sort_order, 17)
        MigrationExecutor(connection).migrate(field_target)

        # Reproduce migration history that says 0042 ran while the column is missing.
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE store_product DROP COLUMN variant_sort_order")
        self.restore_latest()
        restored = Product.objects.get(pk=product.pk)
        self.assertEqual(restored.variant_sort_order, 0)
        self.assertEqual(restored.price, Decimal("123.45"))
        self.assertEqual(restored.category_id, category.pk)
        # A previous deployment can still insert without specifying the new column.
        legacy = legacy_model.objects.create(category=category, name="Earlier code", slug="older", price=1)
        self.assertEqual(Product.objects.get(pk=legacy.pk).variant_sort_order, 0)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.client.force_login(get_user_model().objects.create_user("migration-staff", is_staff=True))
        self.assertEqual(self.client.get(reverse("management_dashboard")).status_code, 200)
