"""
tasks_pokecen.py -- Pipeline dang ky cho pokemoncenter-online.com
Luong:
  1. task_submit_email    : Vao trang login, dien email, click "Dang ky moi"
  2. task_get_email_link  : Doc IMAP, lay link kich hoat
  3. task_inspect_regform : Mo link, dump form ra file (chay 1 lan de lay selector)
  4. task_fill_regform    : Dien form dang ky day du va submit
"""

import json
import logging
import os
import time
from email_handler import get_activation_link

log = logging.getLogger(__name__)

SITE_URL     = 'https://www.pokemoncenter-online.com'
LOGIN_URL    = f'{SITE_URL}/login/'
DUMP_FILE    = 'regform_dump.txt'
SESSIONS_DIR = 'sessions'


def _request_otp(account, prompt):
    req_q = account.get('otp_req_q')
    res_q = account.get('otp_res_q')
    if req_q and res_q:
        req_q.put({'email': account['email'], 'prompt': prompt})
        return res_q.get(timeout=180)
    return input(f'[OTP] {account["email"]} -- {prompt}: ')


def _request_activation_link(account):
    """
    Lay link kich hoat theo thu tu uu tien:
    1. Popup GUI cho nguoi dung dan link tu email
    2. Tu dong doc IMAP (neu co App Password)
    3. Nhap tay terminal (fallback)
    """
    req_q = account.get('link_req_q')
    res_q = account.get('link_res_q')

    # Uu tien 1: Popup GUI
    if req_q and res_q:
        log.info('[2] Hien popup cho ban dan link kich hoat...')
        req_q.put({'email': account['email']})
        link = res_q.get(timeout=300)
        if link:
            return link.strip()

    # Uu tien 2: IMAP tu dong
    if account.get('email_password'):
        log.info('[2] Doc email qua IMAP...')
        link = get_activation_link(
            email_address=account['email'],
            password=account['email_password'],
            sender_domain='pokemoncenter-online.com',
            retries=10, wait=15,
        )
        if link:
            return link

    # Fallback: terminal
    return input(f'[2] Dan link kich hoat cho {account["email"]}: ').strip()


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Submit email de yeu cau dang ky
# ─────────────────────────────────────────────────────────────────────────────
def task_submit_email(page, context, account):
    log.info('[1] Navigating to login page...')
    page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)

    log.info('[1] Filling registration email...')
    page.fill('#login-form-regist-email', account['email'])

    log.info('[1] Clicking register button...')
    page.click('#form2Button')
    page.wait_for_url('**/temporary-customer-confirm/**', timeout=15000)
    log.info('[1] Reached confirmation page.')

    # Trang nay co nut "仮登録メールを送信する" can click de gui email xac nhan
    log.info('[1] Clicking send confirmation email button...')
    page.click('#send-confirmation-email')
    page.wait_for_load_state('networkidle', timeout=15000)
    log.info(f'[1] After send click URL: {page.url}')
    log.info('[1] Confirmation email sent successfully.')


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Doc IMAP, lay link kich hoat
# ─────────────────────────────────────────────────────────────────────────────
def task_get_email_link(page, context, account):
    link = _request_activation_link(account)
    if not link:
        raise Exception('Khong lay duoc link kich hoat')
    account['activation_link'] = link
    log.info(f'[2] Activation link: {link}')


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: Mo link kich hoat va dump toan bo form ra file
# (Chi can chay 1 lan de lay selector, sau do co the bo task nay)
# ─────────────────────────────────────────────────────────────────────────────
def task_inspect_regform(page, context, account):
    link = account.get('activation_link')
    if not link:
        raise Exception('No activation link found in account dict')

    log.info(f'[3] Opening activation link: {link}')
    page.goto(link, wait_until='networkidle', timeout=30000)

    lines = []
    lines.append(f'URL: {page.url}')
    lines.append(f'Title: {page.title()}')
    lines.append('')

    lines.append('[INPUT FIELDS]')
    for el in page.query_selector_all('input'):
        name        = el.get_attribute('name') or ''
        id_         = el.get_attribute('id') or ''
        type_       = el.get_attribute('type') or 'text'
        placeholder = el.get_attribute('placeholder') or ''
        lines.append(f'  type={type_:<14} name={name:<45} id={id_:<45} placeholder={placeholder}')

    lines.append('')
    lines.append('[SELECT FIELDS]')
    for el in page.query_selector_all('select'):
        name = el.get_attribute('name') or ''
        id_  = el.get_attribute('id') or ''
        options = [o.get_attribute('value') or '' for o in el.query_selector_all('option')]
        lines.append(f'  name={name:<45} id={id_}')
        lines.append(f'    values: {options}')

    lines.append('')
    lines.append('[BUTTONS]')
    for el in page.query_selector_all('button, input[type="submit"]'):
        type_ = el.get_attribute('type') or ''
        text  = (el.inner_text() or '').strip().replace('\n', ' ')
        id_   = el.get_attribute('id') or ''
        cls   = el.get_attribute('class') or ''
        lines.append(f'  type={type_:<10} id={id_:<30} class={cls:<50} text={text[:60]}')

    lines.append('')
    lines.append('[FORMS]')
    for el in page.query_selector_all('form'):
        action = el.get_attribute('action') or ''
        method = el.get_attribute('method') or ''
        lines.append(f'  action={action}  method={method}')

    # Luu screenshot
    page.screenshot(path='regform_screenshot.png', full_page=True)
    log.info('[3] Screenshot saved: regform_screenshot.png')

    with open(DUMP_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    log.info(f'[3] Form dump saved: {DUMP_FILE}')


# ─────────────────────────────────────────────────────────────────────────────
# Task 4: Dien form dang ky day du va submit
# (Cap nhat selector sau khi doc regform_dump.txt)
# ─────────────────────────────────────────────────────────────────────────────
def task_fill_regform(page, context, account):
    # Mo URL kich hoat neu chua o trang do
    link = account.get('activation_link', '')
    if link and ('new-customer' in page.url or page.url == 'about:blank' or link not in page.url):
        log.info(f'[4] Navigating to activation link...')
        page.goto(link, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(1500)

    log.info('[4] Filling registration form...')

    def js_fill(selector, value):
        """Dien gia tri va trigger tat ca event (input, change, blur) qua JS."""
        if not value:
            return
        try:
            page.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{selector}');
                    if (!el) return;
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(el, {repr(value)});
                    el.dispatchEvent(new Event('input',  {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('blur',   {{ bubbles: true }}));
                }})();
            """)
        except Exception as e:
            log.warning(f'js_fill failed {selector}: {e}')

    def js_select(selector, value):
        """Chon option va trigger event."""
        if not value:
            return
        try:
            page.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{selector}');
                    if (!el) return;
                    el.value = {repr(value)};
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }})();
            """)
        except Exception as e:
            log.warning(f'js_select failed {selector}: {e}')

    def js_check(selector):
        """Tick checkbox va trigger event."""
        try:
            page.evaluate(f"""
                (function() {{
                    var el = document.querySelector('{selector}');
                    if (!el) return;
                    el.checked = true;
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('click',  {{ bubbles: true }}));
                }})();
            """)
        except Exception as e:
            log.warning(f'js_check failed {selector}: {e}')

    # ── Buoc 1: Dien thong tin ca nhan ───────────────────────────────────────
    log.info('[4] Step 1: Personal info...')
    js_fill('#registration-form-nname', account.get('nickname', ''))
    js_fill('#registration-form-fname', account.get('full_name', ''))
    js_fill('#registration-form-kana',  account.get('full_kana', ''))

    # ── Buoc 2: Ngay sinh + gioi tinh ────────────────────────────────────────
    log.info('[4] Step 2: Birthday & gender...')
    js_select('#registration-form-birthdayyear',  account.get('birthday_year', '1990'))
    js_select('#registration-form-birthdaymonth', account.get('birthday_month', '01'))
    js_select('#registration-form-birthdayday',   account.get('birthday_day', '01'))
    js_select('[name="dwfrm_profile_customer_gender"]', account.get('gender', '1'))

    # ── Buoc 3: Ma buu chinh → auto-fill tinh/thanh pho ─────────────────────
    log.info('[4] Step 3: Postal code lookup...')
    postal = account.get('postal_code', '1060032')
    js_fill('#registration-form-postcode', postal)
    # Click nut tra cuu buu chinh (neu co), neu khong thi Tab de trigger
    try:
        btn = page.query_selector('.postcode-search-btn, .postal-search, [class*="postcode"]')
        if btn:
            btn.click()
        else:
            page.locator('#registration-form-postcode').press('Tab')
    except Exception:
        pass
    page.wait_for_timeout(2000)  # Cho AJAX hoan thanh

    # ── Buoc 4: Dien dia chi (SAU khi AJAX xong) ─────────────────────────────
    log.info('[4] Step 4: Address...')
    js_select('#registration-form-address-level1', account.get('prefecture', '東京都'))
    page.wait_for_timeout(500)
    city = account.get('city', '港区六本木')[:12]  # toi da 12 ky tu toan goc
    js_fill('#registration-form-address-level2', city)
    js_fill('#registration-form-address-line1',  account.get('street', '６−１０−１'))
    js_fill('#registration-form-address-line2',  account.get('building', ''))

    # ── Buoc 5: So dien thoai ────────────────────────────────────────────────
    log.info('[4] Step 5: Phone...')
    phone = account.get('phone') or account.get('phone_gen', '09012345678')
    # Tel field khong co id -> dung name selector qua JS
    page.evaluate(f"""
        (function() {{
            var el = document.querySelector('[name="dwfrm_profile_customer_phone"]');
            if (!el) return;
            var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            setter.call(el, {repr(phone)});
            el.dispatchEvent(new Event('input',  {{bubbles:true}}));
            el.dispatchEvent(new Event('change', {{bubbles:true}}));
            el.dispatchEvent(new Event('blur',   {{bubbles:true}}));
        }})();
    """)

    # ── Buoc 6: Mat khau ─────────────────────────────────────────────────────
    log.info('[4] Step 6: Password...')
    pwd = account['password']
    for sel in ['[name="dwfrm_profile_login_password"]', '[name="dwfrm_profile_login_passwordconfirm"]']:
        page.evaluate(f"""
            (function() {{
                var inputs = document.querySelectorAll('{sel}');
                inputs.forEach(function(el) {{
                    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                    setter.call(el, {repr(pwd)});
                    el.dispatchEvent(new Event('input',  {{bubbles:true}}));
                    el.dispatchEvent(new Event('change', {{bubbles:true}}));
                    el.dispatchEvent(new Event('blur',   {{bubbles:true}}));
                }});
            }})();
        """)

    # ── Buoc 7: Email newsletter radio (chon "Khong nhan") ───────────────────
    log.info('[4] Step 7: Newsletter radio...')
    page.evaluate("""
        (function() {
            var radios = document.querySelectorAll('[name="dwfrm_profile_customer_addtoemaillist"]');
            if (radios.length >= 2) {
                radios[1].checked = true;
                radios[1].dispatchEvent(new Event('change', {bubbles: true}));
            }
        })();
    """)

    # ── Buoc 8: Tick dong y dieu khoan ───────────────────────────────────────
    log.info('[4] Step 8: Agree to terms...')
    js_check('#terms')
    js_check('#privacyPolicy')
    page.wait_for_timeout(500)

    # Kiem tra OTP
    if _has_otp_field(page):
        log.info('[4] OTP field detected!')
        otp = _request_otp(account, f'Nhap ma OTP gui den SDT {phone}:')
        for sel in ['[name="otp"]', '[name="sms_code"]', '[name="verificationCode"]', '#otp']:
            js_fill(sel, otp)

    # ── Buoc 9: Submit ────────────────────────────────────────────────────────
    log.info('[4] Step 9: Submitting...')
    page.click('#registration_button')
    # Cho trang chuyen trang (domcontentloaded nhanh hon networkidle)
    try:
        page.wait_for_load_state('domcontentloaded', timeout=25000)
        page.wait_for_timeout(2000)
    except Exception:
        pass
    log.info(f'[4] URL after submit: {page.url}')

    # Kiem tra loi
    error_els = page.query_selector_all('.form-group-error, .error-message, [class*="error"]')
    if error_els:
        errors = [e.inner_text().strip() for e in error_els if e.inner_text().strip()]
        if errors:
            page.screenshot(path='regform_error.png')
            raise Exception(f'Form errors: {"; ".join(errors[:5])}')

    log.info('[4] Registration form submitted successfully.')


def _has_otp_field(page):
    for sel in ['[name="otp"]', '[name="sms_code"]', '[name="verificationCode"]', '#otp']:
        if page.query_selector(sel):
            return True
    return False


def _try_select(page, selector, value):
    try:
        el = page.query_selector(selector)
        if el and value:
            el.select_option(value)
    except Exception as e:
        log.warning(f'Could not select {selector}={value}: {e}')


def _try_check(page, selector):
    try:
        el = page.query_selector(selector)
        if el and not el.is_checked():
            el.check()
    except Exception as e:
        log.warning(f'Could not check {selector}: {e}')


def _try_fill(page, selector, value):
    """Dien vao field neu ton tai, bo qua neu khong tim thay."""
    try:
        el = page.query_selector(selector)
        if el and value:
            el.fill(value)
    except Exception as e:
        log.warning(f'Could not fill {selector}: {e}')


# ─────────────────────────────────────────────────────────────────────────────
# Task: Inspect trang login – chay 1 lan de lay selector chinh xac
# ─────────────────────────────────────────────────────────────────────────────
LOGIN_DUMP_FILE = 'login_form_dump.txt'

def task_inspect_login_page(page, context, account):
    """
    Mo trang login, dump toan bo input/button ra file login_form_dump.txt
    va chup screenshot login_screenshot.png.
    Chay 1 lan roi doc file de lay dung selector cho task_login_pokecen.
    """
    log.info('[InspectLogin] Navigating to login page...')
    page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)

    lines = [f'URL: {page.url}', f'Title: {page.title()}', '']

    lines.append('[INPUT FIELDS]')
    for el in page.query_selector_all('input'):
        lines.append(
            f'  type={el.get_attribute("type") or "text":<14}'
            f'  name={el.get_attribute("name") or "":<40}'
            f'  id={el.get_attribute("id") or "":<40}'
            f'  placeholder={el.get_attribute("placeholder") or ""}'
        )

    lines.append('')
    lines.append('[BUTTONS / SUBMITS]')
    for el in page.query_selector_all('button, input[type="submit"]'):
        lines.append(
            f'  type={el.get_attribute("type") or "":<10}'
            f'  id={el.get_attribute("id") or "":<30}'
            f'  name={el.get_attribute("name") or "":<30}'
            f'  class={el.get_attribute("class") or "":<50}'
            f'  text={el.inner_text().strip().replace(chr(10)," ")[:60]}'
        )

    lines.append('')
    lines.append('[FORMS]')
    for el in page.query_selector_all('form'):
        lines.append(
            f'  id={el.get_attribute("id") or "":<30}'
            f'  action={el.get_attribute("action") or ""}'
        )

    page.screenshot(path='login_screenshot.png', full_page=True)
    log.info('[InspectLogin] Screenshot: login_screenshot.png')

    with open(LOGIN_DUMP_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    log.info(f'[InspectLogin] Dump saved: {LOGIN_DUMP_FILE}')
    log.info('[InspectLogin] Mo file login_form_dump.txt de xem selector chinh xac.')


# ─────────────────────────────────────────────────────────────────────────────
# Task: Dang nhap vao tai khoan da dang ky
# ─────────────────────────────────────────────────────────────────────────────
def _js_fill_login(page, selector, value):
    """Dien gia tri qua JS, trigger tat ca synthetic event (giong regform)."""
    try:
        page.evaluate(f"""
            (function() {{
                var el = document.querySelector('{selector}');
                if (!el) return;
                var setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, {repr(value)});
                el.dispatchEvent(new Event('input',  {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                el.dispatchEvent(new Event('blur',   {{ bubbles: true }}));
            }})();
        """)
    except Exception as e:
        log.warning(f'js_fill_login {selector}: {e}')


def _find_and_fill(page, selectors, value, label):
    """Thu lan luot cac selector, dien gia tri bang JS, log selector tim thay."""
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            log.info(f'[Login] {label} -> selector: {sel}')
            _js_fill_login(page, sel, value)
            return sel
    log.warning(f'[Login] KHONG TIM THAY selector cho {label}! Thu cac sel: {selectors}')
    return None


def _type_into(page, locator, text, delay=40):
    """Go tung ky tu vao field, tuong thich ca Playwright moi va cu."""
    locator.click()
    try:
        locator.press('Control+a')
        locator.press('Delete')
    except Exception:
        pass
    try:
        locator.press_sequentially(text, delay=delay)   # Playwright >= 1.38
    except AttributeError:
        locator.type(text, delay=delay)                 # Playwright < 1.38


def _get_reset_link(account):
    """
    Lay link dat lai mat khau theo thu tu uu tien:
    1. IMAP tu dong (neu co email_password)
    2. Popup GUI yeu cau user dan link (dung otp_req_q)
    3. Nhap tay terminal (fallback)
    """
    # Uu tien 1: IMAP tu dong
    email_pwd = account.get('email_password', '').strip()
    if email_pwd:
        from email_handler import get_password_reset_link
        log.info('[PwReset] Doc IMAP tim link reset (toi da 3 phut)...')
        url = get_password_reset_link(
            email_address=account['email'],
            password=email_pwd,
            retries=12, wait=15,
        )
        if url:
            return url
        log.warning('[PwReset] Khong tim thay qua IMAP, chuyen sang popup...')

    # Uu tien 2: Popup GUI (dung otp dialog voi prompt mo ta ro)
    req_q = account.get('otp_req_q')
    res_q = account.get('otp_res_q')
    if req_q and res_q:
        prompt = (
            f'Tai khoan {account["email"]} can dat lai mat khau.\n\n'
            '1. Mo Gmail cua tai khoan nay\n'
            '2. Tim email tu pokemoncenter-online.com\n'
            '3. Copy TOAN BO duong link dat lai mat khau\n'
            '4. Dan vao o ben duoi va bam Xac nhan'
        )
        log.info('[PwReset] Hien popup yeu cau user dan link reset...')
        req_q.put({'email': account['email'], 'prompt': prompt})
        url = res_q.get(timeout=300)   # cho toi da 5 phut
        if url and url.strip():
            return url.strip()

    # Fallback: terminal
    log.warning('[PwReset] Nhap link reset tay qua terminal...')
    return input(
        f'[PwReset] Dan link dat lai mat khau cho {account["email"]}:\n> '
    ).strip()


RESET_URL = f'{SITE_URL}/reset-password/'


def _fill_new_password(page, account):
    """Dien mat khau moi + xac nhan vao form."""
    new_pwd = account['password']
    pwd_inputs = page.query_selector_all('input[type="password"]')
    for inp in pwd_inputs:
        sel = f'#{inp.get_attribute("id")}' if inp.get_attribute('id') else 'input[type="password"]'
        try:
            _type_into(page, page.locator(sel).first, new_pwd, delay=30)
        except Exception:
            pass
    page.wait_for_timeout(400)
    for btn_sel in ['button[type="submit"]', 'input[type="submit"]', '#reset-confirm']:
        btn = page.query_selector(btn_sel)
        if btn:
            btn.click()
            break
    else:
        page.keyboard.press('Enter')
    try:
        page.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        pass
    log.info(f'[PwReset] Mat khau moi da dat: {page.url}')
    account['password_reset_done'] = True


def _fill_reset_form_fields(page, account):
    """Dien email + cac truong sinh nhat vao form reset-password."""
    # ── Dien email ──────────────────────────────────────────────────────────
    # Selectors ưu tiên từ cao xuống thấp (dựa trên reset_form_dump.txt thực tế)
    email_filled = False
    email_selectors = [
        '#email',                                        # id=email (SFCC reset form)
        '[name="dwfrm_profile_passwordreset_email"]',   # SFCC exact name
        'input[type="email"]',
        '[name="email"]',
        '[name="loginID"]',
        '[name="username"]',
        '#login-form-email',
    ]
    for sel in email_selectors:
        if email_filled:
            break
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1000):
                loc.click(click_count=3)
                loc.press('Control+a')
                loc.press('Backspace')
                loc.type(account['email'], delay=40)
                val_check = loc.evaluate('el=>el.value')
                if account['email'].lower() in val_check.lower():
                    log.info(f'[PwReset] Email da dien vao: {sel}')
                    email_filled = True
        except Exception:
            pass

    if not email_filled:
        log.warning('[PwReset] Khong tim thay o email qua selectors, thu JavaScript inject...')
        try:
            safe_email = account['email'].replace('"', '\\"')
            page.evaluate(f'''
                const sel = document.querySelector(
                  "#email, [name='dwfrm_profile_passwordreset_email'], input[type=email]"
                );
                if (sel) {{
                    sel.value = "{safe_email}";
                    sel.dispatchEvent(new Event("input",  {{bubbles:true}}));
                    sel.dispatchEvent(new Event("change", {{bubbles:true}}));
                }}
            ''')
            log.info('[PwReset] Email inject qua JavaScript')
        except Exception as e:
            log.warning(f'[PwReset] JS inject loi: {e}')

    page.wait_for_timeout(300)

    # ── Dien sinh nhat (3 select dropdown: nam / thang / ngay) ─────────────
    import random as _rand
    by_year  = account.get('birthday_year', '').strip()
    by_month = account.get('birthday_month', '').strip()
    by_day   = account.get('birthday_day', '').strip()

    # Fallback khi khong co birthday da luu: chon ngau nhien trong khoang hop ly
    # Nam: 2000-2006 (18-26 tuoi), thang: 1-12, ngay: 1-28
    fallback_year  = str(_rand.randint(2000, 2006))
    fallback_month = str(_rand.randint(1, 12))
    fallback_day   = str(_rand.randint(1, 28))

    selects = page.query_selector_all('select')
    log.info(f'[PwReset] Tim thay {len(selects)} select dropdown')

    for idx, sel_el in enumerate(selects):
        sel_id   = sel_el.get_attribute('id')   or ''
        sel_name = sel_el.get_attribute('name') or ''
        key      = (sel_id + sel_name).lower()
        options  = sel_el.query_selector_all('option')

        # Xac dinh day la dropdown gi (year / month / day)
        is_year  = any(k in key for k in ('year', 'yyyy', 'nen', 'birth_y', 'birthdayyear'))
        is_month = any(k in key for k in ('month', 'mm', 'mon', 'tsuki', 'birthdaymonth'))
        is_day   = any(k in key for k in ('day', 'dd', 'nichi', 'birthdayday'))

        if not (is_year or is_month or is_day):
            if idx == 0:   is_year  = True
            elif idx == 1: is_month = True
            elif idx == 2: is_day   = True

        # Chon gia tri uu tien: da luu -> fallback hop ly
        if is_year:
            chosen = by_year or fallback_year
        elif is_month:
            chosen = (by_month.lstrip('0') or fallback_month) if by_month else fallback_month
        elif is_day:
            chosen = (by_day.lstrip('0') or fallback_day) if by_day else fallback_day
        else:
            continue

        # Lay tat ca gia tri option hop le (khong phai placeholder)
        valid_opts = []
        for opt in options:
            v = opt.get_attribute('value') or ''
            if v and v not in ('', '0', '--', '-'):
                valid_opts.append(v)

        if not valid_opts:
            continue

        # Tim option khop voi chosen
        target_val = None
        for opt in options:
            v = opt.get_attribute('value') or ''
            t = opt.inner_text().strip()
            if v == str(chosen) or t == str(chosen) or t.startswith(str(chosen)):
                target_val = v
                break
        if not target_val:
            # Neu khong tim thay exact match, chon option dau tien hop le
            target_val = valid_opts[0]

        try:
            locator_sel = f'#{sel_id}' if sel_id else f'[name="{sel_name}"]'
            page.select_option(locator_sel, value=target_val)
            log.info(f'[PwReset] Select[{idx}] {sel_id or sel_name} = {target_val}  (muon={chosen})')
        except Exception as e:
            log.warning(f'[PwReset] select loi idx={idx}: {e}')

    page.wait_for_timeout(500)


def _do_password_reset(page, account):
    """
    Xu ly flow dat lai mat khau HOAN TOAN TU DONG, khong hien popup.
    Luong:
      1. Vao /reset-password/
      2. Dien email + sinh nhat (dropdown)
      3. Submit
      4a. Trang hien o nhap mat khau moi -> dien luon
      4b. Trang gui email -> lay link qua IMAP -> mo link -> dien mat khau moi
      4c. Khong co IMAP -> bao loi ro rang (khong popup)
    """
    log.info('[PwReset] Xu ly dat lai mat khau tu dong...')
    page.goto(RESET_URL, wait_until='networkidle', timeout=20000)
    page.wait_for_timeout(2000)
    log.info(f'[PwReset] Trang reset: {page.url}')

    # ── Dump form lan dau de debug ────────────────────────────────────────────
    dump_path = 'reset_form_dump.txt'
    lines = ['[RESET FORM DUMP]', f'URL: {page.url}', '']
    for el in page.query_selector_all('input, select'):
        tag  = el.evaluate("el=>el.tagName")
        typ  = el.get_attribute("type")  or ''
        name = el.get_attribute("name")  or ''
        eid  = el.get_attribute("id")    or ''
        ph   = el.get_attribute("placeholder") or ''
        vis  = el.is_visible()
        if tag == 'SELECT':
            opts = [f'{o.get_attribute("value")}={o.inner_text().strip()}'
                    for o in el.query_selector_all('option')[:5]]
            lines.append(f'  SELECT  id={eid:<25} name={name:<25} visible={vis} opts={opts}')
        else:
            lines.append(f'  INPUT   type={typ:<10} id={eid:<25} name={name:<25} ph="{ph}" visible={vis}')
    for el in page.query_selector_all('button'):
        lines.append(f'  BUTTON id={el.get_attribute("id") or ""} text={el.inner_text().strip()[:60]}')
    with open(dump_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    page.screenshot(path='reset_page_screenshot.png', full_page=True)
    log.info(f'[PwReset] Da luu {dump_path} + reset_page_screenshot.png')

    # ── Dien form ─────────────────────────────────────────────────────────────
    _fill_reset_form_fields(page, account)

    # ── Submit ────────────────────────────────────────────────────────────────
    log.info('[PwReset] Submitting...')
    submitted = False
    for btn_sel in ['button[type="submit"]', 'input[type="submit"]', '#reset-button', 'button']:
        try:
            btns = page.query_selector_all(btn_sel)
            for btn in btns:
                if btn.is_visible():
                    btn.click()
                    log.info(f'[PwReset] Click submit: {btn_sel}')
                    submitted = True
                    break
        except Exception:
            pass
        if submitted:
            break
    if not submitted:
        page.keyboard.press('Enter')

    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except Exception:
        pass
    page.wait_for_timeout(2000)
    after_url = page.url
    log.info(f'[PwReset] URL sau submit: {after_url}')
    page.screenshot(path='reset_after_submit.png', full_page=True)

    # ── Ket qua A: Trang cho nhap mat khau moi truc tiep ──────────────────────
    pwd_inputs = page.query_selector_all('input[type="password"]')
    if pwd_inputs:
        log.info('[PwReset] Trang cho nhap mat khau moi truc tiep!')
        _fill_new_password(page, account)
        return

    # ── Kiem tra: neu URL van la /reset-password/ → form bi reject (email sai/trong) ─
    if 'reset-password' in after_url.lower() and after_url.rstrip('/') == RESET_URL.rstrip('/'):
        # Thu doc thong bao loi tren trang
        err_msg = ''
        try:
            err_msg = page.locator(
                '.error-message, .form-group-error, [class*="error"], .alert'
            ).first.inner_text(timeout=2000).strip()
        except Exception:
            pass
        raise Exception(
            f'[PwReset] Form reset bi tu choi (URL khong thay doi). '
            f'Co the email khong dien duoc hoac sai thong tin.'
            + (f' Loi trang: {err_msg}' if err_msg else '')
        )

    # ── Ket qua B: Phai lay reset link tu email ──────────────────────────────
    log.info('[PwReset] Trang da gui email reset. Thu lay link qua IMAP...')
    email_pwd = account.get('email_password', '').strip()
    if not email_pwd:
        raise Exception(
            f'Tai khoan {account["email"]} can dat lai mat khau nhung chua co App Password Gmail.\n'
            'Them App Password Gmail vao cot "App Password Gmail" trong phan Sua tai khoan.'
        )

    from email_handler import get_password_reset_link
    reset_url = get_password_reset_link(
        email_address=account['email'],
        password=email_pwd,
        retries=12, wait=15,
    )
    if not reset_url:
        raise Exception(f'Khong tim thay link reset trong email sau 3 phut ({account["email"]}).')

    log.info(f'[PwReset] Link reset: {reset_url}')
    page.goto(reset_url, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)

    pwd_inputs2 = page.query_selector_all('input[type="password"]')
    if pwd_inputs2:
        _fill_new_password(page, account)
    else:
        log.warning(f'[PwReset] Khong tim thay o mat khau sau khi mo link reset. URL: {page.url}')


def task_login_pokecen(page, context, account):
    """
    Dang nhap pokemoncenter-online.com (SAP CDC / Gigya).
    Tu dong xu ly ca truong hop trang yeu cau dat lai mat khau.
    """
    log.info('[Login] Navigating to login page...')
    page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(3000)   # cho Gigya SDK khoi dong

    email = account['email']
    pwd   = account['password']

    log.info(f'[Login] Typing email: {email}')
    _type_into(page, page.locator('#login-form-email'), email)
    page.keyboard.press('Tab')
    page.wait_for_timeout(500)

    log.info('[Login] Typing password...')
    _type_into(page, page.locator('#current-password'), pwd)
    page.keyboard.press('Tab')
    page.wait_for_timeout(1000)

    log.info('[Login] Clicking submit #form1Button...')
    page.locator('#form1Button').click()

    try:
        page.wait_for_load_state('networkidle', timeout=20000)
    except Exception:
        pass

    current_url = page.url
    log.info(f'[Login] URL sau submit: {current_url}')
    # Luu screenshot de debug
    try:
        page.screenshot(path=f'login_after_submit_{email.split("@")[0]}.png', full_page=True)
    except Exception:
        pass

    # ── Kiem tra yeu cau dat lai mat khau (password reset) ───────────────────
    if 'login' in current_url.lower():
        page_text = ''
        page_html = ''
        try:
            page_text = page.locator('body').inner_text(timeout=3000)
            page_html = page.content()
        except Exception:
            pass

        # Chi trigger khi trang THUC SU yeu cau reset bat buoc (co banner thong bao)
        # Khong trigger khi chi co link "quen mat khau" binh thuong o cuoi trang
        mandatory_reset_indicators = [
            # Banner/thong bao bat buoc doi mat khau (cac bien the tieng Nhat)
            'パスワードリセット' in page_text,
            'パスワードの再設定' in page_text,
            'パスワードを再設定' in page_text,
            'パスワードを変更' in page_text,
            # SFCC class indicators (banner, not just any link)
            bool(page.query_selector(
                '.password-reset-message, .reset-password-notice, '
                '[class*="password-reset-notice"], [class*="passwordreset-notice"], '
                '#password-reset-info, #passwordReset, .password-required-notice'
            )),
            # Link reset-password trong BODY BANNER (header/hero), không phải footer/nav
            bool(page.query_selector(
                '.banner a[href*="reset-password"], .notice a[href*="reset-password"], '
                '.alert a[href*="reset-password"], header a[href*="reset-password"]'
            )),
        ]
        need_reset = any(mandatory_reset_indicators)

        # Neu van o trang login nhung KHONG phai reset -> mat khau sai
        if not need_reset:
            err_text = ''
            try:
                err_text = page.locator(
                    '.error-message, .alert, [class*="error"], '
                    '#errorcommon, #erroLock, .form-group-error'
                ).first.inner_text(timeout=2000).strip()
            except Exception:
                pass
            raise Exception(
                f'Dang nhap that bai. '
                + (f'Loi: {err_text}' if err_text else 'Sai mat khau hoac tai khoan bi khoa.')
            )

        if need_reset and not account.get('password_reset_done'):
            log.info('[Login] Trang yeu cau dat lai mat khau. Bat dau xu ly...')
            _do_password_reset(page, account)
            # Sau reset, thu dang nhap lai
            log.info('[Login] Thu dang nhap lai sau khi dat lai mat khau...')
            page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)
            _type_into(page, page.locator('#login-form-email'), email)
            page.keyboard.press('Tab')
            page.wait_for_timeout(500)
            _type_into(page, page.locator('#current-password'), account['password'])
            page.keyboard.press('Tab')
            page.wait_for_timeout(1000)
            page.locator('#form1Button').click()
            try:
                page.wait_for_load_state('networkidle', timeout=20000)
            except Exception:
                pass
            current_url = page.url
            log.info(f'[Login] URL sau reset + dang nhap: {current_url}')

    # ── OTP 2FA ───────────────────────────────────────────────────────────────
    otp_selectors = [
        '[name="otp"]', '[name="sms_code"]',
        '[name="verificationCode"]', '#otp', 'input[maxlength="6"]',
    ]
    if any(page.query_selector(s) for s in otp_selectors):
        log.info('[Login] OTP 2FA required...')
        otp = _request_otp(account, 'Nhap ma OTP 6 chu so gui qua email:')
        for sel in otp_selectors:
            if page.query_selector(sel):
                page.locator(sel).fill(otp)
                break
        page.keyboard.press('Enter')
        try:
            page.wait_for_load_state('networkidle', timeout=20000)
        except Exception:
            pass
        current_url = page.url

    # ── Kiem tra ket qua cuoi ─────────────────────────────────────────────────
    if 'login' in current_url.lower():
        err_text = ''
        try:
            err_text = page.locator(
                '.error, .alert, [class*="error"], [class*="alert"],'
                '.form-group-error, #errorcommon, #erroLock'
            ).first.inner_text(timeout=2000).strip()
        except Exception:
            pass
        raise Exception(
            f'Dang nhap that bai. Loi trang: {err_text}' if err_text
            else 'Dang nhap that bai - van o trang login'
        )

    log.info(f'[Login] Dang nhap thanh cong! URL: {current_url}')

    # Chuyen ve trang chu va cho
    log.info('[Login] Chuyen ve trang chu...')
    try:
        page.goto(SITE_URL, wait_until='networkidle', timeout=20000)
        page.wait_for_timeout(1000)
    except Exception:
        pass
    log.info(f'[Login] Dang o trang chu: {page.url}')


# ─────────────────────────────────────────────────────────────────────────────
# Session helpers (luu / tai cookies de dang nhap khong can form)
# ─────────────────────────────────────────────────────────────────────────────
def _session_path(email: str) -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    tag = email.replace('@', '_at_').replace('.', '_')
    return os.path.join(SESSIONS_DIR, f'{tag}.json')


def task_save_session(page, context, account):
    """
    Luu cookies hien tai vao sessions/<email>.json.
    Goi ngay sau khi dang ky / dang nhap thanh cong.
    """
    path    = _session_path(account['email'])
    cookies = context.cookies()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    log.info(f'[Session] Da luu {len(cookies)} cookies -> {path}')


def task_login_via_session(page, context, account):
    """
    Dang nhap bang cookies da luu (khong can form, khong can reset mat khau).
    Raise Exception neu session het han hoac chua co file.
    """
    path = _session_path(account['email'])
    if not os.path.exists(path):
        raise Exception(f'Chua co session file: {path}')

    with open(path, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    context.add_cookies(cookies)
    log.info(f'[Session] Da load {len(cookies)} cookies cho {account["email"]}')

    # Vao thang trang chu
    page.goto(SITE_URL, wait_until='networkidle', timeout=20000)
    page.wait_for_timeout(1000)

    # Chi fail neu bi redirect ve trang login (session het han)
    if 'login' in page.url.lower():
        os.remove(path)
        raise Exception('Session het han, se thu dang nhap bang form.')

    log.info(f'[Session] Dang nhap thanh cong qua cookies! Dang o trang chu: {page.url}')


# ─────────────────────────────────────────────────────────────────────────────
# Task: Dung URL co san (da nhap truoc), bo qua buoc gui email
# ─────────────────────────────────────────────────────────────────────────────
def task_use_preset_url(page, context, account):
    """
    Lay URL dang ky da duoc nhap san tu account['reg_url'].
    Dat vao account['activation_link'] de task_fill_regform su dung.
    """
    url = account.get('reg_url', '').strip()
    if not url:
        raise Exception('Tai khoan nay chua co URL dang ky. Hay nhap URL truoc khi chay.')
    account['activation_link'] = url
    log.info(f'[1] Su dung URL co san: {url}')


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

# Khi da co san tat ca URL (nhanh nhat, hoan toan tu dong)
PIPELINE_URL_ONLY = [
    task_use_preset_url,   # doc URL tu account['reg_url']
    task_fill_regform,     # mo URL, dien form, submit
    task_save_session,     # luu cookies ngay sau dang ky thanh cong
]

# Lan dau chay: dung pipeline nay de lay selector form
PIPELINE_INSPECT = [
    task_submit_email,
    task_get_email_link,
    task_inspect_regform,   # <- xem regform_dump.txt + regform_screenshot.png
]

# Khi bot tu gui email va doi link qua GUI
PIPELINE_REGISTER = [
    task_submit_email,
    task_get_email_link,
    task_fill_regform,
]

# Chi dang nhap (tai khoan da dang ky thanh cong)
PIPELINE_LOGIN = [
    task_login_pokecen,
]

# Dang nhap thong minh: thu cookies truoc, neu het han moi dung form
PIPELINE_LOGIN_SMART = [
    task_login_via_session,   # thu cookies da luu
]

# Inspect trang login de lay selector (chay 1 lan)
PIPELINE_INSPECT_LOGIN = [
    task_inspect_login_page,
]
