"""
Inspect tu dong - khong can nhan Enter, tu dong dong browser.
Ghi ket qua ra inspect_result.txt
"""

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

URLS = [
    'https://www.pokemoncenter-online.com/login/',
    'https://www.pokemoncenter-online.com/member/regist/',
    'https://www.pokemoncenter-online.com/regist/',
    'https://www.pokemoncenter-online.com/entry/',
]

OUTPUT_FILE = 'inspect_result.txt'


def inspect_url(page, url):
    lines = []
    try:
        page.goto(url, wait_until='networkidle', timeout=20000)
        lines.append('\n' + '=' * 70)
        lines.append(f'URL:   {page.url}')
        lines.append(f'Title: {page.title()}')
        lines.append('=' * 70)

        lines.append('\n[INPUT FIELDS]')
        for el in page.query_selector_all('input'):
            name        = el.get_attribute('name') or ''
            id_         = el.get_attribute('id') or ''
            type_       = el.get_attribute('type') or 'text'
            placeholder = el.get_attribute('placeholder') or ''
            lines.append(f'  type={type_:<14} name={name:<35} id={id_:<35} placeholder={placeholder}')

        lines.append('\n[SELECT FIELDS]')
        for el in page.query_selector_all('select'):
            name = el.get_attribute('name') or ''
            id_  = el.get_attribute('id') or ''
            lines.append(f'  name={name:<35} id={id_}')

        lines.append('\n[BUTTONS]')
        for el in page.query_selector_all('button, input[type="submit"]'):
            type_ = el.get_attribute('type') or ''
            text  = (el.inner_text() or '').strip().replace('\n', ' ')
            cls   = el.get_attribute('class') or ''
            id_   = el.get_attribute('id') or ''
            lines.append(f'  type={type_:<10} id={id_:<30} text={text[:60]}')

        lines.append('\n[FORMS action]')
        for el in page.query_selector_all('form'):
            action = el.get_attribute('action') or ''
            method = el.get_attribute('method') or ''
            lines.append(f'  action={action}  method={method}')

    except Exception as e:
        lines.append(f'  ERROR: {e}')

    return lines


def main():
    all_lines = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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

        for url in URLS:
            print(f'Inspecting: {url}')
            all_lines += inspect_url(page, url)

        browser.close()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_lines))

    print(f'Done! Written to {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
