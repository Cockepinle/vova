"""Run with python tests/responsive_routes.py in a project environment with Playwright.

The audit creates its own SQLite database, media directory, and loopback server.
PAKLINE_AUDIT_ENGINES selects engines (default: chromium).
PAKLINE_AUDIT_PATH can limit the layout pass to paths containing a substring.
"""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

scratch = TemporaryDirectory()
os.environ.update(
    DJANGO_SETTINGS_MODULE="vova.settings", DATABASE_URL="", DEBUG="1",
    SECRET_KEY="isolated-responsive-audit", CLOUDINARY_URL="", VERCEL="",
    MEDIA_ROOT=scratch.name, MEDIA_URL="/media/",
    ALLOWED_HOSTS="localhost,127.0.0.1,testserver",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)

import django
from django.conf import settings

assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
settings.DATABASES["default"]["NAME"] = str(Path(scratch.name) / "audit.sqlite3")
django.setup()

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test.runner import DiscoverRunner
from django.urls import reverse
from playwright.sync_api import Error as BrowserError, expect, sync_playwright

from store.models import (
    AttributeDefinition, Category, CustomerRequest, DeliveryMethod, Employee,
    Order, OrderItem, PageContent, PaymentMethod, Product, ProductImage, Promotion,
    SiteMedia, SiteSettings, VariantGroup,
)
from store.test_media_uploads import image_file


WIDTHS = (320, 360, 375, 390, 430, 768, 1024, 1280, 1440, 1920)
LAYOUT = """() => {
  const doc = document.documentElement;
  const containers = [doc, ...document.querySelectorAll('.header-inner, .catalog-content, .contact-layout, .mgmt-main, .record-table-wrap, .checkout-panel, .cart-panel, .drawer-panel, .modal-card, .media-picker-dialog')];
  return containers.filter(el => el.clientWidth && el.scrollWidth > el.clientWidth + 2 &&
    !el.closest('[aria-hidden="true"], [hidden]') &&
    !(el.classList.contains('record-table-wrap') && ['auto','scroll'].includes(getComputedStyle(el).overflowX))).map(el => {
      const bounds = el.getBoundingClientRect();
      const suspects = [...el.querySelectorAll('*')].filter(item => {
        const box = item.getBoundingClientRect();
        return box.width && box.right > bounds.right + 2 &&
          !item.closest('.table-wrap, .product-gallery-track, .gallery-thumbnails, .nav-icon-defs') &&
          (location.pathname.startsWith('/admin/') || !item.closest('[aria-hidden="true"]'));
      }).slice(0, 8).map(item => [item.tagName + '.' + (item.getAttribute('class') || ''), item.id,
        Math.round(item.getBoundingClientRect().right)]);
      if (!suspects.length) {
        suspects.push(...[...el.querySelectorAll('*')].filter(item => item.clientWidth && item.scrollWidth > item.clientWidth + 8)
          .slice(0, 14).map(item => [item.tagName, item.id, item.getAttribute('class'), item.clientWidth,
            item.scrollWidth, getComputedStyle(item).overflowX]));
      }
      return [el.tagName + '.' + el.className, el.clientWidth, el.scrollWidth, suspects];
    });
}"""


class ResponsiveAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    def setUp(self):
        users = get_user_model()
        self.staff = users.objects.create_superuser("audit-admin", "admin@example.test", "audit-password")
        self.customer = users.objects.create_user("buyer@example.test", "buyer@example.test", "audit-password")
        self.category = Category.objects.create(name="Audit packaging")
        self.field = AttributeDefinition.objects.create(name="Material", value_type="choice", choices=["Cardboard"])
        self.category.filter_attributes.add(self.field)
        self.group = VariantGroup.objects.create(name="Audit variants")
        self.group.attributes.add(self.field)
        self.product = Product.objects.create(
            category=self.category, variant_group=self.group, name="Audit Box " + "W" * 75,
            sku="AUD-01", price=125, stock_quantity=100, status=Product.STATUS_PUBLISHED,
            min_quantity=2,
        )
        self.product.image.save("cover.png", image_file("cover.png"))
        linked = ProductImage.objects.create(product=self.product)
        linked.image.save("detail.png", image_file("detail.png"))
        self.product.attributes.create(attribute=self.field, value_choice="Cardboard")
        self.employee = Employee.objects.create(name="Audit Employee", role="Sales", status=Employee.STATUS_PUBLISHED)
        self.quote = CustomerRequest.objects.create(name="Audit Buyer", email="buyer@example.test", text="Boxes needed")
        self.media = SiteMedia.objects.create(title="Audit photo", file=image_file("photo.webp", "WEBP"))
        self.order = Order.objects.create(user=self.customer, full_name="Audit Buyer", email="buyer@example.test", total=250)
        OrderItem.objects.create(order=self.order, product=self.product, product_name=self.product.name, quantity=2, price=125, line_total=250)
        self.promotion = Promotion.objects.create(title="Audit promotion")
        self.page = PageContent.objects.create(
            page="custom-audit", is_custom=True, slug="audit-page", title="Audit page", is_visible=True, content_text="Audit content",
            draft_structure=[{"id": "image-audit", "type": "image", "content": {"url": self.media.file.url}}],
        )
        site = SiteSettings.get_solo()
        site.show_header_cta = True
        site.site_name = "PakLine " + "X" * 36
        site.save(update_fields=["show_header_cta", "site_name"])

    def public_routes(self):
        return [
            "/", reverse("catalog"), reverse("catalog") + "?category=" + self.category.slug,
            reverse("catalog") + "?q=Audit", reverse("product_detail", args=[self.product.slug]),
            reverse("promotions"), reverse("team"), reverse("contacts"),
            reverse("document_page", args=["privacy"]), reverse("document_page", args=["offer"]),
            reverse("custom_page", args=[self.page.slug]), reverse("management_login"), reverse("admin_login"),
        ]

    def cms_routes(self):
        routes = [
            ("dashboard",), ("products",), ("product_new",), ("product_edit", self.product.pk), ("product_import",),
            ("variant_groups",), ("variant_group_new",), ("variant_group_edit", self.group.pk),
            ("customers",), ("customer_detail", self.customer.pk),
            ("promotions",), ("promotion_new",), ("promotion_edit", self.promotion.pk),
            ("payment_methods",), ("payment_method_new",), ("payment_method_edit", PaymentMethod.objects.first().pk),
            ("delivery_methods",), ("delivery_method_new",), ("delivery_method_edit", DeliveryMethod.objects.first().pk),
            ("orders",), ("order_detail", self.order.pk),
            ("categories",), ("category_new",), ("category_edit", self.category.pk),
            ("employees",), ("employee_new",), ("employee_detail", self.employee.pk), ("employee_edit", self.employee.pk),
            ("fields",), ("field_new",), ("field_edit", self.field.pk),
            ("media",), ("settings",), ("requests",), ("request_detail", self.quote.pk),
            ("pages",), ("page_new",), ("page_edit", self.page.pk), ("page_blocks", self.page.pk),
        ]
        urls = [reverse(f"management_{name}", args=args) for name, *args in routes]
        urls += [
            reverse("management_request_detail", args=[self.quote.pk]) + "?edit=1",
            reverse("management_settings") + "?tab=brand",
            *(reverse("management_pages") + f"?section={section}" for section in ("texts", "images", "banners", "blocks")),
            *(reverse("management_page_edit", args=[self.page.pk]) + f"?tab={tab}" for tab in ("banners", "images", "properties", "seo")),
            reverse("management_page_blocks", args=[self.page.pk]) + "?block=0",
            reverse("management_page_builder", args=[self.page.pk]),
        ]
        return urls

    def django_admin_routes(self):
        routes = [reverse("admin:index")]
        for model, model_admin in admin.site._registry.items():
            prefix = f"admin:{model._meta.app_label}_{model._meta.model_name}"
            routes.append(reverse(f"{prefix}_changelist"))
            if model_admin.has_add_permission(self.admin_request):
                routes.append(reverse(f"{prefix}_add"))
            obj = model._default_manager.first()
            if obj is not None and model_admin.get_queryset(self.admin_request).filter(pk=obj.pk).exists():
                routes.append(reverse(f"{prefix}_change", args=[obj.pk]))
        return routes

    def audit(self, page, paths, failures):
        for path in paths:
            if os.environ.get("PAKLINE_AUDIT_PATH", "") not in path:
                continue
            response = page.goto(self.live_server_url + path, wait_until="domcontentloaded")
            if not response or response.status != 200:
                failures.append((path, response.status if response else "no response"))
                continue
            for width in WIDTHS:
                page.set_viewport_size({"width": width, "height": 844})
                page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
                if overflow := page.evaluate(LAYOUT):
                    failures.append((path, width, overflow))

    def public_actions(self, page):
        page.set_viewport_size({"width": 320, "height": 390})
        page.goto(self.live_server_url + "/")
        page.locator(".mobile-menu-toggle").click()
        expect(page.locator(".main-nav")).to_be_visible()
        expect(page.locator(".mobile-nav-cta")).to_be_visible()
        assert page.locator(".main-nav").bounding_box()["y"] >= 0
        page.keyboard.press("Escape")
        expect(page.locator(".main-nav")).to_be_hidden()
        expect(page.locator(".mobile-menu-toggle")).to_be_focused()
        page.locator(".js-cookie-settings").click()
        expect(page.locator(".cookie-panel")).to_be_visible()
        page.locator(".cookie-submit").click()
        expect(page.locator(".cookie-modal")).to_have_attribute("aria-hidden", "true")

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(self.live_server_url + reverse("contacts"))
        request_form = page.locator(".request-form")
        request_form.locator('[name="name"]').fill("Browser Buyer")
        request_form.locator('[name="email"]').fill("quote@example.test")
        request_form.locator('[name="text"]').fill("Two boxes for testing")
        page.route("**/requests/create/", lambda route: route.abort(), times=1)
        request_form.locator('button[type="submit"]').click()
        expect(page.locator(".request-message.is-error")).to_be_visible()
        expect(request_form.locator('[name="text"]')).to_have_value("Two boxes for testing")
        with page.expect_response(lambda response: response.url.endswith("/requests/create/")) as quote_response:
            request_form.locator('button[type="submit"]').click()
        assert quote_response.value.ok
        expect(page.locator(".request-message")).to_be_visible()

        catalog = reverse("catalog") + "?category=" + self.category.slug
        page.goto(self.live_server_url + catalog)
        page.locator(".catalog-category-open").click()
        expect(page.locator(".catalog-mobile-category-tree")).to_have_attribute("aria-hidden", "false")
        page.set_viewport_size({"width": 1024, "height": 844})
        expect(page.locator(".catalog-mobile-category-tree")).to_have_attribute("aria-hidden", "true")
        page.set_viewport_size({"width": 390, "height": 844})
        page.locator(".catalog-filter-open:visible").click()
        filters = page.locator("#catalog-mobile-filter-panel")
        expect(filters).to_have_attribute("aria-hidden", "false")
        filters.locator(f'select[name="filter_{self.field.pk}"]').select_option("Cardboard")
        filters.locator('button[type="submit"]').click()
        assert f"filter_{self.field.pk}=Cardboard" in page.url
        page.locator(".catalog-sort-open").click()
        sort = page.locator("#catalog-mobile-sort-panel")
        expect(sort).to_have_attribute("aria-hidden", "false")
        sort.locator('select[name="sort"]').select_option("price_desc")
        sort.locator('button[type="submit"]').click()
        assert "sort=price_desc" in page.url
        search = page.locator('.catalog-search-mobile input[type="search"]')
        search.fill("AUD-01")
        expect(page.locator(".catalog-search-mobile .catalog-search-suggestion")).to_be_visible()
        search.press("Enter")
        expect(page.locator(".catalog-card")).to_have_count(1)

        page.locator(".open-product").first.click()
        expect(page.locator("[data-detail-gallery]")).to_be_visible()
        page.goto(self.live_server_url + "/")
        page.locator(".product-card").first.press("Enter")
        expect(page.locator(".product-modal")).to_have_attribute("aria-hidden", "false")
        for width, height in ((320, 568), (390, 844), (768, 844), (1024, 768)):
            page.set_viewport_size({"width": width, "height": height})
            assert not page.evaluate(LAYOUT), (width, "product modal", page.evaluate(LAYOUT))
        page.keyboard.press("Escape")
        expect(page.locator(".product-modal")).to_have_attribute("aria-hidden", "true")
        page.goto(self.live_server_url + reverse("product_detail", args=[self.product.slug]))
        page.locator(".product-detail-gallery-thumbnail").last.click()
        expect(page.locator(".product-detail-gallery-thumbnail").last).to_have_attribute("aria-current", "true")
        page.locator("[data-detail-gallery-zoom]").click()
        expect(page.locator(".image-lightbox")).to_have_attribute("aria-hidden", "false")
        page.keyboard.press("Escape")
        expect(page.locator(".image-lightbox")).to_have_attribute("aria-hidden", "true")

        page.set_viewport_size({"width": 360, "height": 800})
        page.locator(".mobile-actions .js-favorites-open").click()
        expect(page.locator(".account-drawer")).to_have_attribute("aria-hidden", "false")
        page.locator('.account-tab[data-tab="register"]').click()
        expect(page.locator(".account-form-register")).to_be_visible()
        page.locator('.account-tab[data-tab="login"]').click()
        page.locator(".account-reset-open").click()
        expect(page.locator(".account-form-reset")).to_be_visible()
        page.locator(".account-back-login").click()
        login = page.locator(".account-form-login")
        login.locator('[name="email"]').fill(self.customer.email)
        login.locator('[name="password"]').fill("wrong-password")
        with page.expect_response(lambda response: response.url.endswith("/account/login/")) as denied:
            login.locator('button[type="submit"]').click()
        assert denied.value.status == 400
        expect(page.locator(".account-message.is-error")).to_be_visible()
        login.locator('[name="password"]').fill("audit-password")
        with page.expect_response(lambda response: response.url.endswith("/account/login/")) as login_response:
            login.locator('button[type="submit"]').click()
        assert login_response.value.ok
        expect(page.locator(".account-current")).to_be_attached()
        page.goto(self.live_server_url + catalog)
        page.locator(".mobile-actions .js-favorites-open").click()
        expect(page.locator(".favorites-drawer")).to_have_attribute("aria-hidden", "false")
        page.keyboard.press("Escape")
        page.locator(".catalog-card .add-to-cart").first.click()
        expect(page.locator(".cart-drawer")).to_have_attribute("aria-hidden", "false")
        assert not page.evaluate(LAYOUT)
        page.locator(".cart-checkout").click()
        checkout = page.locator(".checkout-panel")
        expect(checkout).to_be_visible()
        for width in (320, 390, 768, 1024):
            page.set_viewport_size({"width": width, "height": 780})
            assert not page.evaluate(LAYOUT), (width, "checkout", page.evaluate(LAYOUT))
        page.set_viewport_size({"width": 360, "height": 800})
        checkout.locator('[name="full_name"]').fill("Browser Buyer")
        checkout.locator('[name="phone"]').fill("+79990001234")
        checkout.locator('[name="email"]').fill(self.customer.email)
        assert not page.evaluate(LAYOUT)
        with page.expect_response(lambda response: response.url.endswith("/cart/checkout/")) as checkout_response:
            checkout.locator(".checkout-submit").click()
        assert checkout_response.value.ok, checkout_response.value.json()
        expect(checkout.locator(".checkout-message")).to_be_visible()

    def cms_actions(self, page):
        page.set_viewport_size({"width": 320, "height": 568})
        page.goto(self.live_server_url + reverse("management_dashboard"))
        toggle = page.locator("[data-management-menu-toggle]")
        navigation = page.locator("#management-navigation")
        expect(navigation).to_be_hidden()
        toggle.click()
        expect(navigation).to_be_visible()
        navigation.locator("summary").first.focus()
        page.keyboard.press("Escape")
        expect(navigation).to_be_hidden()
        expect(toggle).to_be_focused()

        page.goto(self.live_server_url + reverse("management_employee_edit", args=[self.employee.pk]))
        editor = page.locator(".mgmt-form")
        editor.locator('[name="role"]').fill("Browser audit")
        editor.locator('button[type="submit"]').click()
        expect(page.locator(".record-profile")).to_contain_text("Browser audit")
        page.goto(self.live_server_url + reverse("management_request_detail", args=[self.quote.pk]) + "?edit=1")
        editor = page.locator("form.record-detail")
        editor.locator('[name="status"]').select_option("processing")
        editor.locator('button[type="submit"]').click()
        expect(page.locator(".record-detail .status-processing")).to_be_visible()

        page.goto(self.live_server_url + reverse("management_settings") + "?tab=brand")
        page.locator("[data-content-image] .media-picker-field-actions button").first.click()
        picker = page.locator("[data-media-picker]")
        expect(picker).to_be_visible()
        expect(picker.locator(".media-picker-item").filter(has_text="Audit photo")).to_be_visible()
        assert not page.evaluate(LAYOUT)
        page.keyboard.press("Escape")
        expect(picker).to_be_hidden()
        expect(page.locator("[data-content-image] .media-picker-field-actions button").first).to_be_focused()

        page.goto(self.live_server_url + reverse("management_order_detail", args=[self.order.pk]))
        status = page.locator('select[name="status"]')
        status.select_option("processing")
        status.locator("xpath=ancestor::form").locator('button[type="submit"]').click()
        expect(status).to_have_value("processing")

    def django_admin_actions(self, page):
        page.set_viewport_size({"width": 320, "height": 568})
        page.goto(self.live_server_url + self.native_value_url)
        widget = page.locator(".field-product .select2-selection")
        widget.click()
        search = page.locator(".select2-search__field:visible")
        search.fill("AUD-01")
        result = page.locator(".select2-results__option").filter(has_text=self.product.name)
        expect(result).to_be_visible()
        assert not page.evaluate(LAYOUT), page.evaluate(LAYOUT)
        page.keyboard.press("Escape")
        expect(search).to_be_hidden()

    def test_browser_routes(self):
        failures = []
        self.client.force_login(self.staff)
        self.admin_request = self.client.get(reverse("management_dashboard")).wsgi_request
        self.native_value_url = reverse("admin:store_productattribute_change", args=[self.product.attributes.get().pk])
        public = self.public_routes()
        cms = self.cms_routes()
        native = self.django_admin_routes()
        for engine in os.environ.get("PAKLINE_AUDIT_ENGINES", "chromium").split(","):
            with sync_playwright() as playwright:
                browser = getattr(playwright, engine).launch()
                context = browser.new_context(color_scheme="dark", reduced_motion="reduce")
                page = context.new_page()
                page.set_default_timeout(6500)
                errors = []
                page.on("pageerror", lambda error: errors.append((page.url, str(error))))
                if os.environ.get("PAKLINE_AUDIT_ROUTES", "1") == "1":
                    self.audit(page, public, failures)
                if os.environ.get("PAKLINE_AUDIT_ACTIONS", "1") == "1":
                    try:
                        self.public_actions(page)
                    except (AssertionError, BrowserError) as error:
                        failures.append((engine, "public interactions", str(error)))
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME, "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                }])
                if os.environ.get("PAKLINE_AUDIT_ROUTES", "1") == "1":
                    self.audit(page, cms, failures)
                if os.environ.get("PAKLINE_AUDIT_ACTIONS", "1") == "1":
                    try:
                        self.cms_actions(page)
                    except (AssertionError, BrowserError) as error:
                        failures.append((engine, "CMS interactions", str(error)))
                if os.environ.get("PAKLINE_AUDIT_NATIVE", "1") == "1" and os.environ.get("PAKLINE_AUDIT_ROUTES", "1") == "1":
                    self.audit(page, native, failures)
                if os.environ.get("PAKLINE_AUDIT_NATIVE", "1") == "1" and os.environ.get("PAKLINE_AUDIT_ACTIONS", "1") == "1":
                    try:
                        self.django_admin_actions(page)
                    except (AssertionError, BrowserError) as error:
                        failures.append((engine, "Django admin interactions", str(error)))
                print(f"{engine}: {len(public)} public/login, {len(cms)} CMS, {len(native)} Django admin routes enumerated", flush=True)
                for error in errors:
                    failures.append((engine, "JavaScript", error))
                browser.close()
        for failure in failures:
            print(repr(failure), flush=True)
        if failures:
            self.fail(f"{len(failures)} route/layout/JavaScript failures")


if __name__ == "__main__":
    raise SystemExit(bool(DiscoverRunner(debug_mode=True, interactive=False).run_tests(["__main__"])))
