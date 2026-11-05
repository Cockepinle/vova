"""Browser regression checks against a LOCAL seeded server.
Requires a published hit with multiple distinct photos, and a single-photo product.
PAKLINE_AUDIT_URL=http://127.0.0.1:8765 python tests/theme_gallery_audit.py
"""
import os
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('PAKLINE_AUDIT_URL', 'http://127.0.0.1:8765')
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE + '/catalog/', wait_until='domcontentloaded')
    assert page.locator('html').get_attribute('data-theme') == 'dark'
    page.locator('.theme-toggle').click()
    assert page.locator('html').get_attribute('data-theme') == 'light'
    page.reload(wait_until='domcontentloaded')
    assert page.locator('html').get_attribute('data-theme') == 'light'
    page.emulate_media(color_scheme='dark')
    assert page.locator('html').get_attribute('data-theme') == 'light'
    for theme in ['light', 'dark']:
        if page.locator('html').get_attribute('data-theme') != theme:
            page.locator('.theme-toggle').click()
        for path in ['/', '/catalog/', '/team/', '/contacts/', '/documents/privacy/', '/management/login/']:
            page.goto(BASE + path, wait_until='domcontentloaded')
            assert page.locator('html').get_attribute('data-theme') == theme
            for width in [320, 390, 720, 768, 1024, 1440]:
                page.set_viewport_size({'width': width, 'height': 900})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (theme, path, width)
            if path not in ['/', '/catalog/']:
                continue
            card = page.locator('[data-product]').filter(has=page.locator('.gallery-next')).first
            assert card.count(), 'Seed a multi-photo published hit product'
            track = card.locator('.product-gallery-track')
            photo_count = track.locator('img').count()
            def at_photo(number):
                expect(card.locator('.gallery-counter')).to_have_text(f'{number} / {photo_count}')
                page.wait_for_function('(args) => Math.abs(args.el.scrollLeft - (args.number - 1) * args.el.clientWidth) < 2', arg={'el': track.element_handle(), 'number': number})
            height = card.bounding_box()['height']
            card.locator('.gallery-next').click()
            at_photo(2)
            assert card.bounding_box()['height'] == height
            assert page.locator('.product-modal').get_attribute('aria-hidden') == 'true'
            card.locator('.gallery-previous').focus()
            page.keyboard.press('Enter')
            at_photo(1)
            # Real desktop mouse wheel scrolls photos, not the page.
            track.scroll_into_view_if_needed()
            box = track.bounding_box()
            page.mouse.move(box['x'] + box['width'] * .5, box['y'] + box['height'] * .5)
            scroll_y = page.evaluate('scrollY')
            page.mouse.wheel(0, 120)
            at_photo(2)
            assert page.evaluate('scrollY') == scroll_y
            page.wait_for_timeout(460)
            page.mouse.wheel(0, -120)
            at_photo(1)
            # Native horizontal scrolling updates the indicator and dots.
            track.evaluate('el => el.scrollTo({left: el.clientWidth, behavior: "instant"})')
            at_photo(2)
            expect(card.locator('.gallery-dot').nth(1)).to_have_attribute('aria-current', 'true')
            card.locator('.gallery-dot').first.click()
            at_photo(1)
            # Mouse dragging changes photos without opening product details.
            box = track.bounding_box()
            page.mouse.move(box['x'] + box['width'] * .75, box['y'] + box['height'] * .5)
            page.mouse.down()
            page.mouse.move(box['x'] + box['width'] * .25, box['y'] + box['height'] * .5, steps=12)
            page.mouse.up()
            at_photo(2)
            assert card.locator('.favorite-button').evaluate('el => getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
            assert page.locator('.product-modal').get_attribute('aria-hidden') == 'true'
            # Each card owns its counter and only multi-photo cards have controls.
            for item in page.locator('[data-product]').all():
                count = item.evaluate('el => { const p = JSON.parse(el.dataset.product); return p.thumbs.length + (p.image && p.thumbs[0] !== p.image ? 1 : 0); }')
                assert item.locator('.product-gallery-controls').count() == int(count > 1)
            if path == '/catalog/':
                page.locator('.catalog-topline select').select_option(label='Сначала дешевле')
                page.locator('.catalog-sidebar a').first.click()
                page.wait_for_function("!document.querySelector('.catalog-grid').classList.contains('is-loading')")
                assert page.locator('.gallery-next').count()
                page.locator('.gallery-next').first.click()
                expect(page.locator('.gallery-counter').first).to_have_text(f'2 / {photo_count}')
    # Storage failures must not prevent toggling.
    blocked = browser.new_context()
    blocked.add_init_script("Object.defineProperty(window, 'localStorage', {get() {throw new Error('Blocked');}})")
    blocked_page = blocked.new_page()
    blocked_page.goto(BASE, wait_until='domcontentloaded')
    old = blocked_page.locator('html').get_attribute('data-theme')
    blocked_page.locator('.theme-toggle').click()
    assert blocked_page.locator('html').get_attribute('data-theme') != old
    assert not errors, errors
    browser.close()
print('Theme persistence, layouts, gallery controls and dynamic catalog: OK')
