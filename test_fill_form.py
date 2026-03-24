"""
test_fill_form.py -- Test truc tiep buoc dien form dang ky.
Su dung link kich hoat co san, khong can gui email.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler('run.log', encoding='utf-8')]
)

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from data_gen import generate_japanese_profile
from tasks_pokecen import task_fill_regform
from storage import save_account

ACTIVATION_LINK = 'https://www.pokemoncenter-online.com/new-customer/?token=XwQZVXeyUa1h%2FaVQg9SGAqqeEAnlMoRC2OzteHt3kSo%3D'
EMAIL    = 'linh2005nov@gmail.com'
PASSWORD = 'SecurePass123!'


def main():
    profile = generate_japanese_profile()
    account = {
        **profile,
        'email':    EMAIL,
        'password': PASSWORD,
        'phone':    '09012345678',
        'activation_link': ACTIVATION_LINK,
    }

    print(f'\nProfile sinh ra:')
    print(f'  Ten       : {account["full_name"]}')
    print(f'  Furigana  : {account["full_kana"]}')
    print(f'  Nickname  : {account["nickname"]}')
    print(f'  Sinh      : {account["birthday_year"]}/{account["birthday_month"]}/{account["birthday_day"]}')
    print(f'  Dia chi   : {account["prefecture"]} {account["city"]} {account["street"]}')
    print(f'  Buu chinh : {account["postal_code"]}')
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
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

        print(f'Navigating to activation link...')
        page.goto(ACTIVATION_LINK, wait_until='networkidle', timeout=30000)
        print(f'URL: {page.url}')
        print(f'Title: {page.title()}')

        # Neu token het han -> bao loi
        if 'new-customer' not in page.url:
            print('[LOI] Token co the da het han. Can link moi.')
            page.screenshot(path='token_expired.png')
            browser.close()
            return

        print('\nDien form dang ky...')
        try:
            from tasks_pokecen import (
                task_fill_regform,
                js_fill_page, js_select_page, js_check_page
            )
        except ImportError:
            pass

        # Chi dien, KHONG submit - de kiem tra bang mat
        try:
            # Lay ham noi bo
            import tasks_pokecen as t

            def fill_only(pg, ctx, acc):
                """Chay tat ca buoc tru submit."""
                log_fn = lambda m: print(m)
                import logging
                t.log.info = log_fn

                # Goi task_fill_regform nhung thay the click submit bang wait
                # Tam thoi patch click
                original_click = pg.click
                submit_called = [False]
                def patched_click(sel, **kw):
                    if 'registration_button' in str(sel):
                        submit_called[0] = True
                        print('\n[DUNG] Da dien xong form, KHONG submit. Kiem tra browser...')
                        return
                    return original_click(sel, **kw)
                pg.click = patched_click

                t.task_fill_regform(pg, ctx, acc)
                pg.click = original_click

                if not submit_called[0]:
                    print('[NOTE] Submit button chua duoc goi')

            fill_only(page, context, account)
            page.screenshot(path='form_filled.png', full_page=True)
            print('Screenshot: form_filled.png')
            print('\nKiem tra browser! Bam Enter trong terminal de dong...')
            input()

        except Exception as e:
            print(f'\n[LOI] {e}')
            import traceback
            traceback.print_exc()
            page.screenshot(path='form_error.png')

        browser.close()


if __name__ == '__main__':
    main()
