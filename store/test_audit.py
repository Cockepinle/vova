from html.parser import HTMLParser
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.core.files.base import ContentFile
from .cms_forms import SiteSettingsForm
from .models import Category, Employee, Order, Product, SiteMedia, SiteSettings


class FormStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = False
        self.delete_actions = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.depth += 1
            self.nested |= self.depth > 1
        if tag == 'button' and 'formaction' in attrs:
            self.delete_actions.append(attrs['formaction'])

    def handle_endtag(self, tag):
        if tag == 'form':
            self.depth -= 1


class SiteAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user('manager', is_staff=True)
        cls.category = Category.objects.create(name='Упаковка')
        cls.product = Product.objects.create(category=cls.category, name='Коробка', price=50, min_quantity=10, status='published')
        cls.employee = Employee.objects.create(name='Менеджер', role='Продажи')

    def test_public_pages_without_cms_records(self):
        for url in ['/', '/catalog/', '/team/', '/contacts/', '/documents/privacy/', '/documents/offer/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_management_requires_staff(self):
        self.assertEqual(self.client.get('/management/products/').status_code, 302)
        customer = get_user_model().objects.create_user('customer')
        self.client.force_login(customer)
        self.assertEqual(self.client.post(reverse('management_product_delete', args=[self.product.pk])).status_code, 302)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_row_deletion_forms_are_not_nested(self):
        self.client.force_login(self.staff)
        for kind, obj in [('product', self.product), ('category', self.category), ('employee', self.employee)]:
            with self.subTest(kind=kind):
                parser = FormStructure()
                parser.feed(self.client.get(reverse('management_'+{'product':'products','category':'categories','employee':'employees'}[kind])).content.decode())
                self.assertFalse(parser.nested)
                self.assertEqual(parser.depth, 0)
                self.assertIn(reverse(f'management_{kind}_delete', args=[obj.pk]), parser.delete_actions)

    def test_product_status_and_delete(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('management_product_bulk'), {'action':'save_statuses', 'product_ids':[self.product.pk], f'status_{self.product.pk}':'hidden'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'hidden')
        self.assertEqual(self.client.get(reverse('management_product_delete', args=[self.product.pk])).status_code, 405)
        self.client.post(reverse('management_product_delete', args=[self.product.pk]))
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_category_with_products_cannot_be_deleted(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('management_category_delete', args=[self.category.pk]))
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_order_status(self):
        self.client.force_login(self.staff)
        order = Order.objects.create(user=self.staff, full_name='Покупатель', phone='+79990000000', email='test@example.com')
        self.client.post(reverse('management_order_detail', args=[order.pk]), {'status':'processing'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'processing')

    def test_api_preserves_minimum_quantity(self):
        product = self.client.get('/api/products/').json()['products'][0]
        self.assertEqual(product['min_quantity'], 10)

    def test_product_create_and_edit(self):
        self.client.force_login(self.staff)
        data = {'category':self.category.pk, 'name':'Новая упаковка', 'price':'123.50', 'unit':'шт', 'min_quantity':5, 'stock_quantity':100, 'availability':'in_stock', 'status':'draft'}
        response = self.client.post(reverse('management_product_new'), data)
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name=data['name'])
        data.update(name='Обновлённая упаковка', status='published')
        self.client.post(reverse('management_product_edit', args=[product.pk]), data)
        product.refresh_from_db()
        self.assertEqual(product.name, data['name'])
        self.assertEqual(product.status, 'published')

    def test_page_image_upload(self):
        from io import BytesIO
        from tempfile import TemporaryDirectory
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import PageContent
        self.client.force_login(self.staff)
        image = BytesIO()
        Image.new('RGB', (10,10)).save(image, format='PNG')
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            response = self.client.post(reverse('management_page_new'), {'page':'home', 'is_visible':'on', 'hero_image':SimpleUploadedFile('hero.png', image.getvalue(), content_type='image/png')})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(PageContent.objects.get(page='home').hero_image.name)

    def test_logo_replacement_and_clear_remove_direct_files(self):
        from io import BytesIO
        from tempfile import TemporaryDirectory
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        def image_file(name):
            image = BytesIO()
            Image.new('RGB', (10, 10)).save(image, format='PNG')
            return SimpleUploadedFile(name, image.getvalue(), content_type='image/png')

        self.client.force_login(self.staff)
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            settings = SiteSettings.get_solo()
            first = image_file('first.png')
            settings.logo_image.save(first.name, first, save=True)
            old_name = settings.logo_image.name
            payload = self._settings_payload(settings)
            with patch('store.cms_views.delete_unreferenced_file') as cleanup:
                response = self.client.post(reverse('management_settings'), {**payload, 'logo_image': image_file('second.png')})
            self.assertEqual(response.status_code, 302)
            settings.refresh_from_db()
            self.assertTrue(settings.logo_image.name)
            self.assertNotEqual(settings.logo_image.name, old_name)
            cleanup.assert_called_once()
            self.assertEqual(cleanup.call_args.args[0], old_name)
            self.assertNotEqual(settings.logo_url, '')

            response = self.client.post(reverse('management_settings'), {**self._settings_payload(settings), 'remove_logo': '1'})
            self.assertEqual(response.status_code, 302)
            settings.refresh_from_db()
            self.assertFalse(settings.logo_image.name)
            self.assertEqual(settings.logo_url, '')

    def test_selecting_shared_logo_does_not_delete_media_file(self):
        from tempfile import TemporaryDirectory
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.staff)
        with TemporaryDirectory() as directory, self.settings(MEDIA_ROOT=directory):
            media = SiteMedia.objects.create(title='Логотип', file=SimpleUploadedFile('shared.png', b'file'))
            settings = SiteSettings.get_solo()
            old_file = SimpleUploadedFile('direct.png', b'direct')
            settings.logo_image.save(old_file.name, old_file, save=True)
            old_name = settings.logo_image.name
            with patch('store.cms_views.delete_unreferenced_file') as cleanup:
                response = self.client.post(reverse('management_settings'), {**self._settings_payload(settings), 'logo_media': media.pk})
            self.assertEqual(response.status_code, 302, response.content.decode())
            self.assertEqual(response.status_code, 302)
            settings.refresh_from_db()
            self.assertEqual(settings.logo_media_id, media.pk)
            self.assertFalse(settings.logo_image.name)
            cleanup.assert_called_once()
            self.assertEqual(cleanup.call_args.args[0], old_name)
            self.assertTrue(media.file.storage.exists(media.file.name))

    def test_missing_logo_file_has_no_url(self):
        settings = SiteSettings.get_solo()
        settings.logo_image.name = 'site/missing.png'
        settings.save(update_fields=['logo_image'])
        self.assertEqual(settings.logo_url, '')

    def test_cleanup_deletes_unreferenced_file(self):
        from tempfile import TemporaryDirectory
        from django.core.files.storage import FileSystemStorage
        from store.cms_views import delete_unreferenced_file

        with TemporaryDirectory() as directory:
            storage = FileSystemStorage(location=directory)
            storage.save('logo.png', ContentFile(b'logo'))
            delete_unreferenced_file('logo.png', storage)
            self.assertFalse(storage.exists('logo.png'))

    @staticmethod
    def _settings_payload(settings):
        form = SiteSettingsForm(instance=settings)
        payload = {}
        for name, field in form.fields.items():
            if name in {'logo_image', 'logo_media', 'remove_logo'}:
                continue
            value = getattr(settings, name)
            if hasattr(value, 'pk'):
                value = value.pk
            if isinstance(value, bool):
                value = 'on' if value else ''
            payload[name] = '' if value is None else value
        payload.update({'links-TOTAL_FORMS': '0', 'links-INITIAL_FORMS': '0'})
        return payload
