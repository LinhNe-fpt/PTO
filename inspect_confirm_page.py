import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

EMAIL = 'linh2005nov@gmail.com'

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            locale='ja-JP', timezone_id='Asia/Tokyo',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        # Buoc 1: Submit email
        print('Going to login page...')
        page.goto('https://www.pokemoncenter-online.com/login/', wait_until='networkidle')
        page.fill('#login-form-regist-email', EMAIL)
        page.click('#form2Button')
        page.wait_for_url('**/temporary-customer-confirm/**', timeout=15000)

        print(f'Current URL: {page.url}')
        print(f'Title: {page.title()}')
        print()

        # Dump toan bo trang
        lines = []
        lines.append(f'URL: {page.url}')
        lines.append(f'Title: {page.title()}')

        lines.append('\n[INPUT FIELDS]')
        for el in page.query_selector_all('input'):
            t = el.get_attribute('type') or 'text'
            n = el.get_attribute('name') or ''
            i = el.get_attribute('id') or ''
            v = el.get_attribute('value') or ''
            lines.append(f'  type={t:<12} name={n:<35} id={i:<35} value={v[:40]}')

        lines.append('\n[BUTTONS]')
        for el in page.query_selector_all('button, input[type="submit"], a[href]'):
            tag  = el.evaluate('el => el.tagName')
            text = (el.inner_text() or '').strip().replace('\n', ' ')
            id_  = el.get_attribute('id') or ''
            cls  = el.get_attribute('class') or ''
            href = el.get_attribute('href') or ''
            lines.append(f'  tag={tag:<8} id={id_:<25} text={text[:50]} href={href[:60]}')

        lines.append('\n[FORMS]')
        for el in page.query_selector_all('form'):
            action = el.get_attribute('action') or ''
            method = el.get_attribute('method') or ''
            lines.append(f'  action={action}  method={method}')

        # Luu screenshot
        page.screenshot(path='confirm_page.png', full_page=True)
        print('Screenshot: confirm_page.png')

        with open('confirm_page_dump.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print('Dump: confirm_page_dump.txt')

        browser.close()

if __name__ == '__main__':
    main()
