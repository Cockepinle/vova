from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CustomerRequest, Employee
from .test_media_uploads import image_file


class ManagementRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user("records-manager", is_staff=True)
        cls.customer = user_model.objects.create_user("records-customer")
        cls.employee = Employee.objects.create(
            name="Анна Иванова", role="Логистика", text="Отвечает за доставку",
            phone="+7 (900) 000-00-00", email="employee@example.test",
            status=Employee.STATUS_PUBLISHED, sort_order=7,
        )
        cls.quote = CustomerRequest.objects.create(
            user=cls.customer, name="Иван Петров", company="Компания Петрова",
            email="buyer@example.test", phone="+7 (999) 111-22-33",
            text="Коробки, 150 шт.\nПараметры: 25 × 10 см.",
            attachment="requests/specification.pdf", admin_comment="Уточнить наличие",
        )

    def setUp(self):
        self.client.force_login(self.manager)
        self.employee_detail = reverse("management_employee_detail", args=[self.employee.pk])
        self.employee_edit = reverse("management_employee_edit", args=[self.employee.pk])
        self.quote_detail = reverse("management_request_detail", args=[self.quote.pk])

    def quote_payload(self, **changes):
        self.quote.refresh_from_db()
        return {
            "name": self.quote.name, "company": self.quote.company, "email": self.quote.email,
            "phone": self.quote.phone, "text": self.quote.text, "request_type": self.quote.request_type,
            "status": self.quote.status, "admin_comment": self.quote.admin_comment,
            "version": self.quote.updated_at.isoformat(), **changes,
        }

    def test_employee_card_search_and_existing_actions(self):
        listing = reverse("management_employees")
        found = self.client.get(listing, {"q": "Логистика", "status": Employee.STATUS_PUBLISHED})
        self.assertContains(found, f'href="{self.employee_detail}?')
        self.assertNotContains(self.client.get(listing, {"status": Employee.STATUS_DRAFT}), self.employee.name)
        card = self.client.get(self.employee_detail, {"q": "Иванова"})
        for value in (
            self.employee.name, self.employee.role, self.employee.text, self.employee.email,
            "tel:+79000000000", self.employee.get_status_display(), "no-photo.svg", self.employee_edit,
        ):
            self.assertContains(card, value)
        self.assertContains(card, f'href="{listing}?q=')
        bulk_url = reverse("management_employee_bulk")
        self.client.post(bulk_url, {
            "action": "save_statuses", "employee_ids": [self.employee.pk],
            f"status_{self.employee.pk}": Employee.STATUS_HIDDEN,
        })
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, Employee.STATUS_HIDDEN)
        self.client.post(bulk_url, {"action": Employee.STATUS_PUBLISHED, "ids": [self.employee.pk]})
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, Employee.STATUS_PUBLISHED)
        duplicate = reverse("management_employee_duplicate", args=[self.employee.pk])
        self.assertEqual(self.client.get(duplicate).status_code, 405)
        self.assertEqual(self.client.post(duplicate).status_code, 302)
        clone = Employee.objects.exclude(pk=self.employee.pk).get()
        self.assertEqual(clone.status, Employee.STATUS_DRAFT)
        self.assertEqual(self.client.post(reverse("management_employee_delete", args=[clone.pk])).status_code, 302)
        self.assertFalse(Employee.objects.filter(pk=clone.pk).exists())

    def test_employee_photo_replacement_keeps_other_values(self):
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            self.employee.image.save("before.png", image_file("before.png"))
            original = self.employee.image.name
            self.assertContains(self.client.get(self.employee_edit), self.employee.image.url)
            response = self.client.post(self.employee_edit, {
                "name": self.employee.name, "role": "Руководитель логистики",
                "text": self.employee.text, "phone": self.employee.phone,
                "email": self.employee.email, "status": self.employee.status,
                "image": image_file("after.webp", "WEBP"),
            })
            self.assertRedirects(response, self.employee_detail)
            self.employee.refresh_from_db()
            self.assertEqual(self.employee.role, "Руководитель логистики")
            self.assertNotEqual(self.employee.image.name, original)
            self.assertTrue(self.employee.image.storage.exists(self.employee.image.name))
            self.assertEqual(self.employee.status, Employee.STATUS_PUBLISHED)
            self.assertEqual(self.employee.sort_order, 7)
            self.assertEqual(self.employee.phone, "+7 (900) 000-00-00")
            self.assertEqual(self.employee.email, "employee@example.test")
            self.assertContains(self.client.get(self.employee_detail), self.employee.image.url)

    def test_quote_list_and_detail(self):
        listing = reverse("management_requests")
        for term in (self.quote.email, "Коробки", f"№{self.quote.pk}"):
            response = self.client.get(listing, {"q": term, "status": CustomerRequest.STATUS_NEW})
            self.assertContains(response, self.quote_detail)
        self.assertNotContains(self.client.get(listing, {"status": CustomerRequest.STATUS_DONE}), self.quote.email)
        response = self.client.get(self.quote_detail)
        for value in (
            self.quote.name, self.quote.company, self.quote.email, "tel:+79991112233",
            self.quote.text, self.quote.get_request_type_display(), self.quote.get_status_display(),
            self.quote.attachment.url, self.quote.admin_comment, self.customer.username,
        ):
            self.assertContains(response, value)
        self.assertContains(self.client.get(self.quote_detail, {"edit": "1"}), 'name="version"')

    def test_quote_edit_validates_keeps_metadata_and_detects_stale_edits(self):
        created = self.quote.created_at
        invalid = self.client.post(self.quote_detail, self.quote_payload(email="bad-email", status="invalid", text="Черновой текст"))
        self.assertContains(invalid, "Введите корректный email.")
        self.assertContains(invalid, "Выберите статус из списка.")
        self.assertContains(invalid, "Черновой текст")
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.email, "buyer@example.test")
        stale = self.quote_payload(text="Данные из старой вкладки")
        payload = self.quote_payload(
            name="Новое имя", company="Новая компания", phone="+79992223344",
            email="new@example.test", status=CustomerRequest.STATUS_PROCESSING, text="Изменённые параметры",
            request_type=CustomerRequest.TYPE_SUPPORT, admin_comment="Проверить параметры",
            created_at="2000-01-01", user=self.manager.pk, attachment="requests/another.pdf",
        )
        result = self.client.post(self.quote_detail, payload, follow=True)
        self.assertContains(result, "Запрос сохранён.")
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.email, "new@example.test")
        self.assertEqual(self.quote.name, "Новое имя")
        self.assertEqual(self.quote.company, "Новая компания")
        self.assertEqual(self.quote.phone, "+79992223344")
        self.assertEqual(self.quote.text, "Изменённые параметры")
        self.assertEqual(self.quote.request_type, CustomerRequest.TYPE_SUPPORT)
        self.assertEqual(self.quote.admin_comment, "Проверить параметры")
        self.assertEqual(self.quote.status, CustomerRequest.STATUS_PROCESSING)
        self.assertEqual(self.quote.created_at, created)
        self.assertEqual(self.quote.user_id, self.customer.pk)
        self.assertEqual(self.quote.attachment.name, "requests/specification.pdf")
        self.assertContains(self.client.post(self.quote_detail, stale), "Запрос уже изменён.")
        stale = self.quote_payload()
        bulk = reverse("management_request_bulk")
        self.assertRedirects(self.client.post(bulk, {"ids": [self.quote.pk], "action": CustomerRequest.STATUS_DONE}), reverse("management_requests"))
        self.assertContains(self.client.post(self.quote_detail, stale), "Запрос уже изменён.")
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.status, CustomerRequest.STATUS_DONE)
        self.assertEqual(self.quote.created_at, created)
        self.assertEqual(self.quote.text, "Изменённые параметры")
        temporary_request = CustomerRequest.objects.create(name="Разовый запрос", email="one@example.test", text="Тест удаления")
        self.assertRedirects(self.client.post(bulk, {"ids": [temporary_request.pk], "action": "delete"}), reverse("management_requests"))
        self.assertFalse(CustomerRequest.objects.filter(pk=temporary_request.pk).exists())
        self.assertTrue(CustomerRequest.objects.filter(pk=self.quote.pk).exists())

    def test_request_and_employee_records_require_staff(self):
        for user in (None, self.customer):
            with self.subTest(user=user):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                for url in (self.employee_detail, self.employee_edit, self.quote_detail, self.quote_detail + "?edit=1"):
                    response = self.client.get(url)
                    self.assertTrue(response.url.startswith(reverse("management_login")))
                response = self.client.post(self.quote_detail, self.quote_payload(status=CustomerRequest.STATUS_DONE))
                self.assertEqual(response.status_code, 302)
                self.quote.refresh_from_db()
                self.assertEqual(self.quote.status, CustomerRequest.STATUS_NEW)
