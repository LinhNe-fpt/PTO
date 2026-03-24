"""
inspect_page.py -- Mo trang bang Playwright, ghi toan bo
input/select/button ra file inspect_result.txt de tim selector.

Chay: python inspect_page.py
"""

import sys
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

TARGET_URL  = 'https://www.pokemoncenter-online.com/login/'
OUTPUT_FILE = 'inspect_result.txt'


def inspect(url):
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
        page.goto(url, wait_until='networkidle', timeout=30000)

        lines = []
        lines.append('=' * 60)
        lines.append(f'URL:   {page.url}')
        lines.append(f'Title: {page.title()}')
        lines.append('=' * 60)

        lines.append('\n[INPUT FIELDS]')
        for el in page.query_selector_all('input'):
            name        = el.get_attribute('name') or ''
            id_         = el.get_attribute('id') or ''
            type_       = el.get_attribute('type') or 'text'
            placeholder = el.get_attribute('placeholder') or ''
            lines.append(f'  type={type_:<12} name={name:<30} id={id_:<30} placeholder={placeholder}')

        lines.append('\n[SELECT FIELDS]')
        for el in page.query_selector_all('select'):
            name = el.get_attribute('name') or ''
            id_  = el.get_attribute('id') or ''
            lines.append(f'  name={name:<30} id={id_}')

        lines.append('\n[BUTTONS]')
        for el in page.query_selector_all('button, input[type="submit"]'):
            type_ = el.get_attribute('type') or ''
            text  = (el.inner_text() or '').strip().replace('\n', ' ')
            cls   = el.get_attribute('class') or ''
            id_   = el.get_attribute('id') or ''
            lines.append(f'  type={type_:<10} id={id_:<25} class={cls:<50} text={text[:60]}')

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        sys.stdout.write(f'Done! Ket qua da ghi vao: {OUTPUT_FILE}\nNhan Enter de dong browser...\n')
        sys.stdout.flush()
        input()
        browser.close()


if __name__ == '__main__':
    inspect(TARGET_URL)
