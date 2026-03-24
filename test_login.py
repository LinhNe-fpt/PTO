"""
test_login.py — Test dang nhap pokemoncenter-online.com
Chay doc lap, khong can GUI.

Cach dung:
    python test_login.py
    python test_login.py --email you@gmail.com --password YourPass123!
    python test_login.py --all          # chay tat ca tai khoan Thanh cong trong accounts.json
"""

import argparse
import json
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)

ACCOUNTS_FILE  = 'accounts.json'
DEFAULT_PASS   = 'SecurePass123!'


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def run_login_test(email: str, password: str, headless: bool = False) -> bool:
    """
    Chay 1 lan dang nhap. Tra ve True neu thanh cong.
    """
    from browser import create_browser_context
    from playwright_stealth import Stealth

    log.info(f'{"=" * 60}')
    log.info(f'Email   : {email}')
    log.info(f'Password: {"*" * len(password)} ({len(password)} ky tu)')
    log.info(f'{"=" * 60}')

    pw, browser, ctx = create_browser_context(proxy=None)
    # Ghi de headless neu can
    if headless:
        pw.stop()
        from playwright.sync_api import sync_playwright
        pw   = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        ctx  = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
        )

    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)

    # Lay email_password + birthday tu accounts.json neu co
    email_pwd   = ''
    b_year = b_month = b_day = ''
    for a in load_accounts():
        if a['email'].lower() == email.lower():
            email_pwd = a.get('email_password', '')
            b_year    = a.get('birthday_year', '')
            b_month   = a.get('birthday_month', '')
            b_day     = a.get('birthday_day', '')
            break

    account = {
        'email':          email,
        'password':       password,
        'email_password': email_pwd,
        'birthday_year':  b_year,
        'birthday_month': b_month,
        'birthday_day':   b_day,
        'otp_req_q':      None,
        'otp_res_q':      None,
    }

    from tasks_pokecen import (PIPELINE_LOGIN_SMART, task_login_pokecen,
                               task_save_session)

    ok        = False
    err_note  = ''
    try:
        # Thu session cookies truoc
        try:
            for task_fn in PIPELINE_LOGIN_SMART:
                task_fn(page, ctx, account)
        except Exception as se:
            log.info(f'[Session] {se} -> thu form login...')
            task_login_pokecen(page, ctx, account)
            task_save_session(page, ctx, account)
        ok = True
        log.info(f'[PASS] Dang nhap THANH CONG: {email}')
        log.info(f'       URL hien tai: {page.url}')
        # Chup screenshot thanh cong
        ss = f'test_login_ok_{email.split("@")[0]}.png'
        page.screenshot(path=ss)
        log.info(f'       Screenshot: {ss}')
        # Giu browser mo 5s de xem ket qua
        log.info('       Giu browser 5s...')
        time.sleep(5)
    except Exception as e:
        err_note = str(e)
        log.error(f'[FAIL] Dang nhap THAT BAI: {email}')
        log.error(f'       Loi: {err_note}')
        ss = f'test_login_fail_{email.split("@")[0]}.png'
        try:
            page.screenshot(path=ss)
            log.error(f'       Screenshot: {ss}')
        except Exception:
            pass
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass

    return ok


def run_all_registered(headless: bool = False):
    """Chay tat ca tai khoan co status Thanh cong trong accounts.json."""
    accounts = load_accounts()
    registered = [a for a in accounts if a.get('status') == 'Thanh cong']

    if not registered:
        log.warning('Khong co tai khoan nao co status "Thanh cong" trong accounts.json')
        return

    log.info(f'Tim thay {len(registered)} tai khoan Thanh cong.')
    results = []

    for i, a in enumerate(registered, 1):
        email = a['email']
        pwd   = a.get('pto_password', '').strip() or DEFAULT_PASS
        log.info(f'\n[{i}/{len(registered)}] Bat dau test: {email}')
        ok = run_login_test(email, pwd, headless=headless)
        results.append((email, ok))
        if i < len(registered):
            log.info('Nghi 5s truoc tai khoan tiep theo...')
            time.sleep(5)

    # Tong ket
    log.info('\n' + '=' * 60)
    log.info('KET QUA TONG HOP:')
    success = sum(1 for _, ok in results if ok)
    for email, ok in results:
        status = '✓ PASS' if ok else '✗ FAIL'
        log.info(f'  {status}  {email}')
    log.info(f'\nThanh cong: {success}/{len(results)}')
    log.info('=' * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Test dang nhap pokemoncenter-online.com'
    )
    parser.add_argument('--email',    help='Email can test')
    parser.add_argument('--password', help='Mat khau PTO')
    parser.add_argument('--all',      action='store_true',
                        help='Test tat ca tai khoan Thanh cong trong accounts.json')
    parser.add_argument('--headless', action='store_true',
                        help='Chay an browser (khong hien cua so)')
    args = parser.parse_args()

    if args.all:
        run_all_registered(headless=args.headless)

    elif args.email:
        pwd = args.password or DEFAULT_PASS
        ok  = run_login_test(args.email, pwd, headless=args.headless)
        sys.exit(0 if ok else 1)

    else:
        # Khong co tham so -> hien menu chon
        accounts = load_accounts()
        registered = [a for a in accounts if a.get('status') == 'Thanh cong']

        print('\n=== TEST DANG NHAP POKEMON CENTER ONLINE ===\n')

        if not registered:
            print('Chua co tai khoan Thanh cong nao trong accounts.json.')
            print('Nhap thu cong:')
            email = input('  Email    : ').strip()
            pwd   = input('  Password : ').strip() or DEFAULT_PASS
            run_login_test(email, pwd)
            return

        print('Chon tai khoan can test:')
        for i, a in enumerate(registered):
            pwd_preview = a.get('pto_password', '') or DEFAULT_PASS
            masked = pwd_preview[:2] + '*' * (len(pwd_preview) - 2)
            print(f'  [{i+1}] {a["email"]}  (pass: {masked})')
        print(f'  [0] Test TAT CA ({len(registered)} tai khoan)')
        print(f'  [m] Nhap thu cong')

        choice = input('\nLua chon: ').strip()

        if choice == '0':
            run_all_registered()
        elif choice == 'm':
            email = input('  Email    : ').strip()
            pwd   = input('  Password : ').strip() or DEFAULT_PASS
            run_login_test(email, pwd)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(registered):
                    a   = registered[idx]
                    pwd = a.get('pto_password', '').strip() or DEFAULT_PASS
                    run_login_test(a['email'], pwd)
                else:
                    print('Lua chon khong hop le.')
            except ValueError:
                print('Lua chon khong hop le.')


if __name__ == '__main__':
    main()
