"""Run against a seeded LOCAL server; never point mutation checks at production.
PAKLINE_AUDIT_URL=http://127.0.0.1:8765 python tests/responsive_audit.py
Optional PAKLINE_AUDIT_SESSION contains a staff session from the isolated database.
Requires Playwright with chromium and webkit installed.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get('PAKLINE_AUDIT_URL', 'http://127.0.0.1:8765')
OUT = Path(os.environ.get('PAKLINE_AUDIT_OUTPUT', '/tmp/pakline-audit-results'))
OUT.mkdir(parents=True, exist_ok=True)
WIDTHS = [320, 360, 375, 390, 393, 414, 430, 440, 540, 620, 720, 721, 768, 820, 900, 920, 921, 1024, 1100, 1180, 1280, 1440]
PUBLIC = ['/', '/catalog/', '/team/', '/contacts/', '/documents/privacy/', '/documents/offer/']
ADMIN = ['/management/', '/management/products/', '/management/products/new/', '/management/products/1/edit/', '/management/categories/', '/management/categories/new/', '/management/employees/', '/management/employees/new/', '/management/fields/', '/management/fields/new/', '/management/orders/', '/management/requests/', '/management/settings/', '/management/pages/', '/management/pages/new/']
results, failures, errors = [], [], []

def check_layout(page, label):
    overflow = page.evaluate('''() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
      offenders: [...document.querySelectorAll('body *')].filter(e => {
        const r=e.getBoundingClientRect(); const s=getComputedStyle(e);
        return r.width && (r.right>innerWidth+1 || r.left < -1) && s.position !== 'absolute' && !e.closest('.table-wrap');
      }).slice(0,8).map(e => e.tagName+'.'+e.className)})''')
    if overflow['scroll'] > overflow['width'] + 1: failures.append({'label': label, **overflow})
    results.append(label)

with sync_playwright() as p:
    for name in os.environ.get('PAKLINE_AUDIT_ENGINES', 'chromium,webkit').split(','):
        browser = getattr(p, name).launch()
        context = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        for path in PUBLIC + ['/management/login/']:
            response = page.goto(BASE+path, wait_until='domcontentloaded')
            assert response.status == 200, (path, response.status)
            for width in WIDTHS:
                page.set_viewport_size({'width':width,'height':844})
                check_layout(page, f'{name} {path} {width}')
            page.set_viewport_size({'width':390,'height':844})
            page.screenshot(path=str(OUT/f'{name}-{path.strip("/").replace("/","-") or "home"}.png'), full_page=True)
        page.goto(BASE+'/catalog/', wait_until='domcontentloaded')
        select = page.locator('.catalog-topline select')
        select.select_option(label='Сначала дешевле')
        prices = page.locator('.catalog-card').evaluate_all("cards => cards.map(c => Number(JSON.parse(c.dataset.product).price.replace(/\\s/g, '').replace(',', '.')))")
        assert prices == sorted(prices), prices
        select.select_option(label='По умолчанию')
        page.locator('.catalog-card .add-to-cart').first.click()
        page.wait_for_function("document.querySelector('.mobile-actions [data-cart-count]').textContent !== '0'")
        page.locator('.mobile-menu-toggle').click()
        assert page.locator('.main-nav').is_visible()
        page.locator('.mobile-menu-toggle').click()
        assert not page.locator('.main-nav').is_visible()
        page.locator('.open-product').first.click()
        assert page.locator('.product-modal').get_attribute('aria-hidden') == 'false'
        assert page.locator('.modal-controls input').get_attribute('min') == '10'
        assert not page.locator('.mobile-actions').is_visible()
        for width,height in [(320,568),(390,844),(430,932),(844,390)]:
            page.set_viewport_size({'width':width,'height':height})
            check_layout(page, f'{name} product-modal {width}x{height}')
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(OUT/f'{name}-product-modal.png'))
        page.keyboard.press('Escape')
        page.locator('.mobile-actions .js-cart-open').click()
        assert page.locator('.cart-drawer').get_attribute('aria-hidden') == 'false'
        check_layout(page, f'{name} cart')
        page.locator('.cart-checkout').click()
        page.wait_for_timeout(100)
        check_layout(page, f'{name} checkout-or-login')
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.locator('.js-cookie-settings').click()
        assert page.locator('.cookie-modal').get_attribute('aria-hidden') == 'false'
        assert not page.locator('.mobile-actions').is_visible()
        check_layout(page, f'{name} cookies')
        page.keyboard.press('Escape')
        page.locator('.js-account-open').click()
        check_layout(page, f'{name} account')
        page.keyboard.press('Escape')
        page.locator('.js-favorites-open').click()
        check_layout(page, f'{name} favorites')
        page.keyboard.press('Escape')
        # Continuous-width sweep catches failures between named devices.
        for width in range(320,1441,13):
            page.set_viewport_size({'width':width,'height':844})
            check_layout(page, f'{name} sweep {width}')
        session = os.environ.get('PAKLINE_AUDIT_SESSION')
        if session:
            context.add_cookies([{'name':'sessionid','value':session,'url':BASE}])
            for path in ADMIN:
                response=page.goto(BASE+path,wait_until='domcontentloaded')
                assert response.status == 200, (path,response.status)
                for width in [320,390,430,720,768,900,1024,1440]:
                    page.set_viewport_size({'width':width,'height':844})
                    check_layout(page, f'{name} {path} {width}')
                if path in ['/management/products/','/management/settings/']:
                    page.set_viewport_size({'width':390,'height':844})
                    page.screenshot(path=str(OUT/f'{name}-{path.strip("/").replace("/","-")}.png'), full_page=True)
        (OUT/f'{name}-results.json').write_text(json.dumps({'checks':len(results),'failures':failures,'js_errors':errors},ensure_ascii=False,indent=2))
        browser.close()
(OUT/'results.json').write_text(json.dumps({'checks':len(results),'failures':failures,'js_errors':errors},ensure_ascii=False,indent=2))
print(json.dumps({'checks':len(results),'failures':failures,'js_errors':errors},ensure_ascii=False,indent=2))
assert not failures and not errors
