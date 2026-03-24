"""
run_pokecen.py -- Chay pipeline Pokemon Center Online.

Buoc 1 (lan dau): Chay voi PIPELINE_INSPECT de lay selector form dang ky.
  -> Xem file regform_dump.txt va anh regform_screenshot.png
  -> Cap nhat selector trong task_fill_regform() o tasks_pokecen.py

Buoc 2: Doi PIPELINE = PIPELINE_REGISTER va chay that.
"""

import time
import logging
from browser import create_browser_context
from playwright_stealth import Stealth
from data_gen import generate_japanese_profile
from storage import save_account
from notifier import notify_account_success, notify_account_failure, notify_summary
from loader import load_accounts_from_file

# Chon pipeline: PIPELINE_INSPECT (lan dau) hoac PIPELINE_REGISTER (dang ky that)
from tasks_pokecen import PIPELINE_INSPECT, PIPELINE_REGISTER
PIPELINE = PIPELINE_INSPECT   # <- Doi thanh PIPELINE_REGISTER sau khi co selector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('run.log', encoding='utf-8'),
    ]
)
log = logging.getLogger(__name__)

ACCOUNTS_FILE = 'accounts.txt'
PASSWORD      = 'SecurePass123!'
DELAY         = 30   # giay giua cac tai khoan


def run_account(account, index, total):
    playwright, browser, context = create_browser_context(proxy=None)
    page = context.new_page()
    Stealth().apply_stealth_sync(page)

    task_fn = None
    try:
        for task_fn in PIPELINE:
            log.info(f'  >> {task_fn.__name__}')
            task_fn(page, context, account)
        return True, None
    except Exception as e:
        name = task_fn.__name__ if task_fn else 'unknown'
        log.error(f'  !! Failed at {name}: {e}')
        try:
            page.screenshot(path=f'error_{account["email"]}.png')
        except Exception:
            pass
        return False, name
    finally:
        browser.close()
        playwright.stop()


def main():
    account_list = load_accounts_from_file(ACCOUNTS_FILE)
    total   = len(account_list)
    success = 0
    failed  = []

    for i, entry in enumerate(account_list, 1):
        profile = generate_japanese_profile()
        account = {
            **profile,
            'email':          entry['email'],
            'email_password': entry['email_password'],
            'password':       PASSWORD,
        }

        log.info(f'{"="*60}')
        log.info(f'[{i}/{total}] {account["email"]}')
        log.info(f'{"="*60}')

        ok, failed_task = run_account(account, i, total)

        if ok:
            save_account({'email': account['email'], 'password': PASSWORD})
            success += 1
            notify_account_success(account['email'], i, total)
        else:
            failed.append({'email': account['email'], 'failed_at': failed_task})
            notify_account_failure(account['email'], i, total, failed_task)

        if i < total:
            log.info(f'Waiting {DELAY}s...')
            time.sleep(DELAY)

    notify_summary(success, total, failed, popup=True)


if __name__ == '__main__':
    main()
