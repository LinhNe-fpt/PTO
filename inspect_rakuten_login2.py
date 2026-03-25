"""Inspect all clickable elements on Rakuten login page with full text dump."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

LOGIN_URL = (
    "https://login.account.rakuten.com/sso/authorize"
    "?client_id=rakuten_ichiba_top_web&service_id=s245"
    "&response_type=code&scope=openid"
    "&redirect_uri=https%3A%2F%2Fwww.rakuten.co.jp%2F"
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context(locale='ja-JP', timezone_id='Asia/Tokyo',
        viewport={'width': 1280, 'height': 900},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36')
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)
    page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2500)
    print("URL:", page.url)

    # Dump tat ca elements co the click
    elems = page.evaluate("""() =>
        Array.from(document.querySelectorAll('a,button,[role="button"],input[type=submit],#cta,#cta001,[id^="textl"],[id^="prim"],[id^="seco"]'))
        .map(el => ({
            tag: el.tagName,
            id: el.id || '',
            text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ').slice(0, 80),
            href: el.href || '',
            visible: el.offsetParent !== null
        }))
    """)
    print("\n--- ALL CLICKABLE ELEMENTS ---")
    for e in elems:
        if e['text'] or e['id']:
            print(f"  <{e['tag']:<10}> id={e['id']:<25} vis={e['visible']}  text='{e['text']}'")

    print("\n--- FULL BODY TEXT ---")
    body = page.evaluate("()=>document.body.innerText") or ''
    for line in body.splitlines():
        l = line.strip()
        if l and 'word word' not in l and 'mmMwW' not in l:
            print(f"  {l}")

    print("\n=== Dang doi 60s de xem tay... ===")
    try: page.wait_for_timeout(60000)
    except: pass
    try: browser.close()
    except: pass
