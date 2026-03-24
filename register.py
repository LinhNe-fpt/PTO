import time
import logging
from playwright_stealth import Stealth
from browser import create_browser_context
from data_gen import generate_japanese_profile
from captcha import solve_recaptcha_v2, inject_recaptcha_token

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def fill_registration_form(page, data):
    page.fill('input[name="email"]', data['email'])
    page.fill('input[name="password"]', data['password'])
    page.fill('input[name="last_name"]', data['last_name_katakana'])
    page.fill('input[name="first_name"]', data['first_name_katakana'])
    page.fill('input[name="postal_code"]', data['postal_code'])
    page.select_option('select[name="prefecture"]', data['prefecture'])
    page.fill('input[name="city"]', data['city'])
    page.fill('input[name="street"]', data['street'])
    page.fill('input[name="tel"]', data['phone'])


def _attempt_register(url, profile, captcha_sitekey, proxy):
    playwright, browser, context = create_browser_context(proxy=proxy)
    page = context.new_page()
    Stealth().apply_stealth_sync(page)

    try:
        page.goto(url)
        fill_registration_form(page, profile)

        if captcha_sitekey:
            token = solve_recaptcha_v2(captcha_sitekey, url)
            inject_recaptcha_token(page, token)

        page.click('button[type="submit"]')
        page.wait_for_selector('.success-message', timeout=10000)
        logging.info("Registration successful")
        return True
    finally:
        browser.close()
        playwright.stop()


def register_with_retry(url, email, password, prefecture, captcha_sitekey=None, proxy=None, max_retries=3):
    profile = generate_japanese_profile()
    profile.update({'email': email, 'password': password, 'prefecture': prefecture})

    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Attempt {attempt}/{max_retries}")
            if _attempt_register(url, profile, captcha_sitekey, proxy):
                return True
        except Exception as e:
            logging.error(f"Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(5)
            else:
                raise

    return False


if __name__ == '__main__':
    register_with_retry(
        url='https://example.com/register',
        email='test@example.com',
        password='SecurePass123!',
        prefecture='東京都',
        captcha_sitekey=None,   # '6Le...' nếu có reCAPTCHA
        proxy=None              # {'ip': '1.2.3.4', 'port': '8080', 'user': 'u', 'pass': 'p'}
    )
