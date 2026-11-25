from decimal import Decimal
from io import BytesIO
from tempfile import TemporaryDirectory
from urllib.parse import quote, unquote
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .cms_forms import AttributeDefinitionForm, CategoryForm, DynamicProductFieldsForm, ProductForm
from .excel import BASE_COLUMNS, export_products, import_products
from .models import (
    AttributeDefinition, CartItem, Category, CustomerPrice, CustomerProfile, FavoriteItem, Order, OrderItem,
    Product, ProductAttribute, ProductImage, SiteMedia, SiteSettings, VariantGroup,
)


class CatalogFeaturesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_superuser('manager', 'staff@example.test', 'test-password')
        cls.customer = get_user_model().objects.create_user('buyer@example.test', 'buyer@example.test', 'test-password')
        cls.other = get_user_model().objects.create_user('other@example.test')
        cls.root = Category.objects.create(name='Гофрокартон')
        cls.child = Category.objects.create(name='Коробки под пиццу', parent=cls.root)
        cls.leaf = Category.objects.create(name='Большие коробки', parent=cls.child)
        cls.product = Product.objects.create(
            category=cls.leaf, name='Коробка 400', description='Прочная упаковка',
            price=Decimal('120.35'), cost_price=Decimal('60.10'), status='published',
            min_quantity=2, stock_quantity=100, is_hit=True, is_new=True, is_special=True,
            length_mm=Decimal('400'), width_mm=Decimal('300'), height_mm=Decimal('200'),
            weight_kg=Decimal('0.125'), image_url='https://example.test/box.jpg',
        )
        cls.special = CustomerPrice.objects.create(user=cls.customer, product=cls.product, price=Decimal('91.27'))

    def post_json(self, name, payload):
        return self.client.post(reverse(name), payload, content_type='application/json')

    def product_payload(self, **overrides):
        data = {
            'category': self.leaf.pk, 'name': self.product.name, 'slug': self.product.slug,
            'price': '120.35', 'unit': 'шт', 'min_quantity': 2, 'stock_quantity': 100,
            'availability': 'in_stock', 'status': 'published', 'vat_rate': '22.00',
        }
        data.update(overrides)
        return data

    def test_category_tree_serializes_parent_and_depth(self):
        data = self.client.get(reverse('api_categories')).json()['categories']
        leaf = next(item for item in data if item['id'] == str(self.leaf.pk))
        self.assertEqual(leaf['depth'], 2)
        self.assertEqual(leaf['parent_id'], str(self.child.pk))
        self.assertEqual(leaf['path'], 'Гофрокартон / Коробки под пиццу / Большие коробки')
        products = self.client.get(reverse('api_products'), {'category': self.leaf.slug}).json()['products']
        self.assertEqual([item['id'] for item in products], [str(self.product.pk)])

    def test_category_page_shows_children_and_only_directly_linked_products(self):
        root_product = Product.objects.create(
            category=self.root, name='Коробка верхнего уровня', price=20, status='published',
        )
        child_product = Product.objects.create(
            category=self.child, name='Коробка среднего уровня', price=30, status='published',
        )
        root_response = self.client.get(reverse('catalog'), {'category': self.root.slug})
        self.assertContains(root_response, self.child.name)
        self.assertContains(root_response, reverse('catalog') + '?category=' + quote(self.child.slug))
        self.assertContains(root_response, 'Подробнее')
        self.assertContains(root_response, root_product.name)
        self.assertNotContains(root_response, child_product.name)
        self.assertNotContains(root_response, self.product.name)
        self.assertContains(root_response, reverse('catalog') + '?category=' + quote(self.root.slug))

        child_response = self.client.get(reverse('catalog'), {'category': self.child.slug})
        self.assertContains(child_response, self.leaf.name)
        self.assertContains(child_response, child_product.name)
        self.assertNotContains(child_response, root_product.name)
        self.assertNotContains(child_response, self.product.name)
        self.assertContains(child_response, reverse('catalog') + '?category=' + quote(self.root.slug))

        child_api_products = self.client.get(
            reverse('api_products'), {'category': self.child.slug},
        ).json()['products']
        self.assertEqual([item['id'] for item in child_api_products], [str(child_product.pk)])

        leaf_response = self.client.get(reverse('catalog'), {'category': self.leaf.slug})
        self.assertContains(leaf_response, self.product.name)
        self.assertNotContains(leaf_response, root_product.name)
        self.assertNotContains(leaf_response, child_product.name)
        self.assertContains(leaf_response, self.child.name)
        self.assertContains(leaf_response, self.root.name)
        self.assertContains(leaf_response, reverse('catalog') + '?category=' + quote(self.root.slug))

    def test_sidebar_renders_nested_accordion_and_expands_active_ancestry(self):
        response = self.client.get(reverse('catalog'), {'category': self.leaf.slug})
        tree = response.context['category_tree']
        root = next(item for item in tree if item['id'] == str(self.root.pk))
        child = root['children'][0]
        self.assertEqual(root['name'], self.root.name)
        self.assertTrue(root['is_expanded'])
        self.assertEqual(child['name'], self.child.name)
        self.assertTrue(child['is_expanded'])
        self.assertEqual(child['children'][0]['name'], self.leaf.name)
        self.assertContains(response, f'aria-label="Скрыть подкатегории: {self.root.name}"')
        self.assertContains(response, f'aria-label="Скрыть подкатегории: {self.child.name}"')
        self.assertContains(response, f'id="catalog-category-children-desktop-{self.root.pk}"')
        self.assertContains(response, f'id="catalog-category-children-mobile-{self.root.pk}"')
        self.assertNotContains(response, f'подкатегории: {self.leaf.name}')
        self.assertNotContains(response, f'{self.root.name} / {self.child.name}')

    def test_management_can_start_subcategory_from_parent_row(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('management_category_new'), {'parent': self.root.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.context['form']['parent'].value()), str(self.root.pk))
        self.assertContains(response, 'Новая подкатегория')
        self.assertContains(self.client.get(reverse('management_categories')), f'?parent={self.root.pk}')

    def test_customer_prices_can_be_saved_in_place(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('management_product_edit', args=[self.product.pk]), {
            'save_customer_prices': '1',
            'price_customers': [str(self.other.pk)],
            f'customer_price_{self.other.pk}': '77,50',
        })
        self.assertRedirects(response, reverse('management_product_edit', args=[self.product.pk]))
        self.assertFalse(CustomerPrice.objects.filter(product=self.product, user=self.customer).exists())
        self.assertEqual(CustomerPrice.objects.get(product=self.product, user=self.other).price, Decimal('77.50'))

    def test_management_forms_explain_product_and_category_seo(self):
        self.client.force_login(self.staff)
        product_response = self.client.get(reverse('management_product_edit', args=[self.product.pk]))
        self.assertContains(product_response, 'SEO страницы товара')
        self.assertContains(product_response, 'name="seo_title"')
        category_response = self.client.get(reverse('management_category_edit', args=[self.root.pk]))
        self.assertContains(category_response, 'SEO категории')
        self.assertContains(category_response, 'name="meta_description"')

    def test_keywords_search_is_hidden_and_case_insensitive(self):
        self.product.keywords = 'ПИЦЦА, белая коробка'
        self.product.save(update_fields=['keywords'])
        response = self.client.get(reverse('catalog'), {'q': 'пицца'})
        self.assertContains(response, self.product.name)
        self.assertNotContains(response, 'ПИЦЦА, белая коробка')
        api = self.client.get(reverse('api_products'), {'q': 'БЕЛАЯ'}).json()['products']
        self.assertEqual([item['id'] for item in api], [str(self.product.pk)])

    def test_search_matches_name_sku_description_and_hidden_keywords(self):
        searchable = Product.objects.create(
            category=self.leaf,
            name='Почтовый пакет',
            sku='PACK-321',
            description='Пузырчатая плёнка для посылок',
            keywords='запасная упаковка',
            price=25,
            status=Product.STATUS_PUBLISHED,
        )
        for query in ('  ПОЧТОВЫЙ   ПАКЕТ ', 'pack-321', 'ПЛЁНКА', 'ЗАПАСНАЯ'):
            with self.subTest(query=query):
                products = self.client.get(
                    reverse('api_products'),
                    {'q': query},
                ).json()['products']
                self.assertIn(str(searchable.pk), [item['id'] for item in products])
        response = self.client.get(reverse('catalog'), {'q': 'запасная'})
        self.assertNotContains(response, 'запасная упаковка')

    def test_search_is_global_from_category_unless_scope_is_selected(self):
        elsewhere = Product.objects.create(
            category=self.root,
            name='Коробка для отправки',
            sku='SHIP-42',
            description='Плотный гофрокартон',
            price=65,
            status=Product.STATUS_PUBLISHED,
        )
        global_response = self.client.get(reverse('catalog'), {
            'category': self.leaf.slug,
            'q': 'отправки',
        })
        self.assertEqual(
            [item['id'] for item in global_response.context['products']],
            [str(elsewhere.pk)],
        )
        self.assertEqual(global_response.context['active_category'], None)
        self.assertEqual(global_response.context['search_category'], self.leaf.slug)
        self.assertContains(global_response, 'Искать только в этой категории')
        self.assertIn(
            f'category={self.leaf.slug}',
            unquote(global_response.context['filter_reset_url']),
        )
        global_api = self.client.get(reverse('api_products'), {
            'category': self.leaf.slug,
            'hits': '1',
            'q': 'отправки',
        }).json()['products']
        self.assertEqual([item['id'] for item in global_api], [str(elsewhere.pk)])
        scoped = self.client.get(reverse('catalog'), {
            'category': self.leaf.slug,
            'scope': 'category',
            'q': 'отправки',
        })
        self.assertEqual(scoped.context['products'], [])

    def test_product_suggestions_return_catalog_data_and_fallback_image(self):
        self.product.keywords = 'для отправки'
        self.product.save(update_fields=['keywords'])
        response = self.client.get(reverse('api_product_suggestions'), {'q': 'ОТПРАВКИ'})
        suggestions = response.json()['suggestions']
        self.assertEqual([item['id'] for item in suggestions], [str(self.product.pk)])
        self.assertEqual(suggestions[0]['sku'], self.product.sku or '')
        self.assertEqual(suggestions[0]['price'], '120.35')
        self.assertEqual(suggestions[0]['image'], 'https://example.test/box.jpg')

        no_image = Product.objects.create(
            category=self.leaf,
            name='Упаковка без фотографии',
            price=10,
            status=Product.STATUS_PUBLISHED,
        )
        api_item = next(
            item for item in self.client.get(reverse('api_products')).json()['products']
            if item['id'] == str(no_image.pk)
        )
        self.assertEqual(api_item['image'], '/static/store/images/no-photo.svg')
        ProductImage.objects.create(
            product=no_image,
            image_url='https://example.test/package.jpg',
        )
        suggestion_with_image = self.client.get(
            reverse('api_product_suggestions'),
            {'q': 'упаковка без'},
        ).json()['suggestions']
        self.assertEqual(suggestion_with_image[0]['image'], 'https://example.test/package.jpg')

    def test_price_stock_filters_combine_with_sorting_and_customer_prices(self):
        higher = Product.objects.create(
            category=self.leaf,
            name='Ящик для склада',
            price=130,
            availability=Product.AVAILABILITY_OUT_OF_STOCK,
            status=Product.STATUS_PUBLISHED,
        )
        cheaper = Product.objects.create(
            category=self.leaf,
            name='Альфа коробка',
            price=100,
            status=Product.STATUS_PUBLISHED,
        )
        name_sorted = self.client.get(reverse('api_products'), {
            'category': self.leaf.slug,
            'sort': 'name_desc',
        }).json()['products']
        self.assertEqual(name_sorted[0]['id'], str(higher.pk))
        newest = self.client.get(reverse('api_products'), {
            'category': self.leaf.slug,
            'sort': 'newest',
        }).json()['products']
        self.assertEqual(newest[0]['id'], str(cheaper.pk))
        response = self.client.get(reverse('api_products'), {
            'category': self.leaf.slug,
            'price_min': '120.35',
            'price_max': '140',
            'availability': Product.AVAILABILITY_IN_STOCK,
            'sort': 'name_desc',
        })
        self.assertEqual(
            [item['id'] for item in response.json()['products']],
            [str(self.product.pk)],
        )

        self.client.force_login(self.customer)
        sorted_products = self.client.get(
            reverse('api_products'), {'sort': 'price_asc'},
        ).json()['products']
        self.assertEqual(sorted_products[0]['id'], str(self.product.pk))
        limited = self.client.get(reverse('api_products'), {'price_max': '95'}).json()['products']
        self.assertEqual([item['id'] for item in limited], [str(self.product.pk)])
        self.assertNotIn(str(cheaper.pk), [item['id'] for item in limited])
        invalid_price = self.client.get(reverse('api_products'), {'price_min': 'NaN'})
        self.assertEqual(invalid_price.status_code, 200)

    def test_guest_price_filters_and_sort_use_calculated_retail_price(self):
        calculated = Product.objects.create(
            category=self.leaf, name='Расчётная розница', price=999,
            cost_price=100, retail_coefficient=Decimal('1.5000'),
            status=Product.STATUS_PUBLISHED,
        )
        higher = Product.objects.create(
            category=self.leaf, name='Расчётная дорогая розница', price=1,
            cost_price=100, retail_coefficient=Decimal('2.0000'),
            status=Product.STATUS_PUBLISHED,
        )
        Product.objects.filter(pk=calculated.pk).update(price=999)
        Product.objects.filter(pk=higher.pk).update(price=1)
        filtered = self.client.get(reverse('api_products'), {
            'price_min': '140', 'price_max': '160',
        }).json()['products']
        self.assertEqual([item['id'] for item in filtered], [str(calculated.pk)])

        sorted_products = self.client.get(
            reverse('api_products'), {'sort': 'price_asc'},
        ).json()['products']
        ids = [item['id'] for item in sorted_products]
        self.assertLess(ids.index(str(calculated.pk)), ids.index(str(higher.pk)))
        self.assertEqual(next(item['price'] for item in sorted_products if item['id'] == str(calculated.pk)), '150.00')

    def test_category_filters_use_linked_attributes(self):
        color = AttributeDefinition.objects.create(name='Цвет', value_type='choice', choices=['Белый', 'Крафт'])
        self.leaf.filter_attributes.add(color)
        ProductAttribute.objects.create(product=self.product, attribute=color, value_choice='Белый')
        kraft = Product.objects.create(category=self.leaf, name='Крафт коробка', price=90, status='published')
        ProductAttribute.objects.create(product=kraft, attribute=color, value_choice='Крафт')
        response = self.client.get(reverse('catalog'), {'category': self.leaf.slug, f'filter_{color.pk}': 'Белый'})
        self.assertContains(response, self.product.name)
        self.assertNotContains(response, kraft.name)
        self.assertContains(response, 'name="robots" content="noindex,follow"', html=False)

        size = AttributeDefinition.objects.create(name='Размер короба', value_type='choice', choices=['Малый'])
        self.root.filter_attributes.add(size)
        root_product = Product.objects.create(
            category=self.root,
            name='Коробка верхней категории',
            price=60,
            status='published',
        )
        ProductAttribute.objects.create(product=root_product, attribute=size, value_choice='Малый')
        root_response = self.client.get(reverse('catalog'), {'category': self.root.slug})
        self.assertContains(root_response, 'name="filter_{}"'.format(size.pk))
        self.assertNotContains(root_response, 'name="filter_{}"'.format(color.pk))
        self.assertContains(root_response, root_product.name)

    def test_multiple_and_range_filters_use_saved_product_values_together(self):
        color = AttributeDefinition.objects.create(
            name='Цвет — несколько',
            value_type=AttributeDefinition.TYPE_CHOICE,
            choices=['Белый', 'Крафт', 'Чёрный'],
            filter_type=AttributeDefinition.FILTER_MULTIPLE,
        )
        length = AttributeDefinition.objects.create(
            name='Длина для диапазона',
            value_type=AttributeDefinition.TYPE_INTEGER,
            filter_type=AttributeDefinition.FILTER_RANGE,
        )
        self.leaf.filter_attributes.add(color, length)
        kraft = Product.objects.create(
            category=self.leaf, name='Коробка крафт', price=90, status='published',
        )
        form = DynamicProductFieldsForm(
            {
                f'field_{color.pk}': ['Белый', 'Чёрный'],
            },
            product=self.product,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save(self.product)
        ProductAttribute.objects.create(
            product=self.product, attribute=length, value_integer=400,
        )
        ProductAttribute.objects.create(
            product=kraft, attribute=color, value_choices=['Крафт'],
        )
        ProductAttribute.objects.create(
            product=kraft, attribute=length, value_integer=250,
        )

        response = self.client.get(reverse('catalog'), {
            'category': self.leaf.slug,
            f'filter_{color.pk}': ['Белый', 'Крафт'],
            f'filter_{length.pk}_min': '300',
            f'filter_{length.pk}_max': '500',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['id'] for item in response.context['products']],
            [str(self.product.pk)],
        )
        self.assertEqual(
            ProductAttribute.objects.get(product=self.product, attribute=color).value_choices,
            ['Белый', 'Чёрный'],
        )
        self.assertContains(response, f'name="filter_{color.pk}"')
        self.assertContains(response, f'name="filter_{length.pk}_min"')
        self.assertEqual(response.context['active_filter_count'], 3)
        reset_url = response.context['filter_reset_url']
        self.assertIn(f'category={self.leaf.slug}', unquote(reset_url))
        self.assertNotIn('filter_', reset_url)

    def test_admin_can_create_update_and_delete_filter_definitions(self):
        self.client.force_login(self.staff)
        create_data = {
            'name': 'Материал',
            'value_type': AttributeDefinition.TYPE_CHOICE,
            'filter_type': AttributeDefinition.FILTER_MULTIPLE,
            'choices_text': 'Картон\nПластик',
            'unit': '',
            'is_required': '',
            'default_value': '',
            'is_visible': 'on',
            'is_filterable': 'on',
        }
        response = self.client.post(reverse('management_field_new'), create_data)
        self.assertEqual(response.status_code, 302)
        definition = AttributeDefinition.objects.get(name='Материал')
        self.assertEqual(definition.filter_type, AttributeDefinition.FILTER_MULTIPLE)
        self.assertEqual(definition.choices, ['Картон', 'Пластик'])

        create_data.update({
            'name': 'Материал упаковки',
            'filter_type': AttributeDefinition.FILTER_SINGLE,
            'choices_text': 'Крафт\nБелый',
        })
        response = self.client.post(
            reverse('management_field_edit', args=[definition.pk]),
            create_data,
        )
        self.assertEqual(response.status_code, 302)
        definition.refresh_from_db()
        self.assertEqual(definition.name, 'Материал упаковки')
        self.assertEqual(definition.filter_type, AttributeDefinition.FILTER_SINGLE)
        self.assertEqual(definition.choices, ['Крафт', 'Белый'])

        self.client.post(reverse('management_field_delete', args=[definition.pk]))
        self.assertFalse(AttributeDefinition.objects.filter(pk=definition.pk).exists())

    def test_filter_definition_requires_compatible_values_for_range_and_multiple(self):
        invalid_range = AttributeDefinitionForm(data={
            'name': 'Неверный диапазон',
            'value_type': AttributeDefinition.TYPE_TEXT,
            'filter_type': AttributeDefinition.FILTER_RANGE,
            'choices_text': '',
            'unit': '',
            'is_required': '',
            'default_value': '',
            'is_visible': 'on',
            'is_filterable': 'on',
        })
        self.assertFalse(invalid_range.is_valid())
        self.assertIn('filter_type', invalid_range.errors)

        invalid_multiple = AttributeDefinitionForm(data={
            'name': 'Неверный множественный',
            'value_type': AttributeDefinition.TYPE_INTEGER,
            'filter_type': AttributeDefinition.FILTER_MULTIPLE,
            'choices_text': '',
            'unit': '',
            'is_required': '',
            'default_value': '',
            'is_visible': 'on',
            'is_filterable': 'on',
        })
        self.assertFalse(invalid_multiple.is_valid())
        self.assertIn('filter_type', invalid_multiple.errors)

    def test_catalog_collects_filters_in_filter_button_panel(self):
        response = self.client.get(reverse('catalog'), {
            'category': self.leaf.slug,
            'price_min': '50',
            'availability': Product.AVAILABILITY_IN_STOCK,
        })
        self.assertContains(response, 'class="catalog-filter-open"')
        self.assertContains(response, 'class="catalog-sort-open"')
        self.assertContains(response, 'id="catalog-mobile-filter-panel"')
        self.assertContains(response, 'name="price_min"')
        self.assertContains(response, 'name="availability"')
        self.assertContains(response, 'id="catalog-mobile-sort-panel"')
        self.assertEqual(response.context['active_filter_count'], 2)
        self.assertContains(response, 'от 50 ₽')
        self.assertContains(response, 'В наличии')

    def test_category_filter_configuration_is_limited_to_five_attributes(self):
        attributes = [
            AttributeDefinition.objects.create(name=f'Фильтр {index}')
            for index in range(6)
        ]
        base_data = {
            'name': 'Категория с фильтрами',
            'sort_order': '0',
            'filter_attributes': [str(attribute.pk) for attribute in attributes[:5]],
        }
        form = CategoryForm(data=base_data)
        self.assertTrue(form.is_valid(), form.errors)

        base_data['filter_attributes'] = [str(attribute.pk) for attribute in attributes]
        form = CategoryForm(data=base_data)
        self.assertFalse(form.is_valid())
        self.assertIn('filter_attributes', form.errors)

    def test_catalog_toolbar_is_outside_category_sidebar_and_preserves_filters(self):
        color = AttributeDefinition.objects.create(
            name='Цвет для панели', value_type='choice', choices=['Белый', 'Крафт'],
        )
        self.leaf.filter_attributes.add(color)
        ProductAttribute.objects.create(
            product=self.product, attribute=color, value_choice='Белый',
        )
        params = {
            'category': self.leaf.slug,
            'q': 'Коробка',
            'scope': 'category',
            'price_min': '50',
            'availability': Product.AVAILABILITY_IN_STOCK,
            'sort': 'price_asc',
            f'filter_{color.pk}': 'Белый',
        }
        response = self.client.get(reverse('catalog'), params)

        self.assertEqual(response.status_code, 200)
        sidebar = response.content.decode().split(
            '<aside class="catalog-sidebar"', 1,
        )[1].split('</aside>', 1)[0]
        self.assertNotIn('catalog-search', sidebar)
        self.assertNotIn('catalog-filter-form', sidebar)
        self.assertContains(response, 'catalog-search-desktop')
        self.assertContains(
            response,
            'Найти товар по названию, артикулу или характеристикам...',
        )
        self.assertContains(response, 'catalog-toolbar-row')
        filter_panel = response.content.decode().split(
            'id="catalog-mobile-filter-panel"', 1,
        )[1].split('</aside>', 1)[0]
        self.assertEqual(filter_panel.count('name="price_min"'), 1)
        self.assertEqual(filter_panel.count('name="availability"'), 1)
        self.assertNotContains(response, 'catalog-inline-filter-form')

        expected = {
            'category_query_fields': {'q', 'scope', 'price_min', 'availability', 'sort', f'filter_{color.pk}'},
            'price_query_fields': {'category', 'q', 'scope', 'availability', 'sort', f'filter_{color.pk}'},
            'availability_query_fields': {'category', 'q', 'scope', 'price_min', 'sort', f'filter_{color.pk}'},
            'sort_query_fields': {'category', 'q', 'scope', 'price_min', 'availability', f'filter_{color.pk}'},
            'advanced_query_fields': {'category', 'q', 'scope', 'sort'},
        }
        for field_name, expected_names in expected.items():
            preserved = {
                field['name']
                for field in response.context[field_name]
            }
            self.assertTrue(
                expected_names <= preserved,
                f'{field_name}: {preserved}; filters={response.context["catalog_filters"]}',
            )

    def test_sorting_is_performed_on_server(self):
        cheaper = Product.objects.create(category=self.leaf, name='А дешёвый', price=10, status='published')
        data = self.client.get(reverse('api_products'), {'sort': 'price_asc'}).json()['products']
        self.assertEqual(data[0]['id'], str(cheaper.pk))
        data = self.client.get(reverse('api_products'), {'sort': 'price_desc'}).json()['products']
        self.assertEqual(data[0]['id'], str(self.product.pk))

    def test_variant_group_uses_product_attributes(self):
        color = AttributeDefinition.objects.create(name='Цвет варианта', value_type='choice', choices=['Белый', 'Крафт'])
        group = VariantGroup.objects.create(name='Коробка 400')
        group.attributes.add(color)
        self.product.variant_group = group
        self.product.save(update_fields=['variant_group'])
        ProductAttribute.objects.create(product=self.product, attribute=color, value_choice='Белый')
        kraft = Product.objects.create(category=self.leaf, name='Коробка 400 крафт', price=125, status='published', variant_group=group)
        ProductAttribute.objects.create(product=kraft, attribute=color, value_choice='Крафт')
        detail = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(detail, 'Цвет варианта: Белый')
        self.assertContains(detail, 'Цвет варианта: Крафт')
        payload = self.client.get(reverse('api_products')).json()['products'][0]
        self.assertEqual(len(payload['variants']), 2)

    def test_management_can_create_group_parameters_and_join_existing_products(self):
        self.client.force_login(self.staff)
        kraft = Product.objects.create(
            category=self.leaf,
            name='Коробка 400 крафт',
            sku='BOX-400-K',
            price=125,
            status='published',
        )
        response = self.client.post(
            reverse('management_variant_group_new'),
            {
                'name': 'Коробка 400×400',
                'products': [str(self.product.pk), str(kraft.pk)],
                'parameters-TOTAL_FORMS': '1',
                'parameters-INITIAL_FORMS': '0',
                'parameters-MIN_NUM_FORMS': '0',
                'parameters-MAX_NUM_FORMS': '30',
                'parameters-0-name': 'Цвет коробки',
                'parameters-0-value_type': AttributeDefinition.TYPE_CHOICE,
                'parameters-0-unit': '',
                'parameters-0-choices_text': 'Белый\nКрафт',
                'parameters-0-DELETE': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        group = VariantGroup.objects.get(name='Коробка 400×400')
        color = AttributeDefinition.objects.get(name='Цвет коробки')
        edit_response = self.client.get(
            reverse('management_variant_group_edit', args=[group.pk]),
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, 'Значения')
        self.assertContains(edit_response, 'Добавить параметр')
        self.assertEqual(list(group.products.order_by('pk')), sorted(
            [self.product, kraft], key=lambda product: product.pk,
        ))
        self.assertEqual(list(group.attributes.all()), [color])
        self.assertEqual(color.choices, ['Белый', 'Крафт'])

        self.product.variant_group = group
        self.product.save(update_fields=['variant_group'])
        kraft.variant_group = group
        kraft.save(update_fields=['variant_group'])
        value_form = DynamicProductFieldsForm(
            {f'field_{color.pk}': 'Белый'},
            product=self.product,
        )
        self.assertTrue(value_form.is_valid(), value_form.errors)
        value_form.save(self.product)
        ProductAttribute.objects.create(
            product=kraft,
            attribute=color,
            value_choice='Крафт',
        )

        detail = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(detail, 'Цвет коробки: Белый')
        self.assertContains(detail, 'Цвет коробки: Крафт')
        self.assertContains(detail, 'Коробка 400 крафт')
        switched_detail = self.client.get(
            reverse('product_detail', args=[kraft.slug]),
        )
        self.assertContains(switched_detail, 'Цвет коробки: Крафт')
        cart_response = self.post_json(
            'add_to_cart',
            {'product_id': kraft.pk, 'quantity': 1},
        )
        self.assertEqual(cart_response.status_code, 200)
        self.assertEqual(cart_response.json()['items'][0]['id'], str(kraft.pk))

        self.client.post(
            reverse('management_variant_group_edit', args=[group.pk]),
            {
                'name': group.name,
                'attributes': [str(color.pk)],
                'products': [str(self.product.pk)],
                'parameters-TOTAL_FORMS': '0',
                'parameters-INITIAL_FORMS': '0',
                'parameters-MIN_NUM_FORMS': '0',
                'parameters-MAX_NUM_FORMS': '30',
            },
        )
        kraft.refresh_from_db()
        self.assertIsNone(kraft.variant_group_id)
        self.assertTrue(Product.objects.filter(pk=kraft.pk).exists())
        self.assertTrue(ProductAttribute.objects.filter(product=kraft, attribute=color).exists())

    def test_out_of_stock_variant_is_marked_and_cannot_be_added_to_cart(self):
        color = AttributeDefinition.objects.create(name='Цвет коробки')
        group = VariantGroup.objects.create(name='Коробка 400 варианты')
        group.attributes.add(color)
        self.product.variant_group = group
        self.product.save(update_fields=['variant_group'])
        unavailable = Product.objects.create(
            category=self.leaf,
            name='Коробка 400 крафт',
            sku='BOX-OUT',
            price=45,
            status=Product.STATUS_PUBLISHED,
            availability=Product.AVAILABILITY_OUT_OF_STOCK,
            variant_group=group,
        )
        ProductAttribute.objects.create(
            product=self.product,
            attribute=color,
            value_text='Белый',
        )
        ProductAttribute.objects.create(
            product=unavailable,
            attribute=color,
            value_text='Крафт',
        )

        detail = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(detail, 'Нет в наличии')
        payload = self.client.get(reverse('api_products')).json()['products']
        unavailable_data = next(item for item in payload if item['id'] == str(unavailable.pk))
        self.assertFalse(unavailable_data['can_purchase'])
        self.assertTrue(next(item for item in unavailable_data['variants'] if item['id'] == str(unavailable.pk))['unavailable'])

        response = self.post_json('add_to_cart', {'product_id': unavailable.pk, 'quantity': 1})
        self.assertEqual(response.status_code, 409)

    def test_variant_api_returns_individual_values_and_cart_uses_selected_variant(self):
        color = AttributeDefinition.objects.create(
            name='Цвет для переключения',
            value_type=AttributeDefinition.TYPE_CHOICE,
            choices=['Белый', 'Крафт'],
        )
        size = AttributeDefinition.objects.create(
            name='Размер для переключения',
            value_type=AttributeDefinition.TYPE_TEXT,
        )
        group = VariantGroup.objects.create(name='Архивные короба')
        group.attributes.add(color, size)
        white = self.product
        white.name = 'Архивный короб белый'
        white.sku = 'ARCH-W'
        white.price = Decimal('50.00')
        white.variant_group = group
        white.save()
        kraft = Product.objects.create(
            category=self.leaf,
            name='Архивный короб крафт',
            sku='ARCH-K',
            price=Decimal('45.00'),
            status=Product.STATUS_PUBLISHED,
            image_url='https://example.test/kraft.jpg',
            variant_group=group,
        )
        ProductAttribute.objects.create(
            product=white, attribute=color, value_choice='Белый',
        )
        ProductAttribute.objects.create(
            product=white, attribute=size, value_text='330×250×150',
        )
        ProductAttribute.objects.create(
            product=kraft, attribute=color, value_choice='Крафт',
        )
        ProductAttribute.objects.create(
            product=kraft, attribute=size, value_text='330×250×350',
        )

        white_response = self.client.get(
            reverse('api_product_detail', args=[white.pk]),
        )
        kraft_response = self.client.get(
            reverse('api_product_detail', args=[kraft.pk]),
        )
        white_data = white_response.json()['product']
        kraft_data = kraft_response.json()['product']

        self.assertEqual(white_response.status_code, 200)
        self.assertEqual(kraft_response.status_code, 200)
        white_specs = dict(white_data['specs'])
        kraft_specs = dict(kraft_data['specs'])
        self.assertEqual(white_specs['Цвет для переключения'], 'Белый')
        self.assertEqual(white_specs['Размер для переключения'], '330×250×150')
        self.assertEqual(kraft_specs['Цвет для переключения'], 'Крафт')
        self.assertEqual(kraft_specs['Размер для переключения'], '330×250×350')
        self.assertIn('Крафт', next(
            variant['label']
            for variant in white_data['variants']
            if variant['id'] == str(kraft.pk)
        ))
        self.assertIn('330×250×350', next(
            variant['label']
            for variant in white_data['variants']
            if variant['id'] == str(kraft.pk)
        ))
        self.assertEqual(kraft_data['sku'], 'ARCH-K')
        self.assertEqual(kraft_data['price'], '45.00')
        self.assertEqual(kraft_data['image'], 'https://example.test/kraft.jpg')

        detail = self.client.get(reverse('product_detail', args=[white.slug]))
        self.assertContains(detail, f'data-product-url="{reverse("api_product_detail", args=[kraft.pk])}"')
        self.assertContains(detail, 'data-product-detail')

        cart_response = self.post_json(
            'add_to_cart',
            {'product_id': kraft.pk, 'quantity': 1},
        )
        cart_item = cart_response.json()['items'][0]
        self.assertEqual(cart_item['id'], str(kraft.pk))
        self.assertEqual(cart_item['sku'], 'ARCH-K')
        self.assertEqual(cart_item['price'], '45.00')

    def test_hidden_products_do_not_enter_sitemap(self):
        settings = SiteSettings.get_solo()
        settings.allow_indexing = True
        settings.save(update_fields=['allow_indexing'])
        hidden = Product.objects.create(category=self.leaf, name='Скрытый SEO товар', price=1, status='hidden')
        response = self.client.get(reverse('sitemap_xml'))
        self.assertNotContains(response, hidden.slug)
        self.assertIn(self.product.slug, unquote(response.content.decode()))

    def test_excel_import_updates_by_sku_and_continues_after_error(self):
        from openpyxl import Workbook
        self.product.sku = 'BOX-400'
        self.product.save(update_fields=['sku'])
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(BASE_COLUMNS)
        def row(sku, name, category, subcategory, price):
            values = {column: '' for column in BASE_COLUMNS}
            values.update({'Артикул': sku, 'Название': name, 'Категория': category, 'Подкатегория': subcategory, 'Цена': price, 'Статус': 'published', 'Наличие': 'in_stock'})
            return [values[column] for column in BASE_COLUMNS]
        sheet.append(row('BOX-400', 'Коробка обновлена', self.root.name, f'{self.child.name} / {self.leaf.name}', '199,90'))
        sheet.append(row('BAD-1', 'Ошибка', 'Несуществующая', '', 10))
        sheet.append(row('BOX-NEW', 'Новый товар', self.root.name, f'{self.child.name} / {self.leaf.name}', 75))
        content = BytesIO()
        workbook.save(content)
        content.seek(0)
        result = import_products(content)
        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(Product.objects.filter(sku='BOX-400').count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('199.90'))
        self.assertTrue(Product.objects.filter(sku='BOX-NEW').exists())

    def test_excel_export_can_be_imported_back(self):
        from openpyxl import load_workbook
        self.product.sku = 'ROUNDTRIP-1'
        self.product.save(update_fields=['sku'])
        data = export_products()
        workbook = load_workbook(BytesIO(data))
        headers = [cell.value for cell in workbook.active[1]]
        self.assertEqual(headers[:len(BASE_COLUMNS)], BASE_COLUMNS)
        price_column = headers.index('Цена') + 1
        sku_column = headers.index('Артикул') + 1
        for row in range(2, workbook.active.max_row + 1):
            if workbook.active.cell(row, sku_column).value == 'ROUNDTRIP-1':
                workbook.active.cell(row, price_column).value = '210.50'
        updated = BytesIO()
        workbook.save(updated)
        updated.seek(0)
        result = import_products(updated)
        self.assertGreaterEqual(result['updated'], 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('210.50'))

    def test_excel_round_trips_multiple_choice_attribute_values(self):
        from openpyxl import load_workbook

        color = AttributeDefinition.objects.create(
            name='Цвет для Excel',
            value_type=AttributeDefinition.TYPE_CHOICE,
            choices=['Белый', 'Крафт'],
            filter_type=AttributeDefinition.FILTER_MULTIPLE,
        )
        self.product.sku = 'MULTI-CHOICE-1'
        self.product.save(update_fields=['sku'])
        ProductAttribute.objects.create(
            product=self.product,
            attribute=color,
            value_choices=['Белый', 'Крафт'],
        )

        workbook = load_workbook(BytesIO(export_products()))
        headers = [cell.value for cell in workbook.active[1]]
        attribute_column = headers.index(f'Характеристика: {color.name}') + 1
        sku_column = headers.index('Артикул') + 1
        row_number = next(
            row
            for row in range(2, workbook.active.max_row + 1)
            if workbook.active.cell(row, sku_column).value == self.product.sku
        )
        self.assertEqual(
            workbook.active.cell(row_number, attribute_column).value,
            '["Белый", "Крафт"]',
        )
        content = BytesIO()
        workbook.save(content)
        content.seek(0)

        result = import_products(content)

        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['errors'], [])
        self.assertEqual(
            ProductAttribute.objects.get(product=self.product, attribute=color).value_choices,
            ['Белый', 'Крафт'],
        )

    def test_product_media_link_reuses_library_file(self):
        media = SiteMedia.objects.create(title='Общее фото', file=SimpleUploadedFile('shared.jpg', b'file'), alt='Коробка')
        link = ProductImage.objects.create(product=self.product, media=media, is_primary=True, sort_order=0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.display_image_url, media.file.url)
        link.delete()
        self.assertTrue(SiteMedia.objects.filter(pk=media.pk).exists())

    def test_category_cycles_are_rejected(self):
        for parent in [self.root, self.child, self.leaf]:
            self.root.parent = parent
            with self.assertRaises(ValidationError):
                self.root.save()
        form = CategoryForm({'name': self.root.name, 'parent': self.leaf.pk, 'sort_order': 0}, instance=self.root)
        self.assertFalse(form.is_valid())
        self.assertIn('parent', form.errors)

    def test_category_media_selection_and_filter_update(self):
        self.client.force_login(self.staff)
        self.leaf.image_url = 'https://example.test/old-category.jpg'
        self.leaf.save(update_fields=['image_url'])
        color = AttributeDefinition.objects.create(
            name='Цвет для категории',
            value_type=AttributeDefinition.TYPE_CHOICE,
            choices=['Белый', 'Крафт'],
            is_filterable=True,
            is_visible=True,
        )
        media = SiteMedia.objects.create(
            title='Фото категории',
            file=SimpleUploadedFile('category.png', b'png'),
        )
        media_response = self.client.get(reverse('management_media_api'))
        self.assertEqual(media_response.status_code, 200)
        self.assertIn(media.pk, [item['id'] for item in media_response.json()['items']])
        api_image = BytesIO()
        Image.new('RGB', (10, 10)).save(api_image, format='PNG')
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            upload_response = self.client.post(
                reverse('management_media_upload_api'),
                {
                    'title': 'Фото через медиатеку',
                    'alt': '',
                    'file': SimpleUploadedFile(
                        'media-picker.png',
                        api_image.getvalue(),
                        content_type='image/png',
                    ),
                },
            )
            self.assertEqual(upload_response.status_code, 200, upload_response.content.decode())
            uploaded_media = SiteMedia.objects.get(pk=upload_response.json()['id'])
            self.assertTrue(uploaded_media.file.name)
        image_form_response = self.client.get(
            reverse('management_category_edit', args=[self.leaf.pk]),
        )
        self.assertEqual(image_form_response.status_code, 200)
        self.assertEqual(
            image_form_response.content.count(b'class="current-image-preview"'),
            1,
        )
        self.assertContains(image_form_response, 'data-category-image-change')
        self.assertContains(image_form_response, 'data-category-image-remove')
        response = self.client.post(
            reverse('management_category_edit', args=[self.leaf.pk]),
            {
                'name': self.leaf.name,
                'sort_order': '3',
                'filter_attributes': [str(color.pk)],
                'image_media': str(media.pk),
                'is_active': 'on',
            },
        )
        self.assertEqual(response.status_code, 302, response.content.decode())
        self.leaf.refresh_from_db()
        self.assertEqual(self.leaf.sort_order, 3)
        self.assertEqual(self.leaf.image_media_id, media.pk)
        self.assertEqual(self.leaf.image_url, '')
        self.assertTrue(self.leaf.filter_attributes.filter(pk=color.pk).exists())
        image_bytes = BytesIO()
        Image.new('RGB', (10, 10)).save(image_bytes, format='PNG')
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            upload_response = self.client.post(
                reverse('management_category_edit', args=[self.leaf.pk]),
                {
                    'name': self.leaf.name,
                    'sort_order': '3',
                    'is_active': 'on',
                    'image_media': '',
                    'image': SimpleUploadedFile(
                        'uploaded-category.png',
                        image_bytes.getvalue(),
                        content_type='image/png',
                    ),
                },
            )
            self.assertEqual(upload_response.status_code, 302)
            self.leaf.refresh_from_db()
            self.assertIsNone(self.leaf.image_media_id)
            self.assertTrue(self.leaf.image.name)
            self.assertEqual(self.leaf.image_url, '')

    def test_category_management_filter_editor_preserves_shared_filter_links(self):
        self.client.force_login(self.staff)
        category = self.leaf
        other_category = Category.objects.create(name='Другая категория для фильтра')
        AttributeDefinition.objects.create(name='Уже созданный фильтр')

        response = self.client.get(reverse('management_category_edit', args=[category.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Фильтры категории')
        self.assertContains(response, 'Создать фильтр')
        self.assertContains(response, 'Привязать существующий фильтр')

        create_response = self.client.post(
            reverse('management_category_filter_create', args=[category.pk]),
            {
                'name': 'Цвет коробки',
                'value_type': AttributeDefinition.TYPE_CHOICE,
                'filter_type': AttributeDefinition.FILTER_MULTIPLE,
                'choices_text': 'Белый\nКрафт',
                'unit': '',
                'sort_order': '4',
                'is_required': '',
                'default_value': '',
                'is_visible': 'on',
                'is_filterable': 'on',
            },
        )
        self.assertEqual(create_response.status_code, 302)
        field = AttributeDefinition.objects.get(name='Цвет коробки')
        self.assertEqual(field.choices, ['Белый', 'Крафт'])
        self.assertEqual(field.sort_order, 4)
        category.refresh_from_db()
        self.assertTrue(category.filter_attributes.filter(pk=field.pk).exists())
        kraft_product = Product.objects.create(
            category=category, name='Бурая коробка', price=90, status=Product.STATUS_PUBLISHED,
        )
        ProductAttribute.objects.create(product=self.product, attribute=field, value_choice='Белый')
        ProductAttribute.objects.create(product=kraft_product, attribute=field, value_choice='Бурый')

        self.client.post(
            reverse('management_category_filter_attach', args=[other_category.pk]),
            {'field_id': str(field.pk)},
        )
        edit_response = self.client.post(
            reverse('management_category_filter_edit', args=[category.pk, field.pk]),
            {
                'name': 'Цвет упаковки',
                'value_type': AttributeDefinition.TYPE_CHOICE,
                'filter_type': AttributeDefinition.FILTER_SINGLE,
                'choices_text': 'Белый\nБурый',
                'unit': '',
                'sort_order': '2',
                'is_required': '',
                'default_value': '',
                'is_visible': 'on',
                'is_filterable': 'on',
            },
        )
        self.assertEqual(edit_response.status_code, 302)
        field.refresh_from_db()
        self.assertEqual(field.name, 'Цвет упаковки')
        self.assertEqual(field.choices, ['Белый', 'Бурый'])
        self.assertEqual(field.sort_order, 2)
        filtered_response = self.client.get(
            reverse('catalog'),
            {'category': category.slug, f'filter_{field.pk}': 'Белый'},
        )
        self.assertContains(filtered_response, 'Цвет упаковки')
        self.assertContains(filtered_response, self.product.name)
        self.assertNotContains(filtered_response, kraft_product.name)

        self.client.post(
            reverse('management_category_filter_delete', args=[category.pk, field.pk]),
        )
        self.assertTrue(AttributeDefinition.objects.filter(pk=field.pk).exists())
        self.client.post(
            reverse('management_category_filter_unlink', args=[category.pk, field.pk]),
        )
        self.assertTrue(AttributeDefinition.objects.filter(pk=field.pk).exists())
        self.assertFalse(category.filter_attributes.filter(pk=field.pk).exists())
        self.assertTrue(other_category.filter_attributes.filter(pk=field.pk).exists())

        self.client.post(
            reverse('management_category_filter_delete', args=[other_category.pk, field.pk]),
        )
        self.assertTrue(AttributeDefinition.objects.filter(pk=field.pk).exists())
        ProductAttribute.objects.filter(attribute=field).delete()
        self.client.post(
            reverse('management_category_filter_delete', args=[other_category.pk, field.pk]),
        )
        self.assertFalse(AttributeDefinition.objects.filter(pk=field.pk).exists())

    def test_category_create_edit_image_clear_and_delete_return_success_responses(self):
        self.client.force_login(self.staff)
        category = Category.objects.create(name='Категория без фильтра')
        field = AttributeDefinition.objects.create(name='Фильтр без формы')
        category.filter_attributes.add(field)

        create_response = self.client.post(
            reverse('management_category_new'),
            {'name': 'Созданная категория', 'is_active': 'on'},
        )
        self.assertEqual(create_response.status_code, 302)
        created = Category.objects.get(name='Созданная категория')
        self.assertEqual(created.sort_order, 0)

        image_media = SiteMedia.objects.create(
            title='Выбранное изображение',
            file=SimpleUploadedFile('category.png', b'png'),
        )
        edit_response = self.client.post(
            reverse('management_category_edit', args=[category.pk]),
            {
                'name': category.name,
                'sort_order': '2',
                'is_active': 'on',
                'image_media': str(image_media.pk),
            },
        )
        self.assertEqual(edit_response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.image_media_id, image_media.pk)
        self.assertTrue(category.filter_attributes.filter(pk=field.pk).exists())

        remove_response = self.client.post(
            reverse('management_category_edit', args=[category.pk]),
            {
                'name': category.name,
                'sort_order': '2',
                'is_active': 'on',
                'remove_image': '1',
            },
        )
        self.assertEqual(remove_response.status_code, 302)
        category.refresh_from_db()
        self.assertIsNone(category.image_media_id)
        self.assertEqual(category.image_url, '')
        self.assertEqual(category.image.name, '')

        delete_response = self.client.post(
            reverse('management_category_delete', args=[created.pk]),
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=created.pk).exists())

    def test_category_deletion_keeps_children(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('management_category_delete', args=[self.root.pk]))
        self.assertTrue(Category.objects.filter(pk=self.root.pk).exists())
        self.assertEqual(Category.objects.get(pk=self.child.pk).parent_id, self.root.pk)

    def test_category_filter_editor_preserves_invalid_input_and_product_values(self):
        self.client.force_login(self.staff)
        create_url = reverse('management_category_filter_create', args=[self.leaf.pk])
        response = self.client.post(create_url, {
            'new-filter-name': 'Новый цвет',
            'new-filter-value_type': AttributeDefinition.TYPE_CHOICE,
            'new-filter-filter_type': AttributeDefinition.FILTER_SINGLE,
        })
        self.assertContains(response, 'Новый цвет')
        self.assertContains(response, 'укажите хотя бы один вариант')
        self.assertContains(response, 'class="filter-create" open')
        self.assertFalse(AttributeDefinition.objects.filter(name='Новый цвет').exists())

        field = AttributeDefinition.objects.create(
            name='Цвет', value_type=AttributeDefinition.TYPE_CHOICE,
            filter_type=AttributeDefinition.FILTER_MULTIPLE, choices=['Белый', 'Синий', 'Старый'],
        )
        self.leaf.filter_attributes.add(field)
        value = ProductAttribute.objects.create(product=self.product, attribute=field, value_choices=['Белый', 'Синий', 'Старый'])
        edit_url = reverse('management_category_filter_edit', args=[self.leaf.pk, field.pk])
        prefix = f'filter-{field.pk}-'
        data = {'name': 'Цвет коробки', 'value_type': AttributeDefinition.TYPE_INTEGER, 'filter_type': AttributeDefinition.FILTER_SINGLE,
                'choices_text': 'Синий\nБелый', 'sort_order': '3', 'is_visible': 'on', 'is_filterable': 'on'}
        invalid = self.client.post(edit_url, {prefix + key: entry for key, entry in data.items()})
        self.assertContains(invalid, 'Этот тип уже используется')

        data['value_type'] = AttributeDefinition.TYPE_CHOICE
        saved = self.client.post(edit_url, {prefix + key: entry for key, entry in data.items()})
        self.assertEqual(saved.status_code, 302)
        value.refresh_from_db()
        self.assertEqual(value.value_choices, ['Белый', 'Синий', 'Старый'])
        catalog_url = reverse('catalog')
        query = {'category': self.leaf.slug, f'filter_{field.pk}': 'Синий'}
        storefront = self.client.get(catalog_url, query)
        options = next(item['values'] for item in storefront.context['catalog_filters'] if item.get('parameter') == f'filter_{field.pk}')
        self.assertEqual([option['value'] for option in options], ['Синий', 'Белый'])
        api = self.client.get(reverse('api_products'), query).json()
        self.assertEqual([product['id'] for product in api['products']], [str(self.product.pk)])

        unmodified_product = DynamicProductFieldsForm({f'field_{field.pk}': 'Белый'}, product=self.product)
        self.assertTrue(unmodified_product.is_valid(), unmodified_product.errors)
        unmodified_product.save(self.product)
        value.refresh_from_db()
        self.assertEqual(value.value_choices, ['Белый', 'Синий', 'Старый'])

    def test_category_image_errors_preserve_current_image_and_remove_keeps_shared_file(self):
        self.client.force_login(self.staff)
        edit_url = reverse('management_category_edit', args=[self.leaf.pk])
        photo = BytesIO()
        Image.new('RGB', (12, 12)).save(photo, format='PNG')
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            self.leaf.image.save('shared-category.png', SimpleUploadedFile('shared-category.png', photo.getvalue()))
            sibling = Category.objects.create(name='Категория с общей фотографией', image=self.leaf.image.name)
            invalid = self.client.post(edit_url, {'name': self.leaf.name, 'image_media': 'not-an-id'})
            self.assertContains(invalid, 'Проверьте ошибки в форме категории')
            self.assertContains(invalid, self.leaf.image.url)
            removed = self.client.post(edit_url, {'name': self.leaf.name, 'remove_image': '1'})
            self.assertEqual(removed.status_code, 302)
            self.leaf.refresh_from_db()
            self.assertFalse(self.leaf.image)
            self.assertTrue(sibling.image.storage.exists(sibling.image.name))

    def test_product_detail_page_and_category_recommendations(self):
        sibling = Product.objects.create(
            category=self.leaf,
            name='Рекомендованная коробка',
            price=75,
            status=Product.STATUS_PUBLISHED,
        )
        response = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, 'Характеристики')
        self.assertContains(response, 'Рекомендуем к этому товару')
        self.assertContains(response, sibling.name)

        manual = Product.objects.create(
            category=self.root,
            name='Ручная рекомендация',
            price=55,
            status=Product.STATUS_PUBLISHED,
        )
        self.product.recommended_products.set([manual])
        response = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(response, manual.name)
        self.assertNotContains(response, sibling.name)

    def test_hidden_ancestor_hides_products_everywhere(self):
        CartItem.objects.create(user=self.customer, product=self.product, quantity=2)
        FavoriteItem.objects.create(user=self.customer, product=self.product)
        self.root.is_active = False
        self.root.save()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('api_products')).json()['products'], [])
        self.assertEqual(self.client.get(reverse('api_categories')).json()['categories'], [])
        self.assertEqual(self.client.get(reverse('api_cart')).json()['items'], [])
        self.assertEqual(self.client.get(reverse('product_detail', args=[self.product.slug])).status_code, 404)
        self.assertNotContains(self.client.get('/sitemap.xml'), self.product.slug)
        self.assertNotContains(self.client.get(reverse('home')), 'data-product-id="%s"' % self.product.pk)
        self.assertEqual(self.post_json('add_to_cart', {'product_id': self.product.pk}).status_code, 404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('management_product_edit', args=[self.product.pk])).status_code, 200)

    def test_hidden_product_stays_in_database_and_admin(self):
        self.product.status = 'hidden'
        self.product.save()
        self.assertEqual(self.client.get(reverse('api_products')).json()['products'], [])
        self.assertEqual(self.client.get(reverse('product_detail', args=[self.product.slug])).status_code, 404)
        self.client.force_login(self.staff)
        self.product.retail_coefficient = Decimal('1.5000')
        self.product.wholesale_coefficient = Decimal('1.2000')
        self.product.special_coefficient = Decimal('1.1000')
        self.product.save()
        response = self.client.get(reverse('management_products'))
        self.assertContains(response, self.product.name)
        self.assertContains(response, 'Себестоимость')
        self.assertContains(response, 'Индивид. цены')
        listed_product = response.context['page'].object_list[0]
        self.assertEqual(listed_product.retail_price_display, Decimal('90.15'))
        self.assertEqual(listed_product.wholesale_price_display, Decimal('72.12'))
        self.assertEqual(listed_product.special_price_display, Decimal('66.11'))
        self.assertEqual(listed_product.individual_price_count, 1)

    def test_decimal_volume_zero_unknown_and_changed_dimensions(self):
        self.assertEqual(self.product.volume_m3, Decimal('0.024'))
        self.product.length_mm = Decimal('0')
        self.assertEqual(self.product.volume_m3, Decimal('0'))
        self.product.length_mm = None
        self.assertIsNone(self.product.volume_m3)
        Product.objects.filter(pk=self.product.pk).update(length_mm=Decimal('125.5'), width_mm=Decimal('60.25'), height_mm=Decimal('2.5'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.volume_m3, Decimal('0.0000189034375'))

    def test_dimensions_and_tax_validation(self):
        for field, value in [('vat_rate', '101'), ('vat_rate', '-1'), ('length_mm', '-1'), ('weight_kg', '-0.01'), ('cost_price', '-1')]:
            with self.subTest(field=field, value=value):
                form = ProductForm(self.product_payload(**{field: value}), instance=self.product)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        for vat in ['0', '10', '22', '100']:
            form = ProductForm(self.product_payload(vat_rate=vat), instance=self.product)
            self.assertTrue(form.is_valid(), form.errors)

    def test_database_checks_tax_and_dimensions(self):
        for field, value in [('vat_rate', -1), ('vat_rate', 101), ('weight_kg', -1), ('height_mm', -1), ('cost_price', -1)]:
            with self.subTest(field=field, value=value), self.assertRaises(IntegrityError), transaction.atomic():
                Product.objects.filter(pk=self.product.pk).update(**{field: value})

    def test_individual_price_is_unique_and_nonnegative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerPrice.objects.create(user=self.customer, product=self.product, price=10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CustomerPrice.objects.create(user=self.other, product=self.product, price=-1)

    def test_private_prices_and_cost_do_not_leak(self):
        for user, price in [(None, '120.35'), (self.customer, '91.27'), (self.other, '120.35')]:
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            data = self.client.get(reverse('api_products')).json()['products'][0]
            self.assertEqual(data['price'], price)
            self.assertNotIn('cost_price', data)
            self.assertNotIn('individual_prices', data)
            self.assertContains(self.client.get(reverse('catalog')), f'{price} ₽')
            self.assertContains(self.client.get(reverse('home')), f'{price} ₽')
        self.special.price = 0
        self.special.save()
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('api_products')).json()['products'][0]['price'], '0.00')

    def test_flags_dimensions_and_default_tax_available_in_api(self):
        data = self.client.get(reverse('api_products')).json()['products'][0]
        self.assertTrue(data['is_new'])
        self.assertTrue(data['is_special'])
        self.assertIn('НОВИНКА', data['badges'])
        self.assertIn('СПЕЦПРЕДЛОЖЕНИЕ', data['badges'])
        self.assertEqual(Decimal(data['volume_m3']), Decimal('0.024'))
        self.assertEqual(data['vat_rate'], '22.00')
        self.assertEqual(data['stock_quantity'], 100)

    def test_seo_custom_values_and_fallback(self):
        url = reverse('product_detail', args=[self.product.slug])
        response = self.client.get(url)
        self.assertContains(response, f'<h1>{self.product.name}</h1>')
        self.assertContains(response, 'name="description" content="Прочная упаковка"')
        self.product.h1 = 'Упаковка для пиццы'
        self.product.seo_title = 'Заказать коробку'
        self.product.meta_description = 'Отдельное SEO-описание'
        self.product.save()
        response = self.client.get(url)
        self.assertContains(response, '<h1>Упаковка для пиццы</h1>')
        self.assertContains(response, '<title>Заказать коробку</title>')
        self.assertContains(response, 'name="description" content="Отдельное SEO-описание"')

    def test_catalog_shows_product_description_and_opens_from_card(self):
        response = self.client.get(reverse('catalog'))
        self.assertContains(response, 'class="product-card-description">Прочная упаковка</p>')
        self.assertContains(response, f'class="open-product" href="{reverse("product_detail", args=[self.product.slug])}"')
        self.assertContains(response, f'class="catalog-details-button" href="{reverse("product_detail", args=[self.product.slug])}"')

    def test_product_detail_gallery_contains_main_photo_and_switchable_thumbnails(self):
        ProductImage.objects.create(
            product=self.product,
            image_url='https://example.test/side-one.jpg',
            alt='Вид сбоку',
        )
        ProductImage.objects.create(
            product=self.product,
            image_url='https://example.test/side-two.jpg',
            alt='Вид сверху',
        )
        response = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(response, 'data-detail-gallery')
        self.assertContains(response, 'data-detail-main-image src="https://example.test/box.jpg"')
        self.assertContains(response, 'data-detail-gallery-image="https://example.test/side-one.jpg"')
        self.assertContains(response, 'data-detail-gallery-image="https://example.test/side-two.jpg"')
        self.assertContains(response, 'data-detail-gallery-step="-1"')
        self.assertContains(response, 'aria-label="Открыть фотографию крупно"')

    def test_detail_quantity_and_cart_use_minimum_and_step(self):
        self.product.min_quantity = 2
        self.product.quantity_step = 3
        self.product.save(update_fields=['min_quantity', 'quantity_step'])
        response = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(response, 'type="number" min="2" step="3" value="2"')

        cart_response = self.post_json(
            'add_to_cart',
            {'product_id': self.product.pk, 'quantity': 7},
        )
        self.assertEqual(cart_response.status_code, 200)
        self.assertEqual(cart_response.json()['items'][0]['quantity'], 8)

    def test_cart_validates_input_and_persists_a_valid_quantity_after_repeated_adds(self):
        self.product.min_quantity = 2
        self.product.quantity_step = 3
        self.product.save(update_fields=['min_quantity', 'quantity_step'])
        product_id = self.product.pk

        for quantity in (1.5, 'abc', False, -1, 0):
            with self.subTest(quantity=quantity):
                response = self.post_json('add_to_cart', {'product_id': product_id, 'quantity': quantity})
                self.assertEqual(response.status_code, 400)

        self.post_json('add_to_cart', {'product_id': product_id, 'quantity': 2})
        response = self.post_json('add_to_cart', {'product_id': product_id, 'quantity': 2})
        self.assertEqual(response.json()['items'][0]['quantity'], 5)
        self.assertEqual(self.client.session['cart'][str(product_id)], 5)

        response = self.post_json('update_cart', {'product_id': product_id, 'quantity': '8'})
        self.assertEqual(response.json()['items'][0]['quantity'], 8)
        self.assertEqual(self.client.session['cart'][str(product_id)], 8)

    def test_catalog_fragment_shows_cart_state_and_preserves_disabled_purchase(self):
        product_id = self.product.pk
        self.post_json('add_to_cart', {'product_id': product_id, 'quantity': self.product.min_quantity})
        query = {'category': self.leaf.slug, 'cards': '1'}
        response = self.client.get(reverse('api_products'), query)
        self.assertIn('В корзине</button>', response.json()['cards_html'])

        self.product.availability = Product.AVAILABILITY_OUT_OF_STOCK
        self.product.save(update_fields=['availability'])
        response = self.client.get(reverse('api_products'), query)
        self.assertIn('data-purchase-disabled disabled>Нет в наличии', response.json()['cards_html'])

    def test_cart_add_if_absent_and_bulk_remove(self):
        other = Product.objects.create(
            category=self.leaf, name='Бумага', price=15, status='published',
        )
        for user in (None, self.customer):
            with self.subTest(user=user):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                request = {'product_id': self.product.pk, 'quantity': 2, 'if_absent': True}
                self.post_json('add_to_cart', request)
                duplicate = self.post_json('add_to_cart', request)
                self.assertEqual(duplicate.json()['items'][0]['quantity'], 2)
                self.post_json('add_to_cart', {'product_id': other.pk, 'quantity': 1})
                removed = self.post_json('update_cart', {'product_ids': [self.product.pk, other.pk], 'quantity': 0})
                self.assertEqual(removed.json()['items'], [])

    def test_cart_and_favorites_keep_separate_collections_even_with_legacy_move_flag(self):
        action = {'product_id': self.product.pk, 'is_favorite': True, 'move_from_cart': True}
        self.post_json('add_to_cart', {'product_id': self.product.pk, 'quantity': 2})
        response = self.post_json('toggle_favorite', action)
        self.assertTrue(response.json()['auth_required'])
        self.assertEqual(self.client.session['cart'][str(self.product.pk)], 2)

        self.client.force_login(self.customer)
        CartItem.objects.create(user=self.customer, product=self.product, quantity=2)
        CartItem.objects.create(user=self.other, product=self.product, quantity=2)
        group = VariantGroup.objects.create(name="Варианты для проверки корзины")
        group.products.add(self.product)
        variant = Product.objects.create(category=self.leaf, variant_group=group, name="Другая модификация", price=10, status="published")
        self.post_json('add_to_cart', {'product_id': variant.pk, 'quantity': 1})
        for _ in range(2):
            response = self.post_json('toggle_favorite', action)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('cart', response.json())
            self.assertTrue(response.json()['is_favorite'])
        self.assertEqual(FavoriteItem.objects.filter(user=self.customer, product=self.product).count(), 1)
        self.assertTrue(CartItem.objects.filter(user=self.other, product=self.product).exists())
        self.post_json('update_cart', {'product_id': self.product.pk, 'quantity': 5})
        removed = self.post_json('toggle_favorite', {**action, 'is_favorite': False})
        self.assertFalse(removed.json()['is_favorite'])
        self.client.get(reverse('catalog'))
        items = {item['id']: item['quantity'] for item in self.client.get(reverse('api_cart')).json()['items']}
        self.assertEqual(items, {str(self.product.pk): 5, str(variant.pk): 1})
        self.post_json('toggle_favorite', {'product_id': self.product.pk, 'is_favorite': True})
        self.post_json('update_cart', {'product_id': self.product.pk, 'quantity': 0})
        self.assertTrue(FavoriteItem.objects.filter(user=self.customer, product=self.product).exists())
        self.assertTrue(CartItem.objects.filter(user=self.customer, product=variant).exists())

    def test_recommendations_and_accessories_are_loaded_from_product_relations(self):
        recommended = Product.objects.create(
            category=self.leaf, name='Рекомендованный товар', price=45, status='published',
        )
        accessory = Product.objects.create(
            category=self.leaf, name='Сопутствующий товар', price=25, status='published',
            min_quantity=4,
        )
        self.client.force_login(self.staff)
        save_response = self.client.post(
            reverse('management_product_edit', args=[self.product.pk]),
            self.product_payload(
                recommended_products=[recommended.pk],
                accessory_products=[accessory.pk],
            ),
        )
        self.assertEqual(save_response.status_code, 302)
        self.client.logout()
        response = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(response, 'Рекомендуем к этому товару')
        self.assertContains(response, recommended.name)
        self.assertContains(response, 'С этим товаром покупают')
        self.assertContains(response, accessory.name)
        self.assertContains(response, f'data-add-detail-product="{accessory.pk}"')
        self.assertContains(response, 'data-detail-min="4"')

    def test_staff_preview_uses_the_public_product_template(self):
        self.product.status = Product.STATUS_DRAFT
        self.product.save(update_fields=['status'])
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('product_detail', args=[self.product.slug]),
            {'preview': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/catalog.html')
        self.assertTemplateUsed(response, 'store/partials/product_detail.html')
        self.assertContains(response, 'data-purchase-disabled disabled>Предпросмотр')

    def test_gallery_and_related_media(self):
        ProductImage.objects.create(product=self.product, image_url='https://example.test/side.jpg')
        video = SiteMedia.objects.create(title='Обзор', file='site_media/review.mp4')
        image = SiteMedia.objects.create(title='Схема', file='site_media/diagram.png')
        pdf = SiteMedia.objects.create(title='Инструкция', file='site_media/manual.pdf')
        self.product.media.add(video, image, pdf)
        data = self.client.get(reverse('api_products')).json()['products'][0]
        self.assertEqual(len(data['thumbs']), 3)
        self.assertEqual(len(data['media']), 2)
        self.assertTrue(next(item for item in data['media'] if item['id'] == str(video.pk))['is_video'])
        response = self.client.get(reverse('product_detail', args=[self.product.slug]))
        self.assertContains(response, '<video controls')
        self.assertContains(response, 'manual.pdf')
        self.client.force_login(self.staff)
        self.client.post(reverse('management_media_delete', args=[video.pk]))
        self.assertTrue(SiteMedia.objects.filter(pk=video.pk).exists())

    def test_product_gallery_saves_selection_primary_order_and_unlinks_only(self):
        import json

        self.client.force_login(self.staff)
        photo_a = SiteMedia.objects.create(title="Фото A", file="site_media/photo-a.png")
        photo_b = SiteMedia.objects.create(title="Фото B", file="site_media/photo-b.jpg")
        document = SiteMedia.objects.create(title="Паспорт товара", file="site_media/manual.pdf")
        self.product.media.add(document)
        edit = reverse("management_product_edit", args=[self.product.pk])

        def save(items, primary, revision=None):
            if revision is None:
                self.product.refresh_from_db()
                revision = self.product.updated_at.isoformat()
            return self.client.post(edit, self.product_payload(
                media=[document.pk], gallery_revision=revision,
                gallery_manifest=json.dumps({"items": items, "primary": primary}),
            ))

        keys = [f"media:{photo_b.pk}", "cover:url", f"media:{photo_a.pk}"]
        old_revision = self.product.updated_at.isoformat()
        response = save([{"key": key, "alt": "Описание"} for key in keys], keys[2])
        self.assertEqual(response.status_code, 302)
        rows = list(self.product.images.all())
        self.assertEqual([row.media_id for row in rows], [photo_b.pk, None, photo_a.pk])
        self.assertEqual([row.is_primary for row in rows], [False, False, True])
        self.assertEqual(list(self.product.media.all()), [document])
        api = self.client.get(reverse("api_product_detail", args=[self.product.pk])).json()["product"]
        self.assertEqual(api["thumbs"], [photo_a.file.url, photo_b.file.url, "https://example.test/box.jpg"])

        stale = save([], None, old_revision)
        self.assertContains(stale, "Галерея уже изменилась")
        self.assertEqual(self.product.images.count(), 3)
        self.client.post(reverse("management_media_delete", args=[photo_a.pk]))
        self.assertTrue(SiteMedia.objects.filter(pk=photo_a.pk).exists())
        remaining = f"link:{rows[0].pk}"
        self.assertEqual(save([{"key": remaining}], remaining).status_code, 302)
        self.assertEqual(list(self.product.images.values_list("media_id", flat=True)), [photo_b.pk])
        self.assertTrue(SiteMedia.objects.filter(pk=photo_a.pk).exists())

    def test_product_gallery_refuses_non_image_media_and_foreign_links(self):
        import json

        self.client.force_login(self.staff)
        document = SiteMedia.objects.create(title="Документ", file="site_media/manual.pdf")
        edit = reverse("management_product_edit", args=[self.product.pk])
        for key in (f"media:{document.pk}", "link:99999"):
            response = self.client.post(edit, self.product_payload(
                gallery_revision=self.product.updated_at.isoformat(),
                gallery_manifest=json.dumps({"items": [{"key": key}], "primary": key}),
            ))
            self.assertContains(response, "Одна из фотографий больше недоступна")
        self.assertFalse(self.product.images.exists())

    def test_modal_gallery_controls_are_available_for_four_product_images(self):
        for index in range(3):
            ProductImage.objects.create(
                product=self.product,
                image_url=f'https://example.test/side-{index}.jpg',
                sort_order=index,
            )

        payload = self.client.get(reverse('api_products')).json()['products'][0]
        response = self.client.get(reverse('catalog'))

        self.assertEqual(len(payload['thumbs']), 4)
        self.assertContains(response, 'class="modal-image-frame"')
        self.assertContains(response, 'data-modal-image-step="-1"')
        self.assertContains(response, 'data-modal-image-step="1"')
        self.assertContains(response, '<svg viewBox="0 0 24 24" aria-hidden="true"><path')

    def test_gallery_photo_is_used_when_main_photo_is_empty(self):
        self.product.image_url = ''
        self.product.save()
        ProductImage.objects.create(product=self.product, image_url='https://example.test/only.jpg')
        data = self.client.get(reverse('api_products')).json()['products'][0]
        self.assertEqual(data['image'], 'https://example.test/only.jpg')
        self.assertEqual(data['thumbs'], ['https://example.test/only.jpg'])

    def test_guest_cart_is_in_database_and_merges_on_login(self):
        response = self.post_json('add_to_cart', {'product_id': self.product.pk, 'quantity': 3})
        self.assertEqual(response.status_code, 200)
        stored = Session.objects.get(session_key=self.client.session.session_key).get_decoded()
        self.assertEqual(stored['cart'][str(self.product.pk)], 3)
        response = self.post_json('account_login', {'email': self.customer.username, 'password': 'test-password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CartItem.objects.get(user=self.customer, product=self.product).quantity, 3)
        data = self.client.get(reverse('api_cart')).json()
        self.assertEqual(data['total'], '273.81')
        self.assertEqual(self.client.session.get('cart'), {})

    def test_favorites_use_customer_price(self):
        self.client.force_login(self.customer)
        data = self.post_json('toggle_favorite', {'product_id': self.product.pk}).json()
        self.assertEqual(data['items'][0]['price'], '91.27')
        self.assertTrue(FavoriteItem.objects.filter(user=self.customer, product=self.product).exists())
        self.post_json('toggle_favorite', {'product_id': self.product.pk})
        self.assertFalse(FavoriteItem.objects.filter(user=self.customer, product=self.product).exists())

    @patch('store.notifications.notify_manager')
    def test_checkout_uses_server_price_and_freezes_delivery_snapshot(self, notify):
        self.client.force_login(self.customer)
        self.post_json('add_to_cart', {'product_id': self.product.pk, 'quantity': 3, 'price': '0.01'})
        response = self.post_json('checkout_order', {'full_name': 'Клиент', 'phone': '+79990000000', 'email': self.customer.email, 'total': '0.01'})
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(user=self.customer)
        item = order.items.get()
        self.assertEqual(order.total, Decimal('273.81'))
        self.assertEqual(item.price, Decimal('91.27'))
        self.assertEqual(item.vat_rate, Decimal('22.00'))
        self.assertEqual(order.total_weight_kg, Decimal('0.375'))
        self.assertEqual(order.total_volume_m3, Decimal('0.072'))
        self.product.cost_price = Decimal("100.00")
        self.product.retail_coefficient = Decimal("2.5000")
        self.product.weight_kg = 9
        self.product.length_mm = 900
        self.product.vat_rate = 10
        self.product.save()
        self.special.price = 500
        self.special.save()
        order.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(order.total, Decimal('273.81'))
        self.assertEqual(item.price, Decimal('91.27'))
        self.assertEqual(item.line_total, Decimal('273.81'))
        self.assertEqual(order.total_weight_kg, Decimal('0.375'))
        self.assertEqual(order.total_volume_m3, Decimal('0.072'))
        self.assertFalse(CartItem.objects.filter(user=self.customer).exists())
        self.assertEqual(list(order.status_history.values_list('status', flat=True)), ['awaiting_invoice'])

    @patch('store.notifications.notify_manager')
    def test_checkout_is_atomic_on_item_write_failure(self, notify):
        CartItem.objects.create(user=self.customer, product=self.product, quantity=2)
        self.client.force_login(self.customer)
        with patch('store.views.common.OrderItem.objects.create', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                self.post_json('checkout_order', {'full_name': 'Клиент', 'phone': '+79990000000', 'email': self.customer.email})
        self.assertFalse(Order.objects.exists())
        self.assertTrue(CartItem.objects.filter(user=self.customer).exists())
        notify.assert_not_called()

    def test_status_history_and_unknown_legacy_delivery(self):
        order = Order.objects.create(user=self.customer, full_name='Клиент', phone='123', email=self.customer.email)
        OrderItem.objects.create(order=order, product=self.product, product_name=self.product.name, quantity=2, price=120, line_total=240)
        self.assertIsNone(order.total_weight_kg)
        self.assertIsNone(order.total_volume_m3)
        self.client.force_login(self.staff)
        self.client.post(reverse('management_order_detail', args=[order.pk]), {'status': 'processing'})
        self.client.post(reverse('management_order_detail', args=[order.pk]), {'status': 'processing'})
        self.assertEqual(list(order.status_history.values_list('status', flat=True)), ['new', 'processing'])
        self.assertEqual(self.client.get(reverse('admin:store_order_change', args=[order.pk])).status_code, 200)

    def test_cms_saves_new_fields_and_individual_price(self):
        self.client.force_login(self.staff)
        data = self.product_payload(cost_price='55.12', length_mm='400', width_mm='300', height_mm='200', weight_kg='0.125', is_new='on', is_special='on', vat_rate='10', volume_m3='999')
        data.update({'prices-TOTAL_FORMS': 2, 'prices-INITIAL_FORMS': 1,
                     'prices-0-id': self.special.pk, 'prices-0-user': self.customer.pk, 'prices-0-price': '89.99',
                     'prices-1-user': self.other.pk, 'prices-1-price': '100.01'})
        response = self.client.post(reverse('management_product_edit', args=[self.product.pk]), data)
        self.assertEqual(response.status_code, 302, response.context and response.context['form'].errors)
        self.product.refresh_from_db()
        self.special.refresh_from_db()
        self.assertEqual(self.special.price, Decimal('89.99'))
        self.assertEqual(self.product.cost_price, Decimal('55.12'))
        self.assertEqual(self.product.volume_m3, Decimal('0.024'))
        self.assertEqual(self.product.vat_rate, Decimal('10'))
        self.assertTrue(self.product.is_special)
        self.assertEqual(CustomerPrice.objects.get(user=self.other, product=self.product).price, Decimal('100.01'))
        self.assertEqual(self.client.get(reverse('admin:store_product_change', args=[self.product.pk])).status_code, 200)

    def test_cms_invalid_price_does_not_partially_save_product(self):
        self.client.force_login(self.staff)
        data = self.product_payload(name='Не должно сохраниться')
        data.update({'prices-TOTAL_FORMS': 1, 'prices-INITIAL_FORMS': 1, 'prices-0-id': self.special.pk,
                     'prices-0-user': self.customer.pk, 'prices-0-price': '-1'})
        response = self.client.post(reverse('management_product_edit', args=[self.product.pk]), data)
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Коробка 400')

    def test_prices_across_levels_storefront_and_cart_without_stacking_coefficients(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("management_product_edit", args=[self.product.pk]),
            self.product_payload(
                cost_price="10,05", retail_coefficient="1,30",
                wholesale_coefficient="1,10", special_coefficient="0,90", price="",
            ),
        )
        self.assertEqual(response.status_code, 302, response.context and response.context["form"].errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("13.07"))
        legacy = Product.objects.create(name="Ручная цена", category=self.leaf, price="84.50", status="published")
        profile, _ = CustomerProfile.objects.update_or_create(
            user=self.other, defaults={"price_level": "wholesale"},
        )
        self.client.logout()

        def check(product, amount):
            url = reverse("product_detail", args=[product.slug])
            self.assertContains(self.client.get(url), f"{amount} ₽")
            api = self.client.get(reverse("api_product_detail", args=[product.pk])).json()
            self.assertEqual(api["product"]["price"], amount)
            response = self.post_json("update_cart", {"product_id": product.pk, "quantity": 2})
            line = next(item for item in response.json()["items"] if item["id"] == str(product.pk))
            self.assertEqual(line["price"], amount)
            self.assertEqual(Decimal(line["line_total"]), Decimal(amount) * 2)

        check(self.product, "13.07")
        self.client.force_login(self.other)
        check(self.product, "11.06")
        profile.wholesale_coefficient = Decimal("1.2500")
        profile.save()
        check(self.product, "12.56")
        check(legacy, "84.50")
        profile.price_level = "special"
        profile.save()
        check(self.product, "9.05")
        CustomerPrice.objects.create(user=self.other, product=self.product, price=0)
        check(self.product, "0.00")

    def test_invalid_individual_price_does_not_change_other_prices_or_customer_level(self):
        self.client.force_login(self.staff)
        profile, _ = CustomerProfile.objects.update_or_create(user=self.customer, defaults={"price_level": "retail"})
        url = reverse("management_customer_detail", args=[self.customer.pk])
        data = {"price_level": "wholesale", "wholesale_coefficient": "1,20",
                f"individual_price_{self.product.pk}": "NaN", "email": self.customer.email}
        response = self.client.post(url, data)
        self.assertContains(response, "Укажите индивидуальную цену")
        self.special.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(profile.price_level, "retail")
        self.assertEqual(self.special.price, Decimal("91.27"))
        data[f"individual_price_{self.product.pk}"] = "89,05"
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.special.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(profile.wholesale_coefficient, Decimal("1.2000"))
        self.assertEqual(self.special.price, Decimal("89.05"))

    def test_customer_admin_edits_identity_and_pricing_without_changing_order_snapshot(self):
        self.client.force_login(self.staff)
        self.special.delete()
        self.product.sku = "QA-PRICE-22"
        self.product.cost_price = Decimal("100")
        self.product.retail_coefficient = Decimal("1.20")
        self.product.wholesale_coefficient = Decimal("1.05")
        self.product.save()
        profile = CustomerProfile.objects.create(user=self.customer, company="Тестовая Компания")
        old_order = Order.objects.create(user=self.customer, full_name="Покупатель", phone="123", total=240)
        old_item = OrderItem.objects.create(order=old_order, product=self.product, product_name=self.product.name, price=120, quantity=2, line_total=240)
        archived = Product.objects.create(name="Скрытая позиция", category=self.leaf, price=100, status="hidden")
        archive_price = CustomerPrice.objects.create(user=self.customer, product=archived, price=77)
        index = reverse("management_customers")
        listing = self.client.get(index, {"q": "тестовая компания"})
        self.assertContains(listing, "Сохранить уровни цен", count=1)
        self.assertContains(listing, "Открыть")
        self.assertEqual(self.client.post(index, {f"price_level_{self.customer.pk}": "wholesale"}).status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.price_level, "wholesale")

        detail = reverse("management_customer_detail", args=[self.customer.pk])
        search = reverse("management_customer_product_search", args=[self.customer.pk])
        result = self.client.get(search, {"q": "qa-price-22"}).json()["items"]
        self.assertEqual([(row["id"], row["level_price"]) for row in result], [(self.product.pk, "105.00")])
        self.assertContains(self.client.get(detail), old_order.number)
        response = self.client.post(detail, {
            "first_name": "Анна", "last_name": "Новая", "email": "new-buyer@example.test",
            "company": "ООО Тест", "contact_person": "Анна Новая", "phone": "+70001234567",
            "status": "inactive", "inn": "1234567890", "kpp": "123456789",
            "delivery_addresses": "Первый адрес\n\n Второй адрес ", "comment": "Доставка в офис",
            "price_level": "wholesale", "wholesale_coefficient": "1,08", f"individual_price_{self.product.pk}": "96,50",
        })
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(self.customer.username, "new-buyer@example.test")
        self.assertEqual(self.customer.get_full_name(), "Анна Новая")
        for field, expected in {
            "company": "ООО Тест", "contact_person": "Анна Новая", "phone": "+70001234567",
            "status": "inactive", "inn": "1234567890", "kpp": "123456789",
            "delivery_addresses": ["Первый адрес", "Второй адрес"], "comment": "Доставка в офис",
            "wholesale_coefficient": Decimal("1.0800"),
        }.items():
            self.assertEqual(getattr(profile, field), expected)
        self.assertTrue(CustomerPrice.objects.filter(pk=archive_price.pk, price=77).exists())
        self.client.logout()
        self.assertEqual(self.client.get(search, {"q": "qa-price-22"}).status_code, 302)
        self.assertEqual(self.post_json("account_login", {"email": self.customer.email, "password": "test-password"}).status_code, 200)
        product_api = reverse("api_product_detail", args=[self.product.pk])
        self.assertEqual(self.client.get(product_api).json()["product"]["price"], "96.50")
        storefront = self.client.get(reverse("product_detail", args=[self.product.slug]))
        self.assertContains(storefront, "96.50 ₽")
        self.assertContains(storefront, old_order.number)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(detail, {f"individual_price_{self.product.pk}": ""}).status_code, 302)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(product_api).json()["product"]["price"], "108.00")
        old_order.refresh_from_db()
        old_item.refresh_from_db()
        self.assertEqual(old_order.total, Decimal("240.00"))
        self.assertEqual(old_item.price, Decimal("120.00"))

    def test_guest_cart_merge_persists_quantity_matching_minimum_and_step(self):
        self.product.quantity_step = 3
        self.product.save(update_fields=["quantity_step"])
        CartItem.objects.create(user=self.customer, product=self.product, quantity=2)
        self.post_json("add_to_cart", {"product_id": self.product.pk, "quantity": 2})
        response = self.post_json("account_login", {"email": self.customer.email, "password": "test-password"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(CartItem.objects.get(user=self.customer, product=self.product).quantity, 5)

    def test_cms_creates_nested_category(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('management_category_new'), {'name': 'Глубокая категория', 'parent': self.leaf.pk, 'sort_order': 0, 'is_active': 'on'})
        self.assertEqual(response.status_code, 302)
        category = Category.objects.get(name='Глубокая категория')
        self.assertEqual(category.parent_id, self.leaf.pk)
        catalog_response = self.client.get(reverse('catalog'), {'category': self.leaf.slug})
        self.assertIn(
            category.slug,
            [item['slug'] for item in catalog_response.context['category_tiles']],
        )
        self.assertEqual(Category.objects.filter(slug=category.slug).count(), 1)
