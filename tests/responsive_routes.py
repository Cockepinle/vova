"""Run with python tests/responsive_routes.py in a project environment with Playwright.

The audit creates its own SQLite database, media directory, and loopback server.
PAKLINE_AUDIT_ENGINES selects engines (default: chromium).
PAKLINE_AUDIT_PATH can limit the layout pass to paths containing a substring.
"""
import os
import re
from pathlib import Path
import sys
import traceback
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


VIEWPORTS = [(width, 844) for width in (320, 360, 375, 390, 393, 414, 430, 768, 1024, 1280, 1440, 1920)]
VIEWPORTS += [(667, 375), (852, 393)]
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
        self.subcategory = Category.objects.create(name="Audit subcategory", parent=self.category)
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
        self.category.image_media = self.media
        self.category.save(update_fields=["image_media"])
        self.order = Order.objects.create(user=self.customer, full_name="Audit Buyer", email="buyer@example.test", total=250)
        OrderItem.objects.create(order=self.order, product=self.product, product_name=self.product.name, quantity=2, price=125, line_total=250)
        self.promotion = Promotion.objects.create(title="Audit promotion")
        self.promotion.products.add(self.product)
        self.page = PageContent.objects.create(
            page="custom-audit", is_custom=True, slug="audit-page", title="Audit page", is_visible=True, content_text="Audit content",
            draft_structure=[{"id": "image-audit", "type": "image", "content": {"url": self.media.file.url}}],
        )
        site = SiteSettings.get_solo()
        site.show_header_cta = True
        site.site_name = "PakLine " + "X" * 36
        site.header_phone = "+7 (999) 123-45-67"
        site.header_email = "long-commercial-contact@pakline.example"
        site.save(update_fields=["show_header_cta", "site_name", "header_phone", "header_email"])

    def public_routes(self):
        return [
            "/", reverse("catalog"), reverse("catalog") + "?category=" + self.category.slug,
            reverse("catalog") + "?category=" + self.subcategory.slug,
            reverse("catalog") + "?q=Audit", reverse("product_detail", args=[self.product.slug]),
            reverse("promotions"), reverse("promotion_detail", args=[self.promotion.pk]), reverse("team"), reverse("contacts"),
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
            *(reverse("management_page_edit", args=[PageContent.objects.get(page=key).pk]) for key in ("privacy", "offer")),
            *(reverse("management_pages") + f"?section={section}" for section in ("texts", "images", "banners", "blocks")),
            *(reverse("management_page_edit", args=[self.page.pk]) + f"?tab={tab}" for tab in ("banners", "images", "properties", "seo")),
            reverse("management_page_blocks", args=[self.page.pk]) + "?block=0",
            reverse("management_page_builder", args=[self.page.pk]),
        ]
        return urls

    def check_navigation(self, page):
        page.goto(self.live_server_url + "/")
        for width in (768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 844})
            contact = page.locator(".header-contact")
            expect(contact.locator("a").first).to_have_css("font-size", "16px")
            expect(contact.locator("a").last).to_have_css("font-size", "14px")
            expect(contact.locator("a").first).to_have_attribute("href", "tel:+79991234567")
            expect(contact.locator("a").last).to_have_attribute("href", "mailto:long-commercial-contact@pakline.example")
            assert not page.evaluate(LAYOUT), (width, page.evaluate(LAYOUT))

        for route in ("home", "catalog", "team", "contacts", "promotions"):
            page.goto(self.live_server_url + reverse(route))
            for width in (320, 360, 375, 390, 414, 430):
                page.set_viewport_size({"width": width, "height": 844})
                page.locator(".mobile-menu-toggle").click()
                active = page.locator(".main-nav > a[aria-current=page]")
                expect(active).to_have_count(1)
                expect(active).to_have_attribute("href", reverse(route))
                expect(active.locator("span")).to_have_css("text-decoration-line", "underline")
                expect(page.locator(".mobile-nav-contact a").last).to_have_attribute(
                    "href", "mailto:long-commercial-contact@pakline.example",
                )
                assert active.evaluate("(el) => { const a=el.getBoundingClientRect(), b=el.firstElementChild.getBoundingClientRect(); return Math.abs(a.left+a.width/2-b.left-b.width/2)<1 && getComputedStyle(el, '::after').content==='none'; }")
                page.keyboard.press("Escape")

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
            response = page.goto(self.live_server_url + path, wait_until="domcontentloaded", timeout=30000)
            if not response or response.status != 200:
                failures.append((path, response.status if response else "no response"))
                continue
            for width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
                if overflow := page.evaluate(LAYOUT):
                    failures.append((path, f"{width}x{height}", overflow))

    def capture(self, page, name):
        if output := os.environ.get("PAKLINE_AUDIT_SCREENSHOTS"):
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=directory / f"{name}.png", animations="disabled")

    def favorite_navigation(self, page):
        page.set_viewport_size({"width": 393, "height": 852})
        page.goto(self.live_server_url + reverse("catalog") + "?category=" + self.category.slug)
        page.wait_for_function("typeof window.toggleFavoriteProduct === 'function'")
        first = page.locator(".catalog-card .favorite-button").first
        with page.expect_response(lambda response: response.url.endswith("/favorites/toggle/")) as response:
            first.click()
        assert response.value.ok
        nav = page.locator(".mobile-actions")
        nav.locator(".js-favorites-open").click()
        favorite = page.locator(".favorite-item").first
        expect(favorite).to_be_visible()
        expect(nav.locator(".js-favorites-open")).to_have_attribute("aria-expanded", "true")
        expect(nav).to_be_visible()
        for width, height in ((320, 568), (667, 375), (393, 852)):
            page.set_viewport_size({"width": width, "height": height})
            assert not page.evaluate(LAYOUT)
            page.wait_for_function("""() => {
                const drawer = document.querySelector(".favorites-drawer").getBoundingClientRect();
                const bar = document.querySelector(".mobile-actions").getBoundingClientRect();
                return drawer.bottom <= bar.top + 1;
            }""")
        add = favorite.locator(".favorite-add-cart")
        remove = favorite.locator(".favorite-remove-cart")
        expect(remove).to_be_hidden()
        add.click()
        expect(add).to_have_text("В корзине")
        expect(remove).to_be_visible()
        expect(nav.locator("[data-cart-count]")).to_have_text("2")
        self.capture(page, "mobile-favorites")
        remove.click()
        expect(add).to_have_text("В корзину")
        expect(remove).to_be_hidden()
        expect(nav.locator("[data-cart-count]")).to_have_text("0")
        expect(favorite).to_be_visible()
        expect(nav.locator(".favorite-count")).to_have_text("1")
        nav.locator(".js-account-open").click()
        expect(page.locator(".account-drawer")).to_be_visible()
        expect(nav.locator(".js-account-open")).to_have_attribute("aria-expanded", "true")
        expect(page.locator(".favorites-drawer")).to_be_hidden()
        self.capture(page, "mobile-profile")
        nav.locator(".js-cart-open").click()
        expect(page.locator(".cart-drawer")).to_be_visible()
        expect(page.locator(".account-drawer")).to_be_hidden()
        nav.locator(".js-favorites-open").click()
        expect(favorite).to_be_visible()

    def category_and_promotions(self, page):
        page.set_viewport_size({"width": 393, "height": 852})
        page.goto(self.live_server_url + reverse("management_categories"))
        root = page.locator(f'tr[data-category-id="{self.category.pk}"]')
        child = page.locator(f'tr[data-category-id="{self.subcategory.pk}"]')
        root.locator("[data-category-branch]").click()
        expect(child).to_be_visible()
        expect(root.locator(".category-tree-name img")).to_be_visible()
        page.locator("[data-category-select-all]").check()
        expect(child.locator('[name="ids"]')).to_be_checked()
        for width, height in ((320, 568), (667, 375), (393, 852)):
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
            title = root.locator(".category-tree-name strong").bounding_box()
            assert title["width"] >= 75, (width, title, root.bounding_box())
            status = root.locator(".status-select + details, .status-select:visible").first
            assert status.bounding_box()["width"] >= 135
            assert not page.evaluate(LAYOUT)
        self.capture(page, "mobile-categories")
        select = root.locator(".status-select")
        if select.is_visible():
            select.select_option("hidden")
        else:
            dropdown = root.locator(".status-select + details")
            dropdown.locator("summary").click()
            dropdown.get_by_role("button", name="Скрыто", exact=True).click()
        page.get_by_role("button", name="Сохранить статусы").click()
        expect(select).to_have_value("hidden")
        page.goto(self.live_server_url + reverse("management_product_edit", args=[self.product.pk]))
        picker = page.locator("[data-product-promotions]")
        option = picker.get_by_role("checkbox", name=re.compile(self.promotion.title))
        expect(option).to_be_checked()
        picker.locator("input[type=search]").fill("no match")
        expect(option).to_be_hidden()
        picker.locator("input[type=search]").fill("Audit")
        expect(option).to_be_visible()
        option.uncheck()
        page.get_by_role("button", name="Сохранить", exact=True).click()
        expect(page.get_by_text("Товар сохранён.")).to_be_visible()
        expect(option).not_to_be_checked()

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
        expect(page.locator(".catalog-card .add-to-cart").first).to_have_text("В корзине")
        page.locator(".mobile-actions .js-cart-open").click()
        expect(page.locator(".cart-drawer")).to_have_attribute("aria-hidden", "false")
        assert not page.evaluate(LAYOUT)
        page.locator(".cart-checkout").click()
        checkout = page.locator(".checkout-panel")
        expect(checkout).to_be_visible()
        expect(page.locator("body")).to_have_class(re.compile("overlay-scroll-locked"))
        for width in (320, 390, 768, 1024):
            page.set_viewport_size({"width": width, "height": 780})
            assert not page.evaluate(LAYOUT), (width, "checkout", page.evaluate(LAYOUT))
        page.set_viewport_size({"width": 360, "height": 800})
        checkout.locator('[name="full_name"]').fill("Browser Buyer")
        checkout.locator('[name="phone"]').fill("+79990001234")
        checkout.locator('[name="email"]').fill(self.customer.email)
        checkout.locator('[name="phone"]').focus()
        page.evaluate("""() => {
            Object.defineProperty(visualViewport, 'height', {configurable: true, value: 430});
            visualViewport.dispatchEvent(new Event('resize'));
        }""")
        expect(page.locator("body")).to_have_class(re.compile("keyboard-open"))
        assert checkout.bounding_box()["height"] <= 431
        page.evaluate("""() => {
            delete visualViewport.height;
            visualViewport.dispatchEvent(new Event('resize'));
        }""")
        expect(page.locator("body")).not_to_have_class(re.compile("keyboard-open"))
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
                theme = os.environ.get("PAKLINE_AUDIT_THEME", "dark")
                context = browser.new_context(color_scheme=theme, reduced_motion="reduce")
                page = context.new_page()
                page.set_default_timeout(6500)
                errors = []
                page.on("pageerror", lambda error: errors.append((page.url, str(error))))
                if os.environ.get("PAKLINE_AUDIT_ROUTES", "1") == "1":
                    self.audit(page, public, failures)
                if os.environ.get("PAKLINE_AUDIT_ACTIONS", "1") == "1":
                    try:
                        self.check_navigation(page)
                        self.public_actions(page)
                        self.favorite_navigation(page)
                    except (AssertionError, BrowserError) as error:
                        failures.append((engine, "public interactions", traceback.format_exc()))
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME, "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                    "url": self.live_server_url,
                }])
                if os.environ.get("PAKLINE_AUDIT_ROUTES", "1") == "1":
                    self.audit(page, cms, failures)
                if os.environ.get("PAKLINE_AUDIT_ACTIONS", "1") == "1":
                    try:
                        self.cms_actions(page)
                        self.category_and_promotions(page)
                    except (AssertionError, BrowserError) as error:
                        failures.append((engine, "CMS interactions", traceback.format_exc()))
                if os.environ.get("PAKLINE_AUDIT_NATIVE", "1") == "1" and os.environ.get("PAKLINE_AUDIT_ROUTES", "1") == "1":
                    self.audit(page, native, failures)
                if os.environ.get("PAKLINE_AUDIT_NATIVE", "1") == "1" and os.environ.get("PAKLINE_AUDIT_ACTIONS", "1") == "1":
                    try:
                        self.django_admin_actions(page)
                    except (AssertionError, BrowserError) as error:
                        failures.append((engine, "Django admin interactions", str(error)))
                print(f"{engine}/{theme}: {len(public)} public/login, {len(cms)} CMS, {len(native)} Django admin routes enumerated", flush=True)
                for error in errors:
                    failures.append((engine, "JavaScript", error))
                browser.close()
        for failure in failures:
            print(repr(failure), flush=True)
        if failures:
            self.fail(f"{len(failures)} route/layout/JavaScript failures")


if __name__ == "__main__":
    raise SystemExit(bool(DiscoverRunner(debug_mode=True, interactive=False).run_tests(["__main__"])))
