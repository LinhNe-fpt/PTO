"""
Inspect form dang ky day du cua Pokemon Center Online.
Ghi ket qua ra inspect_regist_form.txt
"""

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# URL trang dien form dang ky day du (sau khi click link email)
# Thuong co dang: /on/demandware.store/.../Account-StartRegister?...
# Ta se di tu login -> submit email -> xem redirect den dau

TEST_EMAIL = 'test_inspect_only@example.com'
OUTPUT_FILE = 'inspect_regist_form.txt'


def main():
    lines = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        # Buoc 1: Vao trang login
        print('Step 1: Go to login page...')
        page.goto('https://www.pokemoncenter-online.com/login/', wait_until='networkidle')

        # Buoc 2: Dien email vao o dang ky moi
        print('Step 2: Fill email for new registration...')
        page.fill('#login-form-regist-email', TEST_EMAIL)

        # Buoc 3: Click nut "Shin-ki Kaiin Toroku" (Dang ky moi)
        print('Step 3: Click register button...')
        page.click('#form2Button')
        page.wait_for_load_state('networkidle', timeout=15000)

        # Ghi lai URL va form sau khi submit
        lines.append('=' * 70)
        lines.append(f'URL after submit: {page.url}')
        lines.append(f'Title: {page.title()}')
        lines.append('=' * 70)

        lines.append('\n[INPUT FIELDS]')
        for el in page.query_selector_all('input'):
            name        = el.get_attribute('name') or ''
            id_         = el.get_attribute('id') or ''
            type_       = el.get_attribute('type') or 'text'
            placeholder = el.get_attribute('placeholder') or ''
            lines.append(f'  type={type_:<14} name={name:<40} id={id_:<40} placeholder={placeholder}')

        lines.append('\n[SELECT FIELDS]')
        for el in page.query_selector_all('select'):
            name = el.get_attribute('name') or ''
            id_  = el.get_attribute('id') or ''
            options = [o.get_attribute('value') or '' for o in el.query_selector_all('option')]
            lines.append(f'  name={name:<40} id={id_}')
            lines.append(f'    options: {options[:10]}')

        lines.append('\n[BUTTONS]')
        for el in page.query_selector_all('button, input[type="submit"]'):
            type_ = el.get_attribute('type') or ''
            text  = (el.inner_text() or '').strip().replace('\n', ' ')
            id_   = el.get_attribute('id') or ''
            lines.append(f'  type={type_:<10} id={id_:<30} text={text[:60]}')

        lines.append('\n[FORMS]')
        for el in page.query_selector_all('form'):
            action = el.get_attribute('action') or ''
            method = el.get_attribute('method') or ''
            lines.append(f'  action={action}  method={method}')

        browser.close()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'Done! Written to {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
