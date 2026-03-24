"""
run_terminal.py -- Chay bot qua terminal (khong can GUI).
Buoc lay link kich hoat se hoi thang trong terminal.
"""

import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('run.log', encoding='utf-8'),
    ]
)

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from data_gen import generate_japanese_profile
from tasks_pokecen import PIPELINE_REGISTER
from storage import save_account

EMAIL    = 'linh2005nov@gmail.com'
PASSWORD = 'SecurePass123!'


def main():
    profile = generate_japanese_profile()
    account = {
        **profile,
        'email':          EMAIL,
        'email_password': '',      # de trong -> se hoi link thu cong
        'phone':          '',
        'password':       PASSWORD,
        # Khong co queue -> _request_activation_link se dung input() o terminal
    }

    print(f'\n{"="*55}')
    print(f'Bat dau dang ky: {EMAIL}')
    print(f'{"="*55}\n')

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

        try:
            for task_fn in PIPELINE_REGISTER:
                print(f'\n>> {task_fn.__name__}')
                task_fn(page, context, account)

            save_account({'email': EMAIL, 'password': PASSWORD})
            print(f'\n{"="*55}')
            print(f'[THANH CONG] {EMAIL} da dang ky xong!')
            print(f'{"="*55}')

        except Exception as e:
            print(f'\n[LOI] {e}')
            page.screenshot(path='terminal_error.png')
            print('Screenshot: terminal_error.png')

        input('\nNhan Enter de dong browser...')
        browser.close()


if __name__ == '__main__':
    main()
