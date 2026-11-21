"""Run with python tests/catalog_storefront_audit.py and Playwright Chromium."""
from io import BytesIO

from responsive_routes import ResponsiveAudit, DiscoverRunner, expect, reverse, sync_playwright
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from store.models import Category, Product


class CatalogStorefrontAudit(ResponsiveAudit):
    def test_storefront(self):
        parent = Category.objects.create(name="Boxes " + "W" * 45)
        self.category.parent = parent
        self.category.save(update_fields=["parent"])
        for category, size in ((parent, (80, 300)), (self.category, (300, 80))):
            image = BytesIO()
            Image.new("RGB", size, "navy").save(image, format="PNG")
            category.image.save("category.png", ContentFile(image.getvalue()))
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
            context = browser.new_context()
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

            page.goto(self.live_server_url + reverse("product_detail", args=[self.product.slug]))
            for width in (1440, 768, 320, 390):
                page.set_viewport_size({"width": width, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), width
                if width > 620:
                    expect(page.locator(".product-breadcrumb-root")).to_be_visible()
            expect(page.locator(".product-breadcrumb-parent")).to_be_visible()
            expect(page.locator(".product-breadcrumb-root")).to_be_hidden()
            expect(page.locator(".product-breadcrumb-current")).to_have_attribute("aria-current", "page")
            expect(page.locator(".detail-variant-more")).not_to_have_attribute("open", "")
            page.locator(".detail-variant-more summary").press("Enter")
            page.locator(f'.detail-variant-more a[data-product-id="{selected.pk}"]').click()
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
            expect(page.locator(".detail-favorite")).to_have_attribute("aria-pressed", "true")
            page.locator(".mobile-actions .js-favorites-open").click()
            expect(page.locator(f'.favorite-item[data-product-id="{selected.pk}"]')).to_be_visible()
            page.keyboard.press("Escape")
            page.locator(".detail-favorite").click()
            expect(page.locator(".detail-favorite")).to_have_attribute("aria-pressed", "false")
            page.goto(self.live_server_url + f"/catalog/?category={self.category.slug}")
            catalog_favorite = page.locator(f'.catalog-card[data-product-id="{selected.pk}"] .favorite-button')
            catalog_favorite.click()
            expect(catalog_favorite).to_have_class("favorite-button is-active")
            expect(page.locator(".mobile-actions .favorite-count")).to_have_text("1")
            expect(page.locator(".mobile-actions [data-cart-count]")).to_have_text("0")
            self.assertFalse(errors, errors)
            browser.close()


if __name__ == "__main__":
    raise SystemExit(bool(DiscoverRunner(debug_mode=True, interactive=False).run_tests(
        ["__main__.CatalogStorefrontAudit.test_storefront"]
    )))
