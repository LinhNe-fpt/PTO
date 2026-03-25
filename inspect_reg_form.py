"""
inspect_reg_form.py
Chay qua toan bo flow dang ky Rakuten + dump chinh xac tat ca truong.
Dung email that de lay OTP that.

Chay: python inspect_reg_form.py
"""
import sys, io, re, json, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import Stealth
from email_handler import get_rakuten_otp, get_latest_uid

EMAIL = "daolinhk18@gmail.com"
PASS  = "qump adnl hcbo ytmo"
OUT   = Path("inspect_reg_form_dump.txt")

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger()

LINES = []
def note(m=''):
    LINES.append(str(m))
    OUT.write_text('\n'.join(LINES), encoding='utf-8')

REGISTER_URL = (
    "https://login.account.rakuten.com/sso/register"
    "?client_id=rakuten_ichiba_top_web&service_id=s245"
    "&response_type=code&scope=openid"
    "&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F"
)

def dump_all_inputs(page: Page, step: str):
    note(); note('='*70)
    note(f'[{step}]'); note(f'URL: {page.url}')

    note('\n--- INPUT ---')
    inputs = page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(el=>({
        type: el.type, name: el.name, id: el.id,
        ariaLabel: el.getAttribute('aria-label')||'',
        placeholder: el.placeholder||'',
        value: el.value||'',
        maxLength: el.maxLength,
        required: el.required
    }))""")
    for inp in inputs:
        note(f"  type={inp['type']:<12} aria='{inp['ariaLabel']:<30}' "
             f"placeholder='{inp['placeholder']:<25}' val='{inp['value']}'")

    note('\n--- SELECT ---')
    selects = page.evaluate("""() => Array.from(document.querySelectorAll('select')).map(el=>({
        name: el.name, id: el.id,
        ariaLabel: el.getAttribute('aria-label')||'',
        options: Array.from(el.options).map(o=>({value:o.value,text:o.text}))
    }))""")
    for s in selects:
        note(f"  aria='{s['ariaLabel']}' name='{s['name']}'")
        for o in s['options'][:5]:
            note(f"    [{o['value']}] {o['text']}")

    note('\n--- RADIO / CHECKBOX ---')
    radios = page.evaluate("""() => Array.from(
        document.querySelectorAll('input[type=radio],input[type=checkbox]')
    ).map(el=>({
        type: el.type, name: el.name, value: el.value, checked: el.checked,
        ariaLabel: el.getAttribute('aria-label')||'',
        labelText: el.closest('label') ? el.closest('label').innerText.trim().slice(0,40) : ''
    }))""")
    for r in radios:
        note(f"  type={r['type']} val='{r['value']}' label='{r['labelText']}' aria='{r['ariaLabel']}'")

    note('\n--- BUTTON / [role=button] ---')
    btns = page.evaluate("""() => Array.from(document.querySelectorAll(
        'button,[role="button"],input[type=submit]'
    )).map(el=>({
        id: el.id||'', tag: el.tagName,
        text: (el.innerText||el.value||el.getAttribute('aria-label')||'').trim().slice(0,60),
        disabled: el.disabled||false
    }))""")
    for b in btns:
        if b['text'] or b['id']:
            note(f"  <{b['tag']}> id={b['id']:<20} disabled={b['disabled']} text={b['text']}")

    note('\n--- VISIBLE TEXT (body) ---')
    body = page.evaluate("()=>document.body.innerText") or ''
    for line in body.splitlines():
        l = line.strip()
        if l and 'word word' not in l and 'mmMwWLliI' not in l:
            note(f'  {l}')


def safe_wait(page, ms):
    try: page.wait_for_timeout(ms)
    except Exception: pass

def js_fill(page, aria, value):
    return bool(page.evaluate(f"""(v)=>{{
        const el = Array.from(document.querySelectorAll('input,textarea')).find(
            e=>e.getAttribute('aria-label')==='{aria}'||e.getAttribute('placeholder')==='{aria}');
        if(!el)return false;
        const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
        s.call(el,v);
        el.dispatchEvent(new Event('input',{{bubbles:true}}));
        el.dispatchEvent(new Event('change',{{bubbles:true}}));
        return true;
    }}""", value))

def click_cta(page, text):
    for cta in page.query_selector_all('#cta'):
        if text in (cta.inner_text() or '') and cta.is_visible():
            cta.click(); return True
    try:
        loc = page.locator(f'[role="button"]:has-text("{text}")')
        if loc.count() > 0: loc.first.click(); return True
    except Exception: pass
    return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(locale='ja-JP', timezone_id='Asia/Tokyo',
            viewport={'width':1280,'height':900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36')
        page = ctx.new_page()
        Stealth().apply_stealth_sync(page)

        # B1: Email
        log.info('B1: Mo trang dang ky...')
        page.goto(REGISTER_URL, wait_until='networkidle', timeout=45000)
        safe_wait(page, 2500)
        dump_all_inputs(page, 'STEP-1 Entry')

        since_uid = get_latest_uid(EMAIL, PASS)
        js_fill(page, 'メールアドレス', EMAIL)
        safe_wait(page, 500)
        click_cta(page, '認証コードを送信する')
        log.info('Da gui OTP...')
        safe_wait(page, 3000)
        dump_all_inputs(page, 'STEP-2 OTP page')

        # B2: OTP
        log.info('Doc OTP tu Gmail...')
        otp = get_rakuten_otp(EMAIL, PASS, target_alias=EMAIL,
                              retries=18, wait=10, since_uid=since_uid)
        if not otp:
            log.error('KHONG CO OTP'); browser.close(); return

        log.info(f'OTP: {otp}')
        js_fill(page, '認証コード', otp)
        safe_wait(page, 500)
        click_cta(page, '認証する')
        safe_wait(page, 5000)
        dump_all_inputs(page, 'STEP-3a Ngay sau OTP')

        # Scroll va dump tiep
        for scroll_step in range(5):
            page.evaluate(f'()=>window.scrollBy(0, 400)')
            safe_wait(page, 800)
            dump_all_inputs(page, f'STEP-3b scroll {scroll_step+1}')

        log.info('Doi 60s de quan sat tay...')
        safe_wait(page, 60000)
        dump_all_inputs(page, 'FINAL sau 60s')

        try: browser.close()
        except: pass

    note('\n=== XONG ===')
    log.info(f'Done -> {OUT.resolve()}')

if __name__ == '__main__':
    main()
