"""Run with python tests/catalog_storefront_audit.py and Playwright Chromium."""
import re
from io import BytesIO

from responsive_routes import ResponsiveAudit, DiscoverRunner, expect, reverse, sync_playwright
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from store.models import Category, PageContent, Product


class CatalogStorefrontAudit(ResponsiveAudit):
    def test_storefront(self):
        demo_subtitle = "Демонстрационные размеры и цены. Подтвердите параметры, наличие и стоимость перед оформлением заказа."
        PageContent.objects.update_or_create(page="catalog", defaults={"subtitle": demo_subtitle})
        parent = Category.objects.create(name="Boxes " + "W" * 45)
        self.category.parent = parent
        self.category.save(update_fields=["parent"])
        for category, size in ((parent, (80, 300)), (self.category, (300, 80))):
            image = BytesIO()
            Image.new("RGB", size, "navy").save(image, format="PNG")
            category.image.save("category.png", ContentFile(image.getvalue()))
        for index in range(12):
            Category.objects.create(name=f"Extra category {index}")
        variants = [
            Product.objects.create(
                category=self.category, variant_group=self.group, name=f"Variant {index}",
                sku=f"VAR-{index}", price=55 + index, status=Product.STATUS_PUBLISHED,
                min_quantity=3, quantity_step=2, stock_quantity=50,
            )
            for index in range(7)
        ]
        selected = variants[-1]
        variant_photo = BytesIO()
        Image.new("RGB", (180, 120), "green").save(variant_photo, format="PNG")
        selected.image.save("selected.png", ContentFile(variant_photo.getvalue()))
        self.client.force_login(self.customer)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            external_requests = re.compile(rf"^https?://(?!{re.escape(self.live_server_url.split('://')[1])}/)")
            context = browser.new_context()
            context.route(external_requests, lambda route: route.abort())
            context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": self.live_server_url}])
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + "/")
            for width in (320, 390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 844})
                media = page.locator(".category-card-media").evaluate_all(
                    "items => items.map(el => [el.offsetWidth, el.offsetHeight])"
                )
                assert len(media) >= 2, media
                assert all(abs(w - h * 4 / 3) < 2 for w, h in media), (width, media)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.locator(f'.category-card[href$="category={self.category.slug}"]').click()
            expect(page).to_have_url(self.live_server_url + f"/catalog/?category={self.category.slug}")

            direct_path = reverse("product_detail", args=[self.product.slug])
            category_path = f"/catalog/?category={self.category.slug}"
            filtered_path = category_path + "&scope=category&q=Variant&sort=price_desc&page=2"
            page.goto(self.live_server_url + filtered_path)
            for width in (320, 375, 430, 768, 1024, 1440, 1920):
                page.set_viewport_size({"width": width, "height": 844})
                cards = page.locator(".catalog-card-image").evaluate_all(
                    "items => items.map(el => [el.offsetWidth, el.offsetHeight, el.getBoundingClientRect().right])"
                )
                assert cards and all(abs(w - h * 5 / 4) < 2 and right <= width for w, h, right in cards), (width, cards)
                if width >= 1024:
                    assert min(w for w, _, _ in cards) >= 260, (width, cards)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), width
            page.set_viewport_size({"width": 375, "height": 844})
            page.locator(".catalog-card .open-product").first.click()
            expect(page.locator(".product-back")).to_have_attribute("href", filtered_path)
            page.locator(".product-back").click()
            expect(page).to_have_url(self.live_server_url + filtered_path)

            page.set_viewport_size({"width": 1440, "height": 900})
            menu = page.locator(".catalog-category-menu")
            menu.locator("summary").press("Enter")
            search = menu.locator("input[type=search]")
            search.fill("Extra category 11")
            expect(menu.locator(".catalog-category-menu-option:visible")).to_have_count(1)
            search.press("Escape")
            expect(menu.locator("summary")).to_be_focused()
            menu.locator("summary").press("Enter")
            search.press("Enter")
            page.keyboard.press("Enter")
            expect(page).to_have_url(re.compile(r"[?&]category=extra-category-11(?:&|$)"))

            page.goto(self.live_server_url + direct_path)
            expect(page.locator(".product-back")).to_have_attribute("href", category_path)
            page.goto(self.live_server_url + direct_path, referer="https://example.org/catalog/?q=external")
            expect(page.locator(".product-back")).to_have_attribute("href", category_path)
            for width in (1440, 768, 320, 390):
                page.set_viewport_size({"width": width, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), width
                expect(page.locator(".product-back")).to_be_visible()
                expect(page.locator(".product-detail-gallery-stage .image-favorite")).to_be_visible()
            selector = page.get_by_role("combobox", name="Вариант товара")
            expect(selector).to_be_visible()
            option = selector.locator(f'option[data-product-url="{reverse("api_product_detail", args=[selected.pk])}"]')
            selector.select_option(value=option.get_attribute("value"))
            expect(page.locator("h1")).to_have_text(selected.name)
            expect(page.locator("[data-detail-sku]")).to_contain_text(selected.sku)
            expect(page.locator("[data-detail-price]")).to_contain_text(str(selected.price))
            expect(page.locator("[data-detail-availability]")).to_have_text(selected.get_availability_display())
            expect(page.locator("[data-detail-main-image]")).to_have_attribute("src", selected.image.url)
            expect(page.locator(".product-detail-purchase .quantity-input")).to_have_attribute("min", "3")
            expect(page.locator(".product-detail-purchase .quantity-input")).to_have_attribute("step", "2")
            page.locator(".product-detail-purchase .quantity-plus").click()
            page.locator(".product-detail-add").click()
            item = page.locator(f'.cart-item[data-product-id="{selected.pk}"]')
            expect(item.locator(".cart-quantity span")).to_have_text("5")
            item.locator(".quantity-plus").click()
            expect(item.locator(".cart-quantity span")).to_have_text("7")
            item.locator(".cart-favorite").click()
            expect(item.locator(".cart-favorite")).to_have_attribute("aria-pressed", "true")
            expect(page.locator(".mobile-actions .favorite-count")).to_have_text("1")
            page.keyboard.press("Escape")
            page.locator(".mobile-actions .js-favorites-open").click()
            favorite = page.locator(f'.favorite-item[data-product-id="{selected.pk}"]')
            favorite.locator(".favorite-remove").click()
            expect(favorite).to_have_count(0)
            page.keyboard.press("Escape")
            expect(page.locator(".mobile-actions .favorite-count")).to_have_text("0")
            expect(page.locator(".mobile-actions [data-cart-count]")).to_have_text("7")
            page.locator(".mobile-actions .js-cart-open").click()
            expect(item.locator(".cart-favorite")).to_have_attribute("aria-pressed", "false")
            expect(item.locator(".cart-quantity span")).to_have_text("7")
            page.reload()
            page.locator(".mobile-actions .js-cart-open").click()
            expect(item.locator(".cart-quantity span")).to_have_text("7")
            item.locator(".cart-favorite").click()
            expect(item.locator(".cart-favorite")).to_have_attribute("aria-pressed", "true")
            item.locator(".cart-remove").click()
            expect(item).to_have_count(0)
            page.keyboard.press("Escape")
            expect(page.locator(".product-detail-gallery-stage .image-favorite")).to_have_attribute("aria-pressed", "true")
            page.locator(".mobile-actions .js-favorites-open").click()
            expect(page.locator(f'.favorite-item[data-product-id="{selected.pk}"]')).to_be_visible()
            page.keyboard.press("Escape")
            page.locator(".product-detail-gallery-stage .image-favorite").click()
            expect(page.locator(".product-detail-gallery-stage .image-favorite")).to_have_attribute("aria-pressed", "false")
            page.goto(self.live_server_url + f"/catalog/?category={self.category.slug}")
            catalog_favorite = page.locator(f'.catalog-card[data-product-id="{selected.pk}"] .favorite-button')
            page.route("**/favorites/toggle/", lambda route: route.abort())
            catalog_favorite.click()
            expect(catalog_favorite).to_have_attribute("aria-pressed", "false")
            expect(catalog_favorite).to_be_enabled()
            page.unroute("**/favorites/toggle/")
            catalog_favorite.click()
            expect(catalog_favorite).to_have_class("favorite-button image-favorite is-active")
            expect(page.locator(".mobile-actions .favorite-count")).to_have_text("1")
            expect(page.locator(".mobile-actions [data-cart-count]")).to_have_text("0")
            context.close()
            touch = browser.new_context(
                is_mobile=True, has_touch=True, viewport={"width": 430, "height": 844},
                color_scheme="dark",
            )
            touch.route(external_requests, lambda route: route.abort())
            mobile = touch.new_page()
            mobile.on("pageerror", lambda error: errors.append(str(error)))
            mobile.goto(self.live_server_url + "/catalog/")
            expect(mobile.get_by_text(demo_subtitle, exact=True)).to_have_count(0)
            expect(mobile.locator("html")).to_have_attribute("data-theme", "dark")
            mobile.locator(".catalog-category-open").tap()
            mobile.locator("#catalog-mobile-category-tree").get_by_role("link", name="Extra category 11").tap()
            expect(mobile).to_have_url(re.compile(r"[?&]category=extra-category-11(?:&|$)"))
            mobile.locator(".catalog-sort-open").tap()
            sorter = mobile.locator("#catalog-mobile-sort-panel select")
            expect(sorter).to_be_visible()
            assert sorter.evaluate("el => getComputedStyle(el).backgroundImage !== 'none' && el.offsetHeight >= 44")
            sorter.select_option("price_asc")
            mobile.locator("#catalog-mobile-sort-panel button[type=submit]").tap()
            expect(mobile).to_have_url(re.compile(r"[?&]sort=price_asc(?:&|$)"))
            assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            touch.close()
            self.assertFalse(errors, errors)
            browser.close()


if __name__ == "__main__":
    raise SystemExit(bool(DiscoverRunner(debug_mode=True, interactive=False).run_tests(
        ["__main__.CatalogStorefrontAudit.test_storefront"]
    )))
