"""
tasks_rakuten.py -- Pipeline dat hang tu dong tren rakuten.co.jp

Luong thuong:
  1. task_login        : Dang nhap tai khoan Rakuten
  2. task_find_product : Tim san pham theo URL hoac keyword
  3. task_add_to_cart  : Them vao gio hang
  4. task_checkout     : Tien hanh thanh toan, xac nhan dia chi
  5. task_place_order  : Xac nhan dat hang cuoi cung

Luong Sniper (dat hang som nhat / flash sale):
  1. task_login
  2. task_find_product
  3. task_monitor_and_snipe  <- Theo doi trang + dem nguoc den gio mo ban
  4. task_checkout
  5. task_place_order
"""

import logging
import time
from datetime import datetime

log = logging.getLogger(__name__)

# Trang chu chinh thuc: https://www.rakuten.co.jp/ (Rakuten Ichiba)
RAKUTEN_TOP = 'https://www.rakuten.co.jp/'
# SSO moi (2025+): /myrakuten/login/ thuong tra trang loi + redirect — dung authorize
RAKUTEN_LOGIN = (
    'https://login.account.rakuten.com/sso/authorize?'
    'client_id=rakuten_ichiba_top_web&service_id=s245&response_type=code&'
    'scope=openid&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F'
)
RAKUTEN_SEARCH = 'https://search.rakuten.co.jp/search/mall/{keyword}/'
CART_URL      = 'https://basket.rakuten.co.jp/'


# ─────────────────────────────────────────────────────────────────────────────
# Helper: OTP / 2FA
# ─────────────────────────────────────────────────────────────────────────────
def _request_otp(account, prompt):
    req_q = account.get('otp_req_q')
    res_q = account.get('otp_res_q')
    if req_q and res_q:
        req_q.put({'email': account.get('rakuten_id', ''), 'prompt': prompt})
        return res_q.get(timeout=180)
    return ''


def _js_fill(page, selector, value):
    """Dien gia tri va trigger input/change/blur events."""
    if not value:
        return
    try:
        page.evaluate(f"""
            (function() {{
                var el = document.querySelector('{selector}');
                if (!el) return;
                var setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, {repr(value)});
                el.dispatchEvent(new Event('input',  {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                el.dispatchEvent(new Event('blur',   {{bubbles: true}}));
            }})();
        """)
    except Exception as e:
        log.warning(f'js_fill failed {selector}: {e}')


# ─────────────────────────────────────────────────────────────────────────────
# Task 1: Dang nhap Rakuten
# ─────────────────────────────────────────────────────────────────────────────
def task_login(page, context, account):
    rakuten_id  = account.get('rakuten_id', '')
    rakuten_pwd = account.get('rakuten_password', '')
    if not rakuten_id or not rakuten_pwd:
        raise Exception('Chua co tai khoan Rakuten (rakuten_id / rakuten_password)')

    log.info(f'[1] Dang nhap Rakuten: {rakuten_id}')
    page.goto(RAKUTEN_LOGIN, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(2000)

    # Dien ID / email (SSO login.account.rakuten.com + form cu)
    user_sels = [
        '#loginInner_u', 'input[name="u"]',
        'input[type="email"]', 'input[name="username"]', 'input[name="userId"]',
        '#user_id', 'input[autocomplete="username"]', 'input[name="email"]',
    ]
    for sel in user_sels:
        if page.query_selector(sel):
            _js_fill(page, sel, rakuten_id)
            break

    # Dien mat khau
    pwd_sels = [
        '#loginInner_p', 'input[name="p"]', 'input[type="password"]',
        'input[autocomplete="current-password"]', 'input[name="password"]',
    ]
    for sel in pwd_sels:
        if page.query_selector(sel):
            _js_fill(page, sel, rakuten_pwd)
            break

    # Click dang nhap
    clicked = False
    for sel in [
        '#loginInner_submit', 'button[type="submit"]', 'input[type="submit"]',
        'button:has-text("ログイン")', 'button:has-text("次へ")',
    ]:
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.click()
            clicked = True
            break
    if not clicked:
        page.keyboard.press('Enter')

    page.wait_for_load_state('domcontentloaded', timeout=20000)
    page.wait_for_timeout(2000)

    # Kiem tra 2FA
    if page.query_selector('[class*="oneTimePassword"], [id*="oneTimePassword"], input[name="otp"]'):
        log.info('[1] 2FA detected! Doi OTP...')
        otp = _request_otp(account, 'Nhap ma OTP Rakuten (SMS/Email):')
        if otp:
            for sel in ['input[name="otp"]', '#oneTimePasswordInput', 'input[maxlength="6"]']:
                if page.query_selector(sel):
                    _js_fill(page, sel, otp)
                    break
            for sel in ['button[type="submit"]', 'input[type="submit"]']:
                el = page.query_selector(sel)
                if el:
                    el.click()
                    break
            page.wait_for_load_state('domcontentloaded', timeout=15000)
            page.wait_for_timeout(1500)

    # Kiem tra dang nhap thanh cong
    current = page.url
    if 'login' in current and 'error' in current.lower():
        page.screenshot(path=f'rakuten_login_err_{rakuten_id.split("@")[0]}.png')
        raise Exception(f'Dang nhap Rakuten that bai: {current}')

    log.info(f'[1] Dang nhap thanh cong. URL: {current}')
    account['logged_in'] = True


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Tim san pham (URL truc tiep hoac keyword)
# ─────────────────────────────────────────────────────────────────────────────
def task_find_product(page, context, account):
    product_url = account.get('product_url', '').strip()
    keyword     = account.get('keyword', '').strip()

    if product_url:
        log.info(f'[2] Truy cap URL san pham: {product_url}')
        page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(1500)
    elif keyword:
        log.info(f'[2] Tim kiem: "{keyword}"')
        search_url = RAKUTEN_SEARCH.format(keyword=keyword)
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(1500)

        # Click vao san pham dau tien
        first = None
        for sel in [
            '.search-result-items .item-thumbnail a',
            '.searchresultitems .item-thumbnail-image a',
            'a[data-ratid]',
            '.item-card__image a',
            '.searchresultitem a.image',
        ]:
            first = page.query_selector(sel)
            if first:
                break

        if not first:
            # Fallback: tim link dau tien trong ket qua
            first = page.query_selector('ul.search-result-items li a')

        if not first:
            page.screenshot(path='rakuten_search_no_result.png')
            raise Exception(f'Khong tim thay san pham nao voi keyword: "{keyword}"')

        href = first.get_attribute('href') or ''
        log.info(f'[2] Chon san pham: {href[:80]}')
        first.click()
        page.wait_for_load_state('domcontentloaded', timeout=20000)
        page.wait_for_timeout(1500)
    else:
        raise Exception('Chua co product_url va keyword. Hay nhap it nhat mot trong hai.')

    account['product_page_url'] = page.url
    log.info(f'[2] Trang san pham: {page.url[:80]}')


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: Them vao gio hang
# ─────────────────────────────────────────────────────────────────────────────
def task_add_to_cart(page, context, account):
    log.info('[3] Them vao gio hang...')

    # Chon bien the (kich co, mau sac) tu dong: chon option dau tien cua moi <select>
    if account.get('auto_select_variant', True):
        selects = page.query_selector_all('select')
        for sel_el in selects:
            try:
                options = sel_el.query_selector_all('option')
                valid = [o for o in options if o.get_attribute('value') and o.get_attribute('value') != '']
                if valid:
                    val = valid[0].get_attribute('value')
                    sel_el.select_option(val)
                    page.wait_for_timeout(500)
                    log.info(f'[3]   Chon bien the: {val}')
            except Exception as e:
                log.warning(f'[3]   Khong the chon bien the: {e}')

    # Dat so luong
    quantity = str(account.get('quantity', 1))
    for sel in ['input[name="quantity"]', '#quantity', 'input[name="count"]', 'select[name="quantity"]']:
        el = page.query_selector(sel)
        if el:
            tag = el.evaluate('el => el.tagName').lower()
            if tag == 'select':
                try: el.select_option(quantity)
                except Exception: pass
            else:
                _js_fill(page, sel, quantity)
            log.info(f'[3]   So luong: {quantity}')
            break

    # Click them vao gio hang
    added = False
    for sel in [
        'input[type="submit"][value*="カートに入れる"]',
        'input[type="submit"][value*="買い物かごに入れる"]',
        'button:has-text("カートに入れる")',
        'button:has-text("買い物かごに入れる")',
        '#addToCart',
        '.add-to-cart',
        'input.add_cart_button',
        'input[name="add_to_cart"]',
    ]:
        el = page.query_selector(sel)
        if el:
            el.click()
            log.info(f'[3]   Click: {sel}')
            added = True
            break

    if not added:
        # Fallback: tim tat ca nut submit va click cai co text phu hop
        for el in page.query_selector_all('input[type="submit"], button[type="submit"]'):
            text = (el.get_attribute('value') or el.inner_text() or '').strip()
            if 'カート' in text or '買い物かご' in text or 'cart' in text.lower():
                el.click()
                added = True
                log.info(f'[3]   Click fallback: {text}')
                break

    if not added:
        page.screenshot(path='rakuten_no_cart_btn.png')
        raise Exception('Khong tim thay nut "Them vao gio hang". Kiem tra rakuten_no_cart_btn.png')

    page.wait_for_load_state('domcontentloaded', timeout=15000)
    page.wait_for_timeout(2000)
    log.info(f'[3] Them vao gio hang thanh cong. URL: {page.url[:80]}')


# ─────────────────────────────────────────────────────────────────────────────
# Task 4: Tien hanh thanh toan, xac nhan dia chi
# ─────────────────────────────────────────────────────────────────────────────
def task_checkout(page, context, account):
    log.info('[4] Tien hanh thanh toan...')

    # Vao gio hang neu chua o do
    if 'basket' not in page.url and 'cart' not in page.url:
        page.goto(CART_URL, wait_until='domcontentloaded', timeout=20000)
        page.wait_for_timeout(1500)

    # Click "ご注文手続きへ" / "proceed to checkout"
    proceeded = False
    for sel in [
        'a:has-text("ご注文手続きへ")',
        'input[value*="ご注文手続き"]',
        'button:has-text("ご注文手続き")',
        'a:has-text("購入手続きへ")',
        'input[value*="購入手続き"]',
        '.checkout-btn',
        'a[href*="order"]',
    ]:
        el = page.query_selector(sel)
        if el:
            el.click()
            proceeded = True
            log.info(f'[4]   Click checkout: {sel}')
            break

    if not proceeded:
        page.screenshot(path='rakuten_no_checkout_btn.png')
        raise Exception('Khong tim thay nut thanh toan. Kiem tra rakuten_no_checkout_btn.png')

    page.wait_for_load_state('domcontentloaded', timeout=20000)
    page.wait_for_timeout(2000)

    # Phuong thuc thanh toan: dung the da luu san
    # Rakuten thong thuong tu chon phuong thuc da luu - khong can lam gi them
    # Neu can chon, tim option "クレジットカード"
    for sel in [
        'input[value*="credit"]',
        'input[id*="credit"]',
        'label:has-text("クレジットカード") input',
        'input[name*="payment"][value*="1"]',
    ]:
        el = page.query_selector(sel)
        if el and not el.is_checked():
            try:
                el.check()
                log.info(f'[4]   Chon thanh toan the tin dung: {sel}')
                page.wait_for_timeout(500)
                break
            except Exception:
                pass

    log.info(f'[4] Trang thanh toan: {page.url[:80]}')
    account['checkout_url'] = page.url


# ─────────────────────────────────────────────────────────────────────────────
# Task 5: Xac nhan dat hang cuoi cung
# ─────────────────────────────────────────────────────────────────────────────
def task_place_order(page, context, account):
    log.info('[5] Xac nhan dat hang...')

    # Chup anh trang xac nhan truoc khi bam
    page.screenshot(path=f'rakuten_confirm_{account.get("rakuten_id","").split("@")[0]}.png')

    # Tim nut xac nhan cuoi cung
    placed = False
    for sel in [
        'button:has-text("注文を確定する")',
        'input[value*="注文を確定する"]',
        'button:has-text("購入を確定する")',
        'input[value*="購入を確定"]',
        'input[value*="注文確定"]',
        'button[type="submit"]:has-text("確定")',
        '#orderSubmitButton',
        '.order-confirm-btn',
    ]:
        el = page.query_selector(sel)
        if el:
            el.click()
            placed = True
            log.info(f'[5]   Click xac nhan: {sel}')
            break

    if not placed:
        page.screenshot(path='rakuten_no_confirm_btn.png')
        raise Exception('Khong tim thay nut xac nhan dat hang. Kiem tra rakuten_no_confirm_btn.png')

    try:
        page.wait_for_load_state('domcontentloaded', timeout=25000)
        page.wait_for_timeout(3000)
    except Exception:
        pass

    log.info(f'[5] URL sau dat hang: {page.url[:80]}')

    # Doc so don hang neu co
    order_id = ''
    for sel in [
        '[class*="orderNumber"]', '[class*="order-number"]',
        '[id*="orderNumber"]', '.order_number',
    ]:
        el = page.query_selector(sel)
        if el:
            order_id = el.inner_text().strip()
            break

    if order_id:
        log.info(f'[5] So don hang: {order_id}')
        account['order_id'] = order_id
    else:
        log.info('[5] Dat hang hoan tat (khong doc duoc so don hang).')

    # Kiem tra co loi khong
    error_els = page.query_selector_all('[class*="error"], [class*="Error"]')
    errors = [e.inner_text().strip() for e in error_els if e.inner_text().strip()]
    if errors:
        raise Exception(f'Loi khi dat hang: {"; ".join(errors[:3])}')

    account['order_placed'] = True


# ─────────────────────────────────────────────────────────────────────────────
# Task SNIPER  (sub-1s engine)
#
# Kien truc:
#   Phase 1 (Python)  : Reload trang dinh ky cho den T-10s
#   Phase 2 (JS)      : Inject JavaScript vao browser, JS tu:
#                         - Dat setTimeout chinh xac den ms
#                         - Gan MutationObserver theo doi DOM
#                         - Click nut "Them vao gio hang" ngay khi active
#                       Khong co roundtrip Python→CDP khi click
#   Phase 3 (Python)  : Poll window.__snipeResult moi 50ms de biet ket qua
#
# Toc do thuc te click: < 50ms tu khi nut xuat hien / den gio
# ─────────────────────────────────────────────────────────────────────────────

# CSS selectors cho nut cart (dung ca trong Python lan JS)
_CART_CSS = [
    'input[type="submit"][value*="カートに入れる"]',
    'input[type="submit"][value*="買い物かごに入れる"]',
    '#addToCart',
    '.add-to-cart',
    'input.add_cart_button',
    'input[name="add_to_cart"]',
    'button[id*="cart"]',
    'input[id*="cart"]',
]

_SOLDOUT_CSS = [
    '[class*="soldout"]', '[class*="sold-out"]', '[class*="outofstock"]',
    '.item_soldout', 'img[alt*="売り切れ"]', 'img[alt*="SOLD OUT"]',
]


def _is_cart_active_py(page):
    """Kiem tra nhanh bang Python (dung truoc khi inject JS)."""
    for sel in _CART_CSS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                if el.get_attribute('disabled') is None:
                    cls = el.get_attribute('class') or ''
                    if 'disabled' not in cls.lower():
                        return True
        except Exception:
            pass
    return False


def _build_sniper_js(target_epoch_ms: float) -> str:
    """
    Tao doan JS inject vao trang.
    target_epoch_ms: thoi diem mo ban tinh bang epoch milliseconds.
                     Neu = 0 thi chi dung MutationObserver (monitor mode).
    """
    selectors_js = str(_CART_CSS)           # list -> JS array string
    return f"""
(function() {{
    if (window.__snipeInjected) return;
    window.__snipeInjected = true;
    window.__snipeResult   = null;   // null | 'clicked' | 'error'
    window.__snipeClickedAt = null;

    var TARGET_MS   = {target_epoch_ms:.0f};
    var SELECTORS   = {selectors_js};
    var RETRY_LIMIT = 200;           // toi da 200 lan retry (10s)
    var retryCount  = 0;

    function findActiveBtn() {{
        for (var i = 0; i < SELECTORS.length; i++) {{
            var els = document.querySelectorAll(SELECTORS[i]);
            for (var j = 0; j < els.length; j++) {{
                var el = els[j];
                if (!el) continue;
                if (el.disabled) continue;
                var cls = (el.className || '').toLowerCase();
                if (cls.indexOf('disabled') !== -1) continue;
                var rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                return el;
            }}
        }}
        return null;
    }}

    function doClick() {{
        if (window.__snipeResult === 'clicked') return true;
        var btn = findActiveBtn();
        if (btn) {{
            var ts = new Date().toISOString();
            try {{ btn.click(); }} catch(e) {{}}
            // Submit form neu button la input[type=submit]
            try {{
                if (btn.form) btn.form.submit();
            }} catch(e) {{}}
            window.__snipeResult    = 'clicked';
            window.__snipeClickedAt = ts;
            console.log('[SNIPE] CLICKED at ' + ts);
            return true;
        }}
        return false;
    }}

    function aggressiveRetry() {{
        if (window.__snipeResult === 'clicked') return;
        if (retryCount++ > RETRY_LIMIT) {{
            window.__snipeResult = 'timeout';
            return;
        }}
        if (!doClick()) {{
            setTimeout(aggressiveRetry, 50);
        }}
    }}

    // ── MutationObserver: phat hien DOM thay doi ──────────────────────────
    var observer = new MutationObserver(function() {{
        if (doClick()) observer.disconnect();
    }});
    observer.observe(document.documentElement, {{
        childList:  true,
        subtree:    true,
        attributes: true,
        attributeFilter: ['disabled', 'class', 'style']
    }});

    // ── Thu click ngay lap tuc (neu nut da co san) ────────────────────────
    if (doClick()) {{ observer.disconnect(); return; }}

    // ── Dat setTimeout chinh xac den millisecond ──────────────────────────
    if (TARGET_MS > 0) {{
        var remaining = TARGET_MS - Date.now();
        console.log('[SNIPE] Scheduled click in ' + remaining + 'ms');

        // T-500ms: bat dau retry nhanh de bom truoc
        setTimeout(function() {{
            aggressiveRetry();
        }}, Math.max(0, remaining - 500));

        // Dung gio: fire chinh xac
        setTimeout(function() {{
            doClick();
            // Van retry them 10s de chac chan
            aggressiveRetry();
        }}, Math.max(0, remaining));
    }} else {{
        // Monitor mode: chi dung observer, retry dinh ky
        aggressiveRetry();
    }}
}})();
"""


def _inject_and_wait(page, target_dt, stop_event, status_cb, timeout_after=30):
    """
    Inject JS sniper vao trang hien tai, roi poll ket qua moi 50ms.
    Tra ve timestamp click (str) neu thanh cong.
    """
    target_ms = target_dt.timestamp() * 1000 if target_dt else 0
    js_code   = _build_sniper_js(target_ms)

    log.info('[SNIPE-JS] Injecting sniper JavaScript...')
    status_cb('JS sniper da inject! Cho nut active...')
    page.evaluate(js_code)

    # Poll Python moi 50ms (chi de biet khi nao JS click xong)
    deadline = time.monotonic() + timeout_after
    last_log = time.monotonic()
    while time.monotonic() < deadline:
        if stop_event and stop_event.is_set():
            raise Exception('Bot da bi dung boi nguoi dung.')

        result = page.evaluate('window.__snipeResult')
        if result == 'clicked':
            ts = page.evaluate('window.__snipeClickedAt') or ''
            log.info(f'[SNIPE-JS] CLICK THANH CONG luc {ts}')
            status_cb(f'CLICK! {ts}')
            return ts
        if result == 'timeout':
            raise Exception('JS sniper: het retry (nut khong xuat hien trong 10s sau gio mo ban)')

        # Log dem nguoc moi 5s
        if target_dt and time.monotonic() - last_log > 5:
            rem = (target_dt - datetime.now()).total_seconds()
            if rem > 0:
                status_cb(f'JS san sang | Con {rem:.1f}s den gio mo ban')
            last_log = time.monotonic()

        time.sleep(0.05)   # 50ms poll

    raise Exception(f'Timeout {timeout_after}s: JS sniper khong bao cao ket qua')


def task_monitor_and_snipe(page, context, account):
    """
    Phase 1: Python reload trang dinh ky (xa gio mo ban).
    Phase 2: Inject JS sniper vao browser (gan gio mo ban / monitor mode).
             JS tu click < 50ms -- khong co Python overhead.
    """
    target_dt    = account.get('target_datetime')
    interval     = int(account.get('monitor_interval', 5))
    stop_event   = account.get('stop_event')
    status_cb    = account.get('status_cb', lambda msg: None)

    log.info('[SNIPE] Khoi dong sniper...')
    if target_dt:
        log.info(f'[SNIPE] Gio mo ban: {target_dt.strftime("%Y-%m-%d %H:%M:%S")}')
        log.info('[SNIPE] Phase 1: Reload dinh ky cho den T-15s, sau do inject JS')
    else:
        log.info('[SNIPE] Monitor mode: inject JS ngay, MutationObserver theo doi DOM')

    iteration = 0

    # ── Phase 1: Python reload cho den T-15s ─────────────────────────────────
    while True:
        if stop_event and stop_event.is_set():
            raise Exception('Bot da bi dung boi nguoi dung.')

        now       = datetime.now()
        remaining = (target_dt - now).total_seconds() if target_dt else None

        # Neu da den luc inject JS -> thoat Phase 1
        if target_dt is None or remaining <= 15:
            break

        # Kiem tra nhanh xem nut da active chua (hang ra som)
        if _is_cart_active_py(page):
            log.info('[SNIPE] Nut active truoc gio! Chuyen sang JS inject ngay.')
            break

        # Quyet dinh thoi gian sleep va co reload hay khong
        if remaining > 120:
            sleep_s = min(interval, remaining - 60)
            status_cb(f'Cho mo ban: con {int(remaining)}s | Reload #{iteration}')
            log.info(f'[SNIPE] Con {remaining:.0f}s. Reload sau {sleep_s:.0f}s.')
            try:
                page.reload(wait_until='domcontentloaded', timeout=15000)
                page.wait_for_timeout(300)
            except Exception as e:
                log.warning(f'[SNIPE] Reload loi: {e}')
            time.sleep(max(1, sleep_s - 1))
        else:
            # T-120s den T-15s: reload moi 5s de dam bao trang moi nhat
            status_cb(f'Gan gio! Con {remaining:.0f}s -- dang chuan bi JS sniper...')
            log.info(f'[SNIPE] Con {remaining:.0f}s. Reload nhanh moi 5s.')
            try:
                page.reload(wait_until='domcontentloaded', timeout=10000)
                page.wait_for_timeout(200)
            except Exception as e:
                log.warning(f'[SNIPE] Reload loi: {e}')
            time.sleep(min(5, max(1, remaining - 15)))

        iteration += 1
        if target_dt is None and iteration > 2880:
            raise Exception('Timeout 4h: san pham chua xuat hien.')

    # ── Phase 2: Inject JS, cho ket qua bang 50ms poll ───────────────────────
    log.info('[SNIPE] Phase 2: Inject JS sniper vao browser...')

    # Tinh timeout: neu co gio mo ban, cho them 15s sau gio; neu khong, cho 2h
    if target_dt:
        remaining_now = max(0, (target_dt - datetime.now()).total_seconds())
        js_timeout    = remaining_now + 15
    else:
        js_timeout    = 7200

    clicked_at = _inject_and_wait(
        page, target_dt, stop_event, status_cb,
        timeout_after=js_timeout)

    account['snipe_triggered_at'] = clicked_at
    log.info(f'[SNIPE] Hoan tat! Click luc {clicked_at}. Chuyen sang add_to_cart.')


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

# Pipeline dat hang binh thuong
PIPELINE_RAKUTEN = [
    task_login,
    task_find_product,
    task_add_to_cart,
    task_checkout,
    task_place_order,
]

# Pipeline sniper: theo doi + dat hang ngay khi den gio / hang xuat hien
PIPELINE_RAKUTEN_SNIPE = [
    task_login,
    task_find_product,
    task_monitor_and_snipe,  # <-- cho den gio / phat hien hang
    task_add_to_cart,
    task_checkout,
    task_place_order,
]
