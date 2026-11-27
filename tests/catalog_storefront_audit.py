"""Run with python tests/catalog_storefront_audit.py and Playwright Chromium."""
import re
from io import BytesIO

from responsive_routes import ResponsiveAudit, DiscoverRunner, expect, reverse, sync_playwright
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from store.models import AttributeDefinition, Category, CustomerPrice, PageContent, Product, VariantGroup
from store.test_media_uploads import image_file


class CatalogStorefrontAudit(ResponsiveAudit):
    def test_public_detail_footer_and_favorites(self):
        child = Category.objects.create(name="Вложенная упаковка", parent=self.category)
        related = [
            Product.objects.create(category=child, name=name, status=Product.STATUS_PUBLISHED, price=41)
            for name in ("Рекомендуемый короб", "Сопутствующий короб")
        ]
        self.product.recommended_products.set(related[:1])
        self.product.accessory_products.set(related[1:])
        self.product.description = "Описание для проверки."
        self.product.save(update_fields=["description"])
        self.client.force_login(self.customer)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
            context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": self.live_server_url}])
            page = context.new_page()
            detail = reverse("product_detail", args=[self.product.slug])
            for path in ("/", reverse("catalog"), reverse("catalog") + f"?category={child.slug}", detail):
                page.goto(self.live_server_url + path)
                expect(page.locator(".catalog-breadcrumbs")).to_have_count(0)
            description = page.locator("#detail-quantity-rules + .product-detail-description")
            expect(description.get_by_role("heading", name="Описание товара")).to_be_visible()
            expect(page.locator("[data-detail-description]")).to_have_count(1)
            assert description.bounding_box()["x"] > page.locator("[data-detail-gallery]").bounding_box()["x"]

            main = page.locator(".product-detail-gallery-stage .image-favorite")
            buttons = [page.locator(f'.product-detail-recommendation[data-product-id="{item.pk}"] .image-favorite') for item in related]
            for button in [main, *buttons]:
                expect(button).to_have_css("background-color", "rgba(0, 0, 0, 0)")
                expect(button).to_have_css("border-top-width", "0px")
                expect(button).to_have_css("box-shadow", "none")
                expect(button).to_have_css("width", "44px")
                expect(button.locator("svg")).to_have_css("fill", "none")
            for button in (main, buttons[0], buttons[1], buttons[0]):
                with page.expect_response(lambda response: response.url.endswith("/favorites/toggle/")) as response:
                    button.click()
                assert response.value.ok
            expect(main).to_have_attribute("aria-pressed", "true")
            expect(buttons[0]).to_have_attribute("aria-pressed", "false")
            expect(buttons[1]).to_have_attribute("aria-pressed", "true")
            assert buttons[1].locator("svg").evaluate("(svg) => getComputedStyle(svg).fill !== 'none'")
            quick_data = page.request.get(self.live_server_url + reverse("api_product_detail", args=[self.product.pk])).json()
            page.evaluate("(product) => window.openProductDetails(product)", quick_data["product"])
            quick_favorite = page.locator(".modal-image-frame .modal-favorite")
            expect(quick_favorite).to_be_visible()
            expect(quick_favorite).to_have_attribute("aria-pressed", "true")
            expect(quick_favorite).to_have_css("background-color", "rgba(0, 0, 0, 0)")
            page.locator(".modal-close").click()

            footer = page.locator(".footer-categories")
            expect(footer.locator("[data-footer-categories]")).to_be_hidden()
            footer.locator("summary").click()
            expect(footer.get_by_role("link", name=self.category.name)).to_be_visible()
            footer.get_by_role("button", name=f"Подкатегории: {self.category.name}").click()
            expect(footer.get_by_role("link", name=child.name)).to_be_visible()
            expect(footer.locator("[data-footer-categories]")).to_have_css("overflow-y", "visible")
            tops = page.locator(".footer-main > *").evaluate_all("(cols) => cols.map(col => col.getBoundingClientRect().top)")
            assert max(tops) - min(tops) <= 1
            footer.locator("summary").press("Escape")
            expect(footer.locator("[data-footer-categories]")).to_be_hidden()
            expect(footer.locator("summary")).to_be_focused()

            page.set_viewport_size({"width": 320, "height": 844})
            page.emulate_media(color_scheme="dark")
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            expect(description).to_be_visible()
            expect(main).to_have_css("background-color", "rgba(0, 0, 0, 0)")
            footer.locator("summary").click()
            branch = footer.get_by_role("button", name=f"Подкатегории: {self.category.name}")
            expect(branch).to_have_attribute("aria-expanded", "false")
            branch.click()
            expect(footer.get_by_role("link", name=child.name)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
            footer.get_by_role("link", name=child.name).click()
            expect(page).to_have_url(re.compile(r"[?&]category="))
            expect(page.locator(".catalog-breadcrumbs")).to_have_count(0)
            browser.close()

    def test_category_tree_and_product_membership(self):
        middle = Category.objects.create(name="Вложенная категория", parent=self.category)
        leaf = Category.objects.create(name="Категория третьего уровня", parent=middle)
        destination = Category.objects.create(name="Другая основная категория")
        self.product.category = leaf
        self.product.save(update_fields=["category"])
        self.client.force_login(self.staff)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme="dark")
            context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": self.live_server_url}])
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + reverse("management_categories"))
            root_row, middle_row, leaf_row = (
                page.locator(f'[data-category-id="{item.pk}"]') for item in (self.category, middle, leaf)
            )
            expect(middle_row).to_be_hidden()
            root_row.locator("[data-category-branch]").click()
            expect(middle_row).to_be_visible()
            middle_row.locator("[data-category-branch]").click()
            expect(leaf_row).to_be_visible()
            page.reload()
            expect(leaf_row).to_be_visible()
            root_row.locator("[data-category-branch]").click()
            expect(leaf_row).to_be_hidden()
            page.locator("[data-category-search]").fill(leaf.name)
            expect(leaf_row).to_be_visible()
            expect(root_row).to_be_visible()
            page.get_by_role("button", name="Развернуть всё").click()
            leaf_row.locator("[data-category-products]").click()
            panel = page.locator(f"#category-products-{leaf.pk}")
            with page.expect_response(lambda response: f"mode=linked&q={self.product.sku}" in response.url):
                panel.locator("[data-member-search]").fill(self.product.sku)
            expect(panel.locator("[data-member-status]")).to_contain_text("Найдено:")
            checkbox = panel.locator("input[type=checkbox]")
            expect(checkbox).to_be_checked()
            checkbox.uncheck()
            panel.locator("[data-member-save]").click()
            expect(panel.locator("[data-member-status]")).to_contain_text("Выберите категорию")
            panel.locator("[data-member-destination]").select_option(str(destination.pk))
            panel.locator("[data-member-save]").click()
            expect(panel.locator("[data-member-status]")).to_contain_text("Привязки сохранены")
            expect(panel.locator("[data-member-search]")).to_have_value(self.product.sku)
            expect(leaf_row.locator("[data-category-products]")).to_have_text("0")
            expect(checkbox).to_have_count(0)
            panel.locator("[data-member-add]").click()
            panel.locator("[data-member-search]").fill(self.product.sku)
            expect(checkbox).to_be_visible()
            checkbox.check()
            panel.locator("[data-member-save]").click()
            expect(panel.locator("[data-member-status]")).to_contain_text("Привязки сохранены")
            expect(leaf_row.locator("[data-category-products]")).to_have_text("1")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
            page.get_by_role("button", name="Свернуть всё").click()
            expect(leaf_row).to_be_hidden()
            page.get_by_role("button", name="Развернуть всё").click()
            leaf_row.locator(".status-select").select_option("hidden")
            page.get_by_role("button", name="Сохранить статусы").click()
            expect(leaf_row).to_be_visible()
            expect(leaf_row.locator(".status-select")).to_have_value("hidden")
            leaf_row.locator(".status-select").select_option("published")
            page.get_by_role("button", name="Сохранить статусы").click()
            page.goto(self.live_server_url + reverse("catalog") + f"?category={leaf.slug}")
            expect(page.locator(f'.catalog-card[data-product-id="{self.product.pk}"]')).to_be_visible()
            self.assertFalse(errors, errors)
            browser.close()

    def test_sparse_variant_dropdown_and_customer_cart(self):
        color = AttributeDefinition.objects.create(name="Цвет", value_type="text", sort_order=0)
        size = AttributeDefinition.objects.create(name="Размер", value_type="text", sort_order=1)
        group = VariantGroup.objects.create(name="Варианты коробки")
        group.attributes.set([color, size])
        items = []
        for idx, (shade, measure, availability) in enumerate((
            ("Крафт", "330 мм", Product.AVAILABILITY_IN_STOCK),
            ("Белая", "330 мм", Product.AVAILABILITY_IN_STOCK),
            ("Белая", "500 мм", Product.AVAILABILITY_PREORDER),
            ("Белая", "700 мм", Product.AVAILABILITY_OUT_OF_STOCK),
        )):
            product = Product.objects.create(
                category=self.category, variant_group=group, variant_sort_order=idx,
                name=f"Коробка {shade} {measure}", sku=f"VARIANT-{idx}",
                price=120 + idx, status=Product.STATUS_PUBLISHED, availability=availability,
                description=f"Описание {shade} {measure}", min_quantity=3, quantity_step=2,
            )
            product.attributes.create(attribute=color, value_text=shade)
            product.attributes.create(attribute=size, value_text=measure)
            items.append(product)
        kraft, white, preorder, _ = items
        CustomerPrice.objects.create(user=self.customer, product=preorder, price=83.25)
        self.client.force_login(self.customer)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 320, "height": 844}, has_touch=True, is_mobile=True)
            context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": self.live_server_url}])
            page = context.new_page()
            page.goto(self.live_server_url + reverse("product_detail", args=[kraft.slug]))
            color_menu = page.locator("[data-variant-dropdown]").filter(has=page.locator('summary[aria-label^="Цвет:"]'))
            expect(page.locator('summary[aria-label^="Размер:"]')).to_have_count(0)
            color_menu.locator("summary").tap()
            page.locator("h1").tap()
            expect(color_menu).not_to_have_attribute("open", "")
            color_menu.locator("summary").tap()
            color_menu.get_by_role("link", name="Белая").tap()
            expect(page.locator("h1")).to_have_text(white.h1)
            size_menu = page.locator("[data-variant-dropdown]").filter(has=page.locator('summary[aria-label^="Размер:"]'))
            size_menu.locator("summary").tap()
            expect(size_menu.get_by_role("link", name=re.compile("700 мм"))).to_contain_text("Нет в наличии")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
            size_menu.get_by_role("link", name=re.compile("500 мм")).tap()
            expect(page.locator("h1")).to_have_text(preorder.h1)
            expect(page).to_have_title(preorder.seo_title)
            expect(page.locator("[data-detail-availability]")).to_have_text("Под заказ")
            expect(page.locator("[data-detail-price]")).to_contain_text("83.25")
            expect(page.locator("[data-detail-sku]")).to_contain_text(preorder.sku)
            expect(page.locator("[data-detail-description]")).to_have_text(preorder.description)
            page.locator(".product-detail-add").tap()
            expect(page.locator(".product-detail-add")).to_have_text("В корзине")
            expect(page.locator(".cart-drawer")).to_be_hidden()
            page.locator(".mobile-actions .js-cart-open").tap()
            expect(page.locator(f'.cart-item[data-product-id="{preorder.pk}"] .cart-quantity')).to_contain_text("3")
            browser.close()

    def test_product_fields_and_media_batch(self):
        self.client.force_login(self.staff)
        cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.on("dialog", lambda dialog: dialog.accept())
            page.context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": self.live_server_url}])
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            library = reverse("management_media")
            page.goto(self.live_server_url + library)
            uploads = page.locator("[data-library-upload]")
            files = uploads.locator("input[type=file]")
            files.set_input_files([
                {"name": name, "mimeType": "image/png", "buffer": image_file(name).read()}
                for name in ("first-test.png", "second-test.png")
            ])
            expect(uploads.get_by_role("button", name="Загрузить")).to_be_enabled()
            uploads.get_by_role("button", name="Загрузить").click()
            expect(page.locator("[data-library-status]")).to_contain_text("2 из 2")
            page.locator("[data-library-search]").fill("second-test.png")
            media_row = page.locator('[data-file-name="second-test.png"]')
            expect(media_row).to_be_visible()
            expect(media_row.locator("img").first).to_be_visible()
            assert media_row.locator("img").first.evaluate("img => img.naturalWidth") > 0
            expect(page.locator('[data-file-name="first-test.png"]')).to_be_hidden()
            items = page.request.get(self.live_server_url + reverse("management_media_api")).json()["items"]
            media = next(item for item in items if item["filename"] == "second-test.png")
            media_id, media_url = media["id"], media["url"]
            self.assertEqual(page.request.get(self.live_server_url + media_url).status, 200)

            upload_endpoint = "**" + reverse("management_media_upload_api")
            def fail_one_upload(route):
                if b'filename="retry-test.png"' in (route.request.post_data_buffer or b""):
                    route.fulfill(status=503, json={"error": "Временная ошибка хранилища"})
                else:
                    route.continue_()

            page.route(upload_endpoint, fail_one_upload)
            files.set_input_files([
                {"name": name, "mimeType": "image/png", "buffer": image_file(name).read()}
                for name in ("kept-test.png", "retry-test.png")
            ])
            uploads.get_by_role("button", name="Загрузить").click()
            expect(page.locator("[data-library-status]")).to_contain_text("retry-test.png — Временная ошибка хранилища")
            assert files.evaluate("input => Array.from(input.files, file => file.name)") == ["retry-test.png"]
            page.unroute(upload_endpoint)
            uploads.get_by_role("button", name="Загрузить").click()
            expect(page.locator("[data-library-status]")).to_contain_text("1 из 1")
            expect(page.locator('[data-file-name="kept-test.png"]')).to_have_count(1)
            expect(page.locator('[data-file-name="retry-test.png"]')).to_have_count(1)

            for path in (reverse("management_product_new"), reverse("management_product_edit", args=[self.product.pk])):
                page.goto(self.live_server_url + path)
                product = page.locator("[data-product-editor]")
                product.locator('[name="name"]').fill("Коробка с черновиком")
                product.locator('[name="sku"]').fill("CHECK-SKU")
                product.locator('[name="description"]').fill("Описание в черновике")
                product.locator('[name="price"]').fill("150")
                product.locator('[name="category"]').select_option(str(self.category.pk))
                product.locator("[data-open-variant]").click()
                variant_dialog = page.locator("[data-variant-dialog]")
                expect(variant_dialog).to_be_visible()
                variant_dialog.locator("[data-dialog-group]").select_option(str(self.group.pk))
                variant_dialog.locator("[data-use-variant]").click()
                expect(variant_dialog).to_be_hidden()
                product.locator("[data-gallery-pick]").click()
                page.locator("[data-media-picker-search]").fill("second-test.png")
                page.locator(".media-picker-item").filter(has_text="second-test.png").click()
                page.locator("[data-media-picker-apply]").click()
                tile = product.locator(f'[data-key="media:{media_id}"]')
                primary = tile.locator("[data-gallery-primary]")
                if primary.is_visible():
                    primary.click()
                gallery = product.locator("[data-gallery-manifest]").input_value()
                self.assertIn(f"media:{media_id}", gallery)

                dialog = page.locator("[data-attribute-dialog]")
                product.locator("[data-attribute-picker]").click()
                product.locator("[data-attribute-new]").click()
                label = "Проверка " + ("нового" if path.endswith("/new/") else "редактируемого")
                dialog.locator('[name="definition-name"]').fill(label)
                dialog.get_by_role("button", name="Создать и добавить").click()
                row = product.locator("[data-product-attribute]").filter(has_text=label)
                value = row.locator("textarea")
                value.fill("Сохранить в черновике")
                row.locator("[data-attribute-edit]").click()
                expect(dialog).to_contain_text("для всех товаров")
                dialog.locator('[name="definition-unit"]').fill("мм")
                dialog.locator('[name="confirm_global"]').check()
                dialog.get_by_role("button", name="Сохранить изменения").click()
                expect(row).to_contain_text("мм")
                expect(value).to_have_value("Сохранить в черновике")
                value.fill("")
                row.locator("[data-attribute-remove]").click()
                expect(row).to_have_count(0)
                expect(product.locator('[name="name"]')).to_have_value("Коробка с черновиком")
                expect(product.locator('[name="sku"]')).to_have_value("CHECK-SKU")
                expect(product.locator('[name="description"]')).to_have_value("Описание в черновике")
                expect(product.locator('[name="price"]')).to_have_value("150")
                expect(product.locator('[name="variant_group"]')).to_have_value(str(self.group.pk))
                expect(product.locator("[data-gallery-manifest]")).to_have_value(gallery)

            product.get_by_role("button", name="Сохранить", exact=True).click()
            expect(page.get_by_text("Товар сохранён.")).to_be_visible()
            page.goto(self.live_server_url + reverse("product_detail", args=[self.product.slug]))
            expect(page.locator(f'[data-detail-gallery] img[src="{media_url}"]').first).to_be_visible()
            fallback = browser.new_page(viewport={"width": 390, "height": 844})
            fallback.context.add_cookies([{"name": cookie.key, "value": cookie.value, "url": self.live_server_url}])
            fallback.on("pageerror", lambda error: errors.append(str(error)))
            fallback.add_init_script("""const supports = CSS.supports.bind(CSS);
                CSS.supports = (...args) => args[0] === "selector(::picker(select))" ? false : supports(...args);""")
            fallback.goto(self.live_server_url + reverse("management_product_new"))
            selector = fallback.locator('[name="category"] + details')
            summary = selector.locator("summary")
            summary.press("End")
            expect(selector.get_by_role("button", name=self.subcategory.name)).to_be_focused()
            fallback.keyboard.press("Enter")
            expect(fallback.locator('[name="category"]')).to_have_value(str(self.subcategory.pk))
            summary.click()
            fallback.locator("h1").click()
            expect(selector).not_to_have_attribute("open", "")
            self.assertFalse(errors, errors)
            browser.close()
        self.assertTrue(self.product.images.filter(media_id=media_id).exists())

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
            selector = page.locator("[data-variant-dropdown] summary").first
            expect(selector).to_be_visible()
            selector.press("Enter")
            option = page.locator(f'[data-variant-dropdown][open] a[href="{reverse("product_detail", args=[selected.slug])}"]')
            expect(option).to_be_visible()
            option.press("Escape")
            expect(selector).to_be_focused()
            selector.click()
            option.click()
            expect(page.locator("h1")).to_have_text(selected.name)
            expect(page.locator("[data-detail-sku]")).to_contain_text(selected.sku)
            expect(page.locator("[data-detail-price]")).to_contain_text(str(selected.price))
            expect(page.locator("[data-detail-availability]")).to_have_text(selected.get_availability_display())
            expect(page.locator("[data-detail-main-image]")).to_have_attribute("src", selected.image.url)
            expect(page.locator(".product-detail-purchase .quantity-input")).to_have_attribute("min", "3")
            expect(page.locator(".product-detail-purchase .quantity-input")).to_have_attribute("step", "2")
            page.wait_for_function("typeof window.setProductCartQuantity === 'function'")
            page.locator(".product-detail-purchase .quantity-plus").click()
            expect(page.locator(".product-detail-purchase .quantity-input")).to_have_value("5")
            page.locator(".product-detail-add").click()
            expect(page.locator(".product-detail-add")).to_have_text("В корзине")
            expect(page.locator(".cart-drawer")).to_be_hidden()
            page.locator(".mobile-actions .js-cart-open").click()
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
        ["__main__.CatalogStorefrontAudit.test_storefront",
         "__main__.CatalogStorefrontAudit.test_category_tree_and_product_membership",
         "__main__.CatalogStorefrontAudit.test_sparse_variant_dropdown_and_customer_cart",
         "__main__.CatalogStorefrontAudit.test_public_detail_footer_and_favorites",
         "__main__.CatalogStorefrontAudit.test_product_fields_and_media_batch"]
    )))
