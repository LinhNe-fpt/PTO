"""
test_step1.py -- Chi chay buoc 1: submit email len Pokemon Center.
Khong can App Password. Kiem tra browser + selector co dung khong.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

EMAIL = 'linhne2005nov@gmail.com'


def main():
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

        print('Step 1: Opening login page...')
        page.goto('https://www.pokemoncenter-online.com/login/', wait_until='networkidle', timeout=30000)
        print(f'  URL   : {page.url}')
        print(f'  Title : {page.title()}')

        email_field = page.query_selector('#login-form-regist-email')
        reg_button  = page.query_selector('#form2Button')
        print(f'  Email field found  : {email_field is not None}')
        print(f'  Register btn found : {reg_button is not None}')

        if not email_field or not reg_button:
            print('ERROR: Selector not found. Check inspect_result.txt for correct selectors.')
            browser.close()
            return

        print(f'\nStep 2: Filling email: {EMAIL}')
        page.fill('#login-form-regist-email', EMAIL)

        print('Step 3: Clicking register button...')
        page.click('#form2Button')
        page.wait_for_url('**/temporary-customer-confirm/**', timeout=15000)
        print(f'  URL: {page.url}')

        send_btn = page.query_selector('#send-confirmation-email')
        print(f'  Send email button found: {send_btn is not None}')

        if send_btn:
            print('Step 4: Clicking send confirmation email button...')
            page.click('#send-confirmation-email')
            page.wait_for_load_state('networkidle', timeout=15000)

        print(f'\nResult:')
        print(f'  URL after send : {page.url}')
        print(f'  Title          : {page.title()}')
        page.screenshot(path='test_step1_result.png')
        print('  Screenshot saved: test_step1_result.png')
        print('\n[PASS] Done! Check linh2005nov@gmail.com for activation link.')

        browser.close()


if __name__ == '__main__':
    main()
