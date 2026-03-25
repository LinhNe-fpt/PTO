"""
tasks_rakuten_reg.py
Core logic dang ky tai khoan Rakuten SSO tu dong.
Duoc import boi ca inspect_rakuten_register.py (script) va gui.py (GUI).
"""
import json
import logging
import re
import time
from pathlib import Path
from playwright.sync_api import Page
from playwright_stealth import Stealth
from email_handler import get_rakuten_otp, get_latest_uid

log = logging.getLogger(__name__)

ACCOUNTS_FILE = Path("rakuten_reg_accounts.json")
REGISTER_URL  = (
    "https://login.account.rakuten.com/sso/register"
    "?client_id=rakuten_ichiba_top_web"
    "&service_id=s245"
    "&response_type=code"
    "&scope=openid"
    "&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F"
)
LOGIN_URL     = (
    "https://login.account.rakuten.com/sso/authorize"
    "?client_id=rakuten_ichiba_top_web"
    "&service_id=s245"
    "&response_type=code"
    "&scope=openid"
    "&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F"
)


# ── JSON helpers ──────────────────────────────────────────────────────────────
def load_accounts() -> list[dict]:
    if ACCOUNTS_FILE.exists():
        return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    return []


def save_accounts(data: list[dict]):
    ACCOUNTS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def update_account_status(n: int, status: str, note: str = "", rakuten_id: str = ""):
    """Cap nhat trang thai 1 account trong file JSON."""
    data = load_accounts()
    for acc in data:
        if acc["n"] == n:
            acc["status"] = status
            if note:       acc["note"]       = note
            if rakuten_id: acc["rakuten_id"]  = rakuten_id
    save_accounts(data)


# ── Playwright helpers ────────────────────────────────────────────────────────
def js_fill(page: Page, aria_label: str, value: str) -> bool:
    return bool(page.evaluate(f"""(v) => {{
        const el = Array.from(document.querySelectorAll('input,textarea')).find(
            e => e.getAttribute('aria-label') === '{aria_label}'
              || e.getAttribute('placeholder') === '{aria_label}'
        );
        if (!el) return false;
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
        setter.call(el, v);
        el.dispatchEvent(new Event('input',  {{bubbles: true}}));
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        return true;
    }}""", value))


def click_cta(page: Page, text: str) -> bool:
    try:
        for cta in page.query_selector_all('#cta'):
            if text in (cta.inner_text() or "") and cta.is_visible():
                cta.click()
                return True
        loc = page.locator(f'[role="button"]:has-text("{text}")')
        if loc.count() > 0:
            loc.first.click()
            return True
    except Exception as e:
        log.warning(f"click_cta({text!r}): {e}")
    return False


def safe_wait(page: Page, ms: int):
    try:
        page.wait_for_timeout(ms)
    except Exception:
        pass


def safe_shot(page: Page, path: str):
    try:
        page.screenshot(path=path, full_page=True)
    except Exception:
        pass


def _page_text(page: Page) -> str:
    try:
        body = page.evaluate("() => document.body.innerText") or ""
        return " ".join(l.strip() for l in body.splitlines() if l.strip())[:200]
    except Exception:
        return ""


# ── Core registration flow ────────────────────────────────────────────────────
def register_one(acc: dict, browser,
                 status_cb=None,
                 stop_check=None) -> tuple[bool, str]:
    """
    Dang ky 1 account Rakuten.

    Args:
        acc:       Dict account tu rakuten_reg_accounts.json
        browser:   Playwright browser instance (da mo san)
        status_cb: Callback(msg: str) de update trang thai len GUI (optional)
        stop_check: Callable() -> bool; tra True neu can dung (optional)

    Returns:
        (success: bool, note: str)
    """
    def _cb(msg: str):
        log.info(msg)
        if status_cb:
            status_cb(msg)

    def _stopped() -> bool:
        return stop_check() if stop_check else False

    email_addr = acc["email"]
    email_pass = acc["email_pass"]
    password   = acc["password"]
    n          = acc["n"]
    base_email = (email_addr.split("+")[0] + "@gmail.com"
                  if "+" in email_addr else email_addr)

    _cb(f"[#{n:03d}] Bat dau: {email_addr}")

    ctx  = browser.new_context(
        locale="ja-JP", timezone_id="Asia/Tokyo",
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)

    try:
        if _stopped(): return False, "Da dung"

        # ── B1: Nhap email ────────────────────────────────────────────────
        _cb(f"[#{n:03d}] Mo trang dang ky...")
        page.goto(REGISTER_URL, wait_until="networkidle", timeout=45000)
        safe_wait(page, 2500)

        if not js_fill(page, "メールアドレス", email_addr):
            return False, "Khong tim thay input email"

        safe_wait(page, 500)

        # Lay UID truoc khi gui OTP de tranh doc OTP cu
        since_uid = get_latest_uid(base_email, email_pass)
        log.info(f"[#{n:03d}] since_uid={since_uid} (chi lay mail moi hon)")

        _cb(f"[#{n:03d}] Gui OTP...")
        click_cta(page, "認証コードを送信する")
        safe_shot(page, f"raku_{n:03d}_01.png")

        # Cho trang chuyen sang buoc 2 hoac cao hon, toi da 15s
        _cb(f"[#{n:03d}] Cho trang chuyen sang buoc OTP...")
        try:
            page.wait_for_function(
                """() => location.hash.includes('/registration/2')
                      || location.hash.includes('/registration/3')
                      || location.hash.includes('/registration/4')""",
                timeout=15000
            )
            _cb(f"[#{n:03d}] Da chuyen sang buoc tiep: {page.url[-30:]}")
        except Exception:
            safe_wait(page, 2000)

        safe_shot(page, f"raku_{n:03d}_01b.png")
        log.info(f"[#{n:03d}] URL sau Gui OTP: {page.url}")

        # ── Xu ly CAPTCHA neu trang van o buoc 1 ────────────────────────────────
        from captcha_solver import _get_captcha_bytes, _fill_captcha_input
        from vision_captcha import solve_captcha_vision, has_vision_config

        def _past_step1() -> bool:
            """Tra ve True neu trang da vuot qua buoc 1 (email + CAPTCHA)."""
            url = page.url
            return ("registration/2" in url or "registration/3" in url
                    or "registration/4" in url or "registration/5" in url)

        if not _past_step1():
            captcha_bytes = _get_captcha_bytes(page)
            captcha_text = None
            if captcha_bytes and has_vision_config():
                _cb(f"[#{n:03d}] Thu Vision AI giai CAPTCHA...")
                captcha_text = solve_captcha_vision(captcha_bytes)
                if captcha_text:
                    _cb(f"[#{n:03d}] Vision AI: '{captcha_text}'")

            if captcha_text:
                filled = False
                if captcha_bytes:
                    filled = _fill_captcha_input(page, captcha_text)
                if not filled:
                    try:
                        loc = page.locator('input[aria-label*="文字"]')
                        if loc.count() == 0:
                            loc = page.locator(
                                'input:not([type=email]):not([type=password]):not([type=hidden]):visible'
                            )
                        if loc.count() > 0:
                            loc.last.click()
                            loc.last.fill(captcha_text)
                            filled = True
                    except Exception as _e:
                        log.debug(f"  CAPTCHA fill: {_e}")
                if filled:
                    safe_wait(page, 300)
                    click_cta(page, "認証コードを送信する")
                    try:
                        page.wait_for_function(
                            """() => location.hash.includes('/registration/2')
                                  || location.hash.includes('/registration/3')
                                  || location.hash.includes('/registration/4')""",
                            timeout=12000,
                        )
                        _cb(f"[#{n:03d}] Vision AI + Gui OTP thanh cong.")
                    except Exception:
                        safe_wait(page, 2000)

            if not _past_step1():
                safe_shot(page, f"raku_{n:03d}_captcha_wait.png")
                _cb(
                    f"[#{n:03d}] Hay NHAP CAPTCHA trong browser, roi bam "
                    f"'Gui OTP'. Bot se tu dong tiep tuc — KHONG can go terminal."
                )
                _deadline = time.monotonic() + 600.0  # 10 phut
                while not _past_step1():
                    if _stopped():
                        return False, "Da dung"
                    if time.monotonic() > _deadline:
                        return False, "Het thoi gian cho CAPTCHA (10 phut)"
                    safe_wait(page, 700)
                _cb(f"[#{n:03d}] Da vuot buoc email/CAPTCHA, tiep tuc...")

        if not _past_step1():
            return False, f"Khong vuot qua buoc email/CAPTCHA. URL={page.url[-60:]}"

        if _stopped(): return False, "Da dung"

        # ── B2: Doc OTP tu Gmail (chi neu con o buoc 2) ───────────────────
        # Neu trang da o registration/3 tro len, Rakuten da xac nhan OTP roi (skip)
        if "registration/2" in page.url:
            # Cap nhat since_uid sau khi CAPTCHA xong de chi lay OTP moi nhat
            new_uid = get_latest_uid(base_email, email_pass)
            if new_uid > since_uid:
                log.info(f"[#{n:03d}] Cap nhat since_uid: {since_uid} -> {new_uid}")
                since_uid = new_uid

            _cb(f"[#{n:03d}] Doc OTP tu Gmail (since_uid={since_uid})...")
            otp = get_rakuten_otp(
                email_address=base_email,
                password=email_pass,
                target_alias=email_addr,
                retries=18,
                wait=10,
                since_uid=since_uid,
            )

            if not otp:
                safe_shot(page, f"raku_{n:03d}_otp_fail.png")
                return False, "Khong lay duoc OTP"

            _cb(f"[#{n:03d}] OTP: {otp}")
            safe_shot(page, f"raku_{n:03d}_02_otp_page.png")
            log.info(f"[#{n:03d}] OTP page URL: {page.url}")
            safe_wait(page, 800)

        # Fill OTP chi khi con o buoc 2
        if "registration/2" in page.url:
            otp_filled = False
            for otp_label in ["認証コード", "確認コード", "ワンタイムパスワード", "コード"]:
                try:
                    loc = page.locator(f'input[aria-label*="{otp_label}"]')
                    if loc.count() > 0:
                        loc.first.click(); loc.first.fill(otp)
                        otp_filled = True
                        log.info(f"  OTP filled via aria*='{otp_label}'")
                        break
                except Exception as e:
                    log.debug(f"  '{otp_label}': {e}")

            if not otp_filled:
                for sel in ['input[type=number]', 'input[inputmode="numeric"]',
                            'input[autocomplete="one-time-code"]', 'input[maxlength="6"]']:
                    try:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            loc.first.click(); loc.first.fill(otp)
                            otp_filled = True
                            log.info(f"  OTP filled via '{sel}'")
                            break
                    except Exception as e:
                        log.debug(f"  '{sel}': {e}")

            if not otp_filled:
                try:
                    els = page.query_selector_all(
                        'input:not([type=email]):not([type=password]):not([type=hidden])')
                    for el in els:
                        if el.is_visible():
                            el.click(); el.fill(otp)
                            otp_filled = True
                            log.info("  OTP filled via visible fallback")
                            break
                except Exception as e:
                    log.debug(f"  visible fallback: {e}")

            if not otp_filled:
                return False, "Khong tim thay input OTP"

            safe_wait(page, 500)
            _cb(f"[#{n:03d}] Xac thuc OTP...")
            click_cta(page, "認証する")
            safe_wait(page, 5000)
            safe_shot(page, f"raku_{n:03d}_02.png")

            if "registration/2" in page.url:
                txt = _page_text(page)
                return False, f"Sai OTP hoac het han: {txt[:80]}"
        else:
            _cb(f"[#{n:03d}] Da qua buoc OTP, trang: {page.url[-30:]}")

        if _stopped(): return False, "Da dung"

        # ── B3: Dien form thong tin ca nhan ──────────────────────────────
        # Form Rakuten chi co: password, ho ten kanji, ho ten katakana
        # (KHONG co ngay sinh / SDT / gioi tinh o buoc nay)
        _cb(f"[#{n:03d}] Dien form thong tin...")
        safe_wait(page, 2000)

        def fill(lbl, val):
            """
            Thu nhieu cach fill (React-safe):
            1. page.get_by_label (khop label HTML, aria-label, placeholder)
            2. locator aria-label contains
            3. js_fill fallback
            """
            # 1. Playwright get_by_label - nhat quan voi React
            try:
                loc = page.get_by_label(lbl)
                if loc.count() > 0:
                    loc.first.click()
                    loc.first.fill(val)
                    log.info(f"  fill [{lbl}] via get_by_label OK")
                    return True
            except Exception as e:
                log.debug(f"  get_by_label [{lbl}]: {e}")
            # 2. aria-label contains (partial match)
            try:
                loc = page.locator(f'input[aria-label*="{lbl}"]')
                if loc.count() > 0:
                    loc.first.click()
                    loc.first.fill(val)
                    log.info(f"  fill [{lbl}] via aria*= OK")
                    return True
            except Exception as e:
                log.debug(f"  aria*= [{lbl}]: {e}")
            # 3. placeholder contains
            try:
                loc = page.locator(f'input[placeholder*="{lbl}"]')
                if loc.count() > 0:
                    loc.first.click()
                    loc.first.fill(val)
                    log.info(f"  fill [{lbl}] via placeholder*= OK")
                    return True
            except Exception as e:
                log.debug(f"  placeholder*= [{lbl}]: {e}")
            # 4. js_fill (fallback)
            r = js_fill(page, lbl, val)
            log.info(f"  fill [{lbl}] = {val!r} -> js_fill={r}")
            return r

        # Password: dung Playwright native fill (chinh xac nhat voi React forms)
        def fill_password(aria: str, val: str) -> bool:
            try:
                # Tim theo aria-label (Playwright locator)
                loc = page.locator(f'input[type=password][aria-label="{aria}"]')
                if loc.count() > 0:
                    loc.first.click()
                    loc.first.fill(val)
                    return True
                # Fallback: tat ca input[type=password] theo thu tu
                els = page.query_selector_all('input[type=password]')
                if els:
                    idx = 0 if aria == "パスワード" else 1
                    if idx < len(els):
                        els[idx].click()
                        els[idx].fill(val)
                        return True
            except Exception as e:
                log.debug(f"  fill_password({aria}) error: {e}")
            return False

        # Dump inputs de debug
        inputs_info = page.evaluate("""() =>
            Array.from(document.querySelectorAll('input,textarea')).map(el => ({
                type: el.type,
                aria: el.getAttribute('aria-label') || '',
                placeholder: el.placeholder || '',
                name: el.name || '',
                id: el.id || ''
            }))
        """)
        log.info(f"  [B3] Inputs tren trang: {inputs_info}")

        # ── Generate Rakuten ID (neu chua co) ──────────────────────────────
        import hashlib
        rakuten_id = acc.get("rakuten_id", "")
        if not rakuten_id:
            # Tao ID: "pto" + n zfill(4) + 4 ky tu tu hash email
            h = hashlib.md5(email_addr.encode()).hexdigest()[:4]
            rakuten_id = f"pto{n:04d}{h}"
            # Luu vao account
            update_account_status(n, acc["status"], rakuten_id=rakuten_id)
            acc["rakuten_id"] = rakuten_id
            log.info(f"  Generated rakuten_id: {rakuten_id}")

        # ── Fill Rakuten ID (dung name='username' la chinh xac nhat) ────────
        rid_filled = False
        # 1. name=username (nhanh nhat, khong phu thuoc label encoding)
        try:
            loc = page.locator('input[name="username"]')
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click()
                loc.first.fill(rakuten_id)
                rid_filled = True
                log.info(f"  rakuten_id filled via name=username")
        except Exception as e:
            log.debug(f"  name=username: {e}")
        # 2. aria-label contains "ID" 
        if not rid_filled:
            try:
                loc = page.locator('input[aria-label*="ID"]:visible')
                if loc.count() > 0:
                    loc.first.click()
                    loc.first.fill(rakuten_id)
                    rid_filled = True
                    log.info("  rakuten_id filled via aria*=ID")
            except Exception as e:
                log.debug(f"  aria*=ID: {e}")
        log.info(f"  rakuten_id='{rakuten_id}' filled={rid_filled}")

        r1 = fill_password("パスワード",      password)
        r2 = fill_password("パスワード再入力", password)
        log.info(f"  password={r1} confirm={r2}")
        safe_wait(page, 400)

        fill("姓（漢字）",    acc["last_kanji"])
        fill("名（漢字）",    acc["first_kanji"])
        fill("姓（カタカナ）", acc["last_kana"])
        fill("名（カタカナ）", acc["first_kana"])
        safe_wait(page, 500)
        safe_shot(page, f"raku_{n:03d}_03_form.png")

        if _stopped(): return False, "Da dung"

        # ── B4: Click "Xac nhan tien hanh" (Confirm / 確認に進む) ─────────
        _cb(f"[#{n:03d}] Click 'Xac nhan tien hanh'...")
        clicked = click_cta(page, "確認に進む")
        if not clicked:
            clicked = click_cta(page, "確認") or click_cta(page, "次へ")
        safe_wait(page, 5000)
        safe_shot(page, f"raku_{n:03d}_04_confirm_page.png")

        confirm_url  = page.url
        confirm_text = _page_text(page)
        log.info(f"[#{n:03d}] Confirm URL: {confirm_url}")

        # Trang xac nhan (registration/3/confirm) - can click nut cuoi
        if "registration/3/confirm" in confirm_url or "confirm" in confirm_url:
            _cb(f"[#{n:03d}] Trang xac nhan! Click nut dang ky cuoi...")
            safe_wait(page, 1000)

            # Dump cac nut tren trang confirm
            confirm_btns = page.evaluate("""() =>
                Array.from(document.querySelectorAll('[role="button"],button'))
                .map(el=>({
                    id: el.id||'',
                    text: (el.innerText||'').trim().slice(0,60),
                    disabled: el.disabled||false
                }))
            """)
            log.info(f"[#{n:03d}] Confirm buttons: {confirm_btns}")

            # Click nut dang ky cuoi tren trang confirm
            # Nut that su la "会員登録を完了する" (hoan tat dang ky)
            final_clicked = (
                click_cta(page, "会員登録を完了する") or
                click_cta(page, "会員登録する")       or
                click_cta(page, "登録する")            or
                click_cta(page, "確定する")            or
                click_cta(page, "完了する")
            )
            log.info(f"[#{n:03d}] Final button clicked: {final_clicked}")
            safe_wait(page, 10000)
            safe_shot(page, f"raku_{n:03d}_05_final.png")

            final_url  = page.url
            final_text = _page_text(page)
            log.info(f"[#{n:03d}] Final URL: {final_url}")
            log.info(f"[#{n:03d}] Final text (200c): {final_text[:200]}")

            # Thanh cong: redirect khoi login domain, hoac text xac nhan
            login_domain = "login.account.rakuten.com"
            if login_domain not in final_url:
                return True, f"Dang ky thanh cong! URL={final_url[:70]}"
            if any(kw in final_text for kw in ["登録完了", "ありがとう", "ようこそ", "完了しました"]):
                return True, f"Dang ky thanh cong! (text match)"
            # Van con tren login domain - that bai hoac can them buoc
            return False, f"Chua hoan tat. URL={final_url[-60:]}"

        # Neu chua den trang confirm
        return False, f"Chua den confirm. URL={confirm_url[:60]} | {confirm_text[:60]}"

    except Exception as e:
        log.exception(f"[#{n:03d}] Exception: {e}")
        safe_shot(page, f"raku_{n:03d}_err.png")
        return False, str(e)[:120]
    finally:
        try:
            ctx.close()
        except Exception:
            pass


# ── Login verification flow ───────────────────────────────────────────────────
def verify_login_one(acc: dict, browser,
                     status_cb=None,
                     stop_check=None) -> tuple[bool, str]:
    """
    Kiem tra dang nhap 1 account Rakuten da dang ky.
    - Buoc 1: Nhap email/ID -> click 'Next'
    - Buoc 2: Nhap password -> click submit
    - Kiem tra: redirect ve rakuten.co.jp = thanh cong

    Returns: (ok: bool, note: str)
    """
    def _cb(msg: str):
        log.info(msg)
        if status_cb:
            status_cb(msg)

    def _stopped() -> bool:
        return stop_check() if stop_check else False

    email_addr = acc["email"]
    password   = acc["password"]
    n          = acc["n"]

    _cb(f"[#{n:03d}] Kiem tra dang nhap: {email_addr}")

    ctx  = browser.new_context(
        locale="ja-JP", timezone_id="Asia/Tokyo",
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)

    try:
        if _stopped():
            return False, "Da dung"

        # ── Buoc 1: Nhap email ────────────────────────────────────────────
        _cb(f"[#{n:03d}] Mo trang dang nhap...")
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=45000)
        safe_wait(page, 2500)

        if "sign_in" not in page.url and "authorize" not in page.url.lower():
            return False, f"Trang khong phai login: {page.url[:60]}"

        # ── Buoc 1: Nhap email (Rakuten login la 2-buoc: email -> password) ───
        _cb(f"[#{n:03d}] Nhap email...")

        # Dien vao truong email (aria-label hoac input text dau tien)
        email_filled = False
        for aria in ["楽天ID/メールアドレス（必須）", "楽天ID/メールアドレス",
                     "メールアドレス", "ユーザーID", "楽天ID"]:
            if js_fill(page, aria, email_addr):
                email_filled = True
                log.info(f"  email filled via aria='{aria}'")
                break

        if not email_filled:
            filled = page.evaluate(f"""(v) => {{
                const el = document.querySelector('input[type=text],input[type=email]');
                if (!el) return false;
                const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(el, v);
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                return true;
            }}""", email_addr)
            if not filled:
                safe_shot(page, f"raku_{n:03d}_login_noemail.png")
                return False, "Khong tim thay truong email tren trang login"

        safe_wait(page, 400)

        # ── Buoc 2: Click "次" (Next) de qua buoc nhap password ───────────────
        # QUAN TRONG: Chi click cta001 (#次/Next), KHONG click textl_173
        # (textl_173 = "パスワードをお忘れの方" = quen mat khau -> CAPTCHA trang reset!)
        _cb(f"[#{n:03d}] Click Next (buoc 1 - email)...")
        next_clicked = False
        try:
            el = page.query_selector("#cta001")
            if el and el.is_visible():
                el.click()
                next_clicked = True
                log.info("  Clicked #cta001 (Next)")
        except Exception:
            pass
        if not next_clicked:
            try:
                el = page.query_selector("#cta")
                if el and el.is_visible():
                    el.click()
                    next_clicked = True
            except Exception:
                pass
        safe_wait(page, 3000)
        safe_shot(page, f"raku_{n:03d}_login_step2.png")
        log.info(f"[#{n:03d}] After Next click, URL: {page.url}")
        log.info(f"[#{n:03d}] After Next page text: {_page_text(page)[:150]}")

        # Kiem tra neu co nut "パスワードでログイン" tren trang buoc 2
        pw_link_clicked = False
        for btn_text in ["パスワードでログイン", "パスワード認証"]:
            try:
                loc = page.locator(f'text="{btn_text}"')
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    pw_link_clicked = True
                    log.info(f"  Clicked '{btn_text}'")
                    safe_wait(page, 2000)
                    break
            except Exception:
                pass
        # Tim theo contains
        if not pw_link_clicked:
            try:
                loc = page.locator('[id^="textl"]:visible')
                for i in range(loc.count()):
                    el = loc.nth(i)
                    t  = (el.inner_text() or '').strip()
                    if 'パスワード' in t and 'お忘れ' not in t and '再設定' not in t:
                        el.click()
                        pw_link_clicked = True
                        log.info(f"  Clicked password-mode btn: '{t}'")
                        safe_wait(page, 2000)
                        break
            except Exception:
                pass
        if pw_link_clicked:
            safe_wait(page, 1500)
            safe_shot(page, f"raku_{n:03d}_login_pwmode.png")

        if _stopped():
            return False, "Da dung"

        # ── Buoc 3: Nhap password ─────────────────────────────────────────────
        _cb(f"[#{n:03d}] Nhap password...")

        # Dung Playwright native fill (chinh xac hon JS inject voi React forms)
        pwd_filled = False
        try:
            pwd_el = page.query_selector('input[type=password]')
            if pwd_el:
                pwd_el.click()
                pwd_el.fill(password)
                pwd_filled = True
                log.info("  Password filled via Playwright el.fill()")
        except Exception as e:
            log.debug(f"  Playwright fill failed: {e}")

        if not pwd_filled:
            safe_shot(page, f"raku_{n:03d}_login_nopwd.png")
            return False, "Khong tim thay truong password (sau click Next)"

        safe_wait(page, 400)

        # ── Buoc 4: Click Submit login ────────────────────────────────────────
        _cb(f"[#{n:03d}] Click Login...")
        for cta_id in ["cta001", "cta"]:
            try:
                el = page.query_selector(f"#{cta_id}")
                if el and el.is_visible():
                    el.click()
                    log.info(f"  Clicked #{cta_id}")
                    break
            except Exception:
                pass

        safe_wait(page, 10000)
        safe_shot(page, f"raku_{n:03d}_login_result.png")

        final_url  = page.url
        final_text = _page_text(page)
        log.info(f"[#{n:03d}] Login result URL: {final_url}")
        log.info(f"[#{n:03d}] Login result text: {final_text[:100]}")

        # Xu ly CAPTCHA neu xuat hien sau khi submit (chi check sau khi co ket qua)
        from captcha_solver import detect_captcha, solve_captcha_on_page
        if detect_captcha(page):
            _cb(f"[#{n:03d}] CAPTCHA xuat hien sau submit, giai tu dong...")
            safe_shot(page, f"raku_{n:03d}_login_captcha.png")
            captcha_text = solve_captcha_on_page(page)
            if captcha_text:
                for cta_id in ["cta001", "cta"]:
                    try:
                        el = page.query_selector(f"#{cta_id}")
                        if el and el.is_visible():
                            el.click(); break
                    except Exception:
                        pass
                safe_wait(page, 8000)
                final_url  = page.url
                final_text = _page_text(page)

        # Thanh cong: redirect ra ngoai login domain
        login_domain = "login.account.rakuten.com"
        if login_domain not in final_url:
            _cb(f"[#{n:03d}] DANG NHAP THANH CONG -> {final_url[:60]}")
            return True, f"Login OK -> {final_url[:60]}"

        # Kiem tra loi (tranh false positive)
        error_kws = ["エラー", "invalid", "incorrect", "不正", "パスワードが違います",
                     "認証に失敗", "ログインできません"]
        for kw in error_kws:
            if kw in final_text:
                return False, f"Login that bai ({kw}): {final_text[:80]}"

        return False, f"Chua redirect. URL={final_url[-60:]}"

    except Exception as e:
        log.exception(f"[#{n:03d}] verify_login Exception: {e}")
        safe_shot(page, f"raku_{n:03d}_login_err.png")
        return False, str(e)[:120]
    finally:
        try:
            ctx.close()
        except Exception:
            pass
