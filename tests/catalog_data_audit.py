"""Run only on a seeded LOCAL server (see tests/responsive_audit.py).
Requires PAKLINE_AUDIT_SESSION for a staff user with a price override.
"""
import os
from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('PAKLINE_AUDIT_URL', 'http://127.0.0.1:8765')
SESSION = os.environ['PAKLINE_AUDIT_SESSION']
with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    categories = context.request.get(BASE + '/api/categories/').json()['categories']
    root = next(category for category in categories if category['parent_id'] is None)
    page.goto(BASE + '/catalog/', wait_until='domcontentloaded')
    page.locator('.catalog-sidebar a').filter(has_text=root['name']).first.click()
    page.wait_for_function("!document.querySelector('.catalog-grid').classList.contains('is-loading')")
    assert page.locator('.catalog-card').count()
    card = page.locator('.catalog-card').first
    public_product = card.evaluate('el => JSON.parse(el.dataset.product)')
    assert 'cost_price' not in public_product
    card.locator('.catalog-card-info').click()
    expect(page.locator('.modal-specs')).to_contain_text('НДС')
    expect(page.locator('.modal-specs')).to_contain_text('Объём, м³')
    expect(page.locator('.modal-badge')).to_contain_text('СПЕЦПРЕДЛОЖЕНИЕ')
    page.keyboard.press('Escape')
    context.add_cookies([{'name': 'sessionid', 'value': SESSION, 'url': BASE}])
    page.reload(wait_until='domcontentloaded')
    card = page.locator('.catalog-card').first
    private_product = card.evaluate('el => JSON.parse(el.dataset.product)')
    assert private_product['price'] != public_product['price'], 'Seed an individual price for the first product'
    card.locator('.add-to-cart').click()
    expect(page.locator('.cart-drawer')).to_have_attribute('aria-hidden', 'false')
    cart = context.request.get(BASE + '/api/cart/').json()
    assert cart['items'][0]['price'] == private_product['price']
    page.goto(BASE + f'/management/products/{private_product["id"]}/edit/', wait_until='domcontentloaded')
    for name in ['cost_price', 'vat_rate', 'length_mm', 'width_mm', 'height_mm', 'weight_kg', 'is_new', 'is_special', 'media']:
        expect(page.locator(f'[name="{name}"]')).to_be_visible()
    expect(page.locator('[name="volume_m3"]')).to_be_disabled()
    assert page.locator('[name="prices-0-price"]').count()
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.goto(BASE + '/management/categories/new/', wait_until='domcontentloaded')
    expect(page.locator('[name="parent"]')).to_be_visible()
    assert not errors, errors
    browser.close()
print('Nested catalog, private prices, cart, tax/dimensions and CMS: OK')
