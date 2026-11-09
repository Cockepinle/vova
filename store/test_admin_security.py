from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AdminLoginAttempt, AdminLoginThrottleBucket


class AdminLoginSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.staff = users.objects.create_user("panel-admin", "admin@example.test", "strong-password", is_staff=True)
        cls.customer = users.objects.create_user("ordinary-customer", "customer@example.test", "customer-password")

    def post_login(self, username, password, path=None):
        return self.client.post(
            path or reverse("management_login"),
            {"username": username, "password": password},
        )

    def test_public_pages_do_not_disclose_management_login_url(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, reverse("management_login"))
        self.assertNotContains(response, "/admin/")

    def test_admin_and_cms_login_routes_use_staff_only_login(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)
        response = self.post_login("ordinary-customer", "customer-password")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(AdminLoginAttempt.objects.latest("created_at").outcome, AdminLoginAttempt.OUTCOME_FAILURE)

        response = self.post_login(
            "panel-admin",
            "strong-password",
            path="/admin/login/",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("admin:index"))
        attempt = AdminLoginAttempt.objects.latest("created_at")
        self.assertEqual(attempt.outcome, AdminLoginAttempt.OUTCOME_SUCCESS)
        self.assertEqual(attempt.user, self.staff)

    def test_failed_attempts_are_logged_and_temporarily_blocked(self):
        for _ in range(5):
            self.post_login("panel-admin", "wrong-password")

        response = self.post_login("panel-admin", "strong-password")
        self.assertContains(response, "Вход временно ограничен")
        self.assertEqual(
            AdminLoginAttempt.objects.filter(outcome=AdminLoginAttempt.OUTCOME_FAILURE).count(),
            5,
        )
        self.assertEqual(
            AdminLoginAttempt.objects.filter(outcome=AdminLoginAttempt.OUTCOME_BLOCKED).count(),
            1,
        )
        self.assertTrue(AdminLoginThrottleBucket.objects.filter(locked_until__gt=timezone.now()).exists())

    def test_lockout_expires_and_successful_login_clears_failed_attempts(self):
        for _ in range(5):
            self.post_login("panel-admin", "wrong-password")

        later = timezone.now() + timedelta(minutes=16)
        with patch("store.security.timezone.now", return_value=later):
            response = self.post_login("panel-admin", "strong-password")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("management_dashboard"))
        self.assertFalse(
            AdminLoginThrottleBucket.objects.filter(locked_until__gt=later).exists()
        )
        self.assertEqual(AdminLoginAttempt.objects.latest("created_at").outcome, AdminLoginAttempt.OUTCOME_SUCCESS)

    def test_management_endpoints_remain_staff_protected(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("management_orders")).status_code, 302)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)
        self.assertEqual(self.client.get(reverse("api_management_orders")).status_code, 302)
