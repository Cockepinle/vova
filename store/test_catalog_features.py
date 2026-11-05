from decimal import Decimal
from io import BytesIO
from urllib.parse import unquote
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .cms_forms import CategoryForm, DynamicProductFieldsForm, ProductForm
from .excel import BASE_COLUMNS, export_products, import_products
from .models import (
    AttributeDefinition, CartItem, Category, CustomerPrice, FavoriteItem, Order, OrderItem,
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
        self.assertContains(root_response, reverse('catalog') + '?category=' + self.child.slug)
        self.assertContains(root_response, root_product.name)
        self.assertNotContains(root_response, child_product.name)
        self.assertNotContains(root_response, self.product.name)
        self.assertContains(root_response, reverse('catalog') + '?category=' + self.root.slug)

        child_response = self.client.get(reverse('catalog'), {'category': self.child.slug})
        self.assertContains(child_response, self.leaf.name)
        self.assertContains(child_response, child_product.name)
        self.assertNotContains(child_response, root_product.name)
        self.assertNotContains(child_response, self.product.name)
        self.assertContains(child_response, reverse('catalog') + '?category=' + self.root.slug)

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
        self.assertContains(leaf_response, reverse('catalog') + '?category=' + self.root.slug)

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

    def test_mobile_catalog_drawers_and_active_filter_controls_render(self):
        response = self.client.get(reverse('catalog'), {
            'category': self.leaf.slug,
            'price_min': '50',
            'availability': Product.AVAILABILITY_IN_STOCK,
        })
        self.assertContains(response, 'class="catalog-filter-open"')
        self.assertContains(response, 'class="catalog-sort-open"')
        self.assertContains(response, 'id="catalog-mobile-filter-panel"')
        self.assertContains(response, 'id="catalog-mobile-sort-panel"')
        self.assertEqual(response.context['active_filter_count'], 2)
        self.assertContains(response, 'от 50 ₽')
        self.assertContains(response, 'В наличии')

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

    def test_category_deletion_keeps_children(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('management_category_delete', args=[self.root.pk]))
        self.assertTrue(Category.objects.filter(pk=self.root.pk).exists())
        self.assertEqual(Category.objects.get(pk=self.child.pk).parent_id, self.root.pk)

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
        self.assertContains(self.client.get(reverse('management_products')), self.product.name)

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
        Product.objects.filter(pk=self.product.pk).update(price=999, weight_kg=9, length_mm=900, vat_rate=10)
        self.special.price = 500
        self.special.save()
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('273.81'))
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
