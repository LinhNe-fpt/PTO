import time
import logging
from data_gen import generate_japanese_profile
from runner import run_pipeline
from storage import save_account
from proxy_pool import get_random_proxy
from tasks import DEFAULT_PIPELINE
from loader import load_accounts_from_file
from notifier import notify_account_success, notify_account_failure, notify_summary

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('run.log', encoding='utf-8'),
    ]
)
log = logging.getLogger(__name__)

# ── Cấu hình chung ────────────────────────────────────────────────────────────
REGISTER_URL    = 'https://trang-muon-test.com/register'   # ← URL trang đăng ký
LOGIN_URL       = 'https://trang-muon-test.com/login'      # ← URL trang đăng nhập
PROFILE_URL     = 'https://trang-muon-test.com/mypage'     # ← URL trang profile
SENDER_DOMAIN   = 'trang-muon-test.com'                    # ← domain gửi email xác nhận
PASSWORD        = 'SecurePass123!'
PREFECTURE      = '東京都'
CAPTCHA_SITEKEY = None      # '6Le...' nếu trang có reCAPTCHA
DELAY_BETWEEN_ACCOUNTS = 30 # giây chờ giữa các tài khoản

ACCOUNTS_FILE   = 'accounts.txt'  # ← đường dẫn file email

# ── Nạp danh sách tài khoản từ file ──────────────────────────────────────────
ACCOUNT_LIST = load_accounts_from_file(ACCOUNTS_FILE)


def build_account(entry):
    """Gộp thông tin cố định + dữ liệu sinh ngẫu nhiên thành 1 dict account."""
    profile = generate_japanese_profile()
    return {
        **profile,
        'email':           entry['email'],
        'email_password':  entry['email_password'],
        'password':        PASSWORD,
        'prefecture':      PREFECTURE,
        'register_url':    REGISTER_URL,
        'login_url':       LOGIN_URL,
        'profile_url':     PROFILE_URL,
        'sender_domain':   SENDER_DOMAIN,
        'captcha_sitekey': CAPTCHA_SITEKEY,
    }


def main():
    total   = len(ACCOUNT_LIST)
    success = 0
    failed  = []

    for i, entry in enumerate(ACCOUNT_LIST, 1):
        account = build_account(entry)
        proxy   = get_random_proxy()
        email   = account['email']

        log.info(f"{'='*60}")
        log.info(f"[{i}/{total}] Starting pipeline for: {email}")
        log.info(f"{'='*60}")

        ok, failed_task = run_pipeline(
            account, pipeline=DEFAULT_PIPELINE, proxy=proxy, index=i, total=total
        )

        if ok:
            save_account({
                'email':      email,
                'password':   PASSWORD,
                'prefecture': PREFECTURE,
            })
            success += 1
            notify_account_success(email, i, total)
        else:
            failed.append({'email': email, 'failed_at': failed_task})
            notify_account_failure(email, i, total, failed_task)

        if i < total:
            log.info(f"Waiting {DELAY_BETWEEN_ACCOUNTS}s before next account...\n")
            time.sleep(DELAY_BETWEEN_ACCOUNTS)

    # ── Tổng kết ──────────────────────────────────────────────────────────────
    notify_summary(success, total, failed, popup=True)


if __name__ == '__main__':
    main()
