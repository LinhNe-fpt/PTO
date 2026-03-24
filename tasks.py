"""
Mỗi hàm trong file này là một tác vụ trong pipeline.
Signature chuẩn: task_xxx(page, context, account) -> None
- page     : Playwright page hiện tại
- context  : BrowserContext (để mở tab mới nếu cần)
- account  : dict chứa thông tin tài khoản (email, password, ...)
Nếu tác vụ thất bại, raise Exception để pipeline dừng tại đó.
"""

import logging

log = logging.getLogger(__name__)


# ── Tác vụ 1: Đăng ký ────────────────────────────────────────────────────────
def task_register(page, context, account):
    from register import fill_registration_form
    from captcha import solve_recaptcha_v2, inject_recaptcha_token

    url = account['register_url']
    log.info(f"[register] Navigating to {url}")
    page.goto(url)
    fill_registration_form(page, account)

    if account.get('captcha_sitekey'):
        token = solve_recaptcha_v2(account['captcha_sitekey'], url)
        inject_recaptcha_token(page, token)

    page.click('button[type="submit"]')
    page.wait_for_selector('.success-message', timeout=10000)
    log.info("[register] Done")


# ── Tác vụ 2: Xác nhận email ─────────────────────────────────────────────────
def task_verify_email(page, context, account):
    from email_handler import get_activation_link

    log.info("[verify_email] Waiting for activation email...")
    link = get_activation_link(
        email_address=account['email'],
        password=account['email_password'],
        sender_domain=account['sender_domain'],
    )
    if not link:
        raise Exception("Activation link not found in inbox")

    log.info(f"[verify_email] Clicking activation link: {link}")
    page.goto(link)
    page.wait_for_load_state('networkidle')
    log.info("[verify_email] Done")


# ── Tác vụ 3: Đăng nhập ──────────────────────────────────────────────────────
def task_login(page, context, account):
    log.info("[login] Logging in...")
    page.goto(account['login_url'])
    page.fill('input[name="email"]', account['email'])
    page.fill('input[name="password"]', account['password'])
    page.click('button[type="submit"]')
    page.wait_for_selector('.dashboard, .mypage', timeout=10000)
    log.info("[login] Done")


# ── Tác vụ 4: Cập nhật profile ───────────────────────────────────────────────
def task_update_profile(page, context, account):
    log.info("[update_profile] Updating profile...")
    page.goto(account['profile_url'])
    # Thêm logic điền form profile ở đây
    # page.fill('input[name="birthday"]', account['birthday'])
    page.click('button[type="submit"]')
    page.wait_for_load_state('networkidle')
    log.info("[update_profile] Done")


# ── Tác vụ 5: Tác vụ tùy chỉnh khác ─────────────────────────────────────────
def task_custom(page, context, account):
    log.info("[custom] Running custom task...")
    # Thêm logic tùy chỉnh ở đây
    log.info("[custom] Done")


# ── Pipeline mặc định ─────────────────────────────────────────────────────────
# Chỉnh thứ tự hoặc bỏ bớt tác vụ tùy theo luồng của bạn
DEFAULT_PIPELINE = [
    task_register,
    task_verify_email,
    task_login,
    task_update_profile,
    task_custom,
]
