"""inspect_rakuten_login.py - Dump form dang nhap Rakuten (sso/authorize)"""
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
    page.wait_for_timeout(2000)

    print("URL:", page.url)

    inputs = page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(el=>({
        type: el.type, aria: el.getAttribute('aria-label')||'',
        placeholder: el.placeholder||'', id: el.id, name: el.name
    }))""")
    print("\n--- INPUTS ---")
    for inp in inputs:
        print(f"  type={inp['type']:<14} aria='{inp['aria']:<35}' ph='{inp['placeholder'][:30]}'")

    btns = page.evaluate("""() => Array.from(document.querySelectorAll(
        'button,[role="button"],#cta,input[type=submit]'
    )).map(el=>({id:el.id||'',text:(el.innerText||el.value||'').trim().slice(0,60)}))""")
    print("\n--- BUTTONS ---")
    for b in btns:
        if b['text'] or b['id']:
            print(f"  id={b['id']:<22} text={b['text']}")

    body = page.evaluate("()=>document.body.innerText") or ''
    print("\n--- BODY TEXT ---")
    for line in body.splitlines():
        l = line.strip()
        if l and 'word word' not in l and 'mmMwW' not in l:
            print(" ", l)

    try: page.wait_for_timeout(30000)
    except: pass
    try: browser.close()
    except: pass
