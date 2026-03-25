"""
inspect_rakuten_auth.py
Truy cap cac trang Rakuten lien quan dang nhap / dang ky,
dump form, input, link -> file UTF-8 (tranh loi console Windows).

Chay:
  python inspect_rakuten_auth.py
  python inspect_rakuten_auth.py --headless

Ket qua:
  rakuten_auth_dump.txt
  rakuten_auth_*.png (screenshot tung buoc)
"""

import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# Trang chu chinh thuc Rakuten Ichiba (楽天市場)
# https://www.rakuten.co.jp/
RAKUTEN_HOME = "https://www.rakuten.co.jp/"

# Cac URL can phan tich (co the thay doi)
PAGES = [
    ("01_top", RAKUTEN_HOME),  # trang chu — tim link ログイン / 会員登録
    ("02_myrakuten_login", "https://www.rakuten.co.jp/myrakuten/login/"),
    ("03_search_rakuen", "https://search.rakuten.co.jp/search/mall/Rakuen/"),
    # Trang dang ky thuong gap (Rakuten co the redirect)
    ("04_register_entry", "https://order.my.rakuten.co.jp/purchase/register/"),
]


def dump_page(page, label: str, lines: list):
    """Ghi thong tin trang hien tai vao lines."""
    lines.append("")
    lines.append("=" * 72)
    lines.append(f"[{label}]")
    lines.append(f"Final URL: {page.url}")
    lines.append(f"Title: {page.title()}")

    lines.append("\n--- INPUT ---")
    for el in page.query_selector_all("input"):
        t = el.get_attribute("type") or "text"
        n = el.get_attribute("name") or ""
        i = el.get_attribute("id") or ""
        ph = el.get_attribute("placeholder") or ""
        cls = (el.get_attribute("class") or "")[:40]
        lines.append(f"  type={t:<14} name={n:<42} id={i:<35} class={cls}")
        if ph:
            lines.append(f"    placeholder={ph}")

    lines.append("\n--- SELECT ---")
    for el in page.query_selector_all("select"):
        n = el.get_attribute("name") or ""
        i = el.get_attribute("id") or ""
        opts = [o.get_attribute("value") or "" for o in el.query_selector_all("option")][:12]
        lines.append(f"  name={n:<42} id={i}")
        lines.append(f"    options(first 12)={opts}")

    lines.append("\n--- BUTTON / SUBMIT ---")
    for el in page.query_selector_all("button, input[type='submit'], input[type='button']"):
        t = el.get_attribute("type") or ""
        i = el.get_attribute("id") or ""
        val = el.get_attribute("value") or ""
        txt = (el.inner_text() or "").strip().replace("\n", " ")[:70]
        lines.append(f"  type={t:<10} id={i:<35} value={val[:40]} text={txt}")

    lines.append("\n--- FORM ---")
    for el in page.query_selector_all("form"):
        act = el.get_attribute("action") or ""
        meth = el.get_attribute("method") or "get"
        fid = el.get_attribute("id") or ""
        lines.append(f"  id={fid}  method={meth}")
        lines.append(f"    action={act[:120]}")

    lines.append("\n--- LINKS (login / register / member keywords) ---")
    kw = re.compile(
        r"ログイン|会員|登録|login|register|sign.?up|myrakuten|purchase/register",
        re.I,
    )
    seen = set()
    for el in page.query_selector_all("a[href]"):
        href = el.get_attribute("href") or ""
        text = (el.inner_text() or "").strip().replace("\n", " ")[:60]
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        if kw.search(href) or kw.search(text):
            key = (href[:200], text)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  {text[:50]:<52} -> {href[:85]}")

    lines.append("\n--- META / redirect hints ---")
    for el in page.query_selector_all('meta[http-equiv="refresh"], link[rel="canonical"]'):
        lines.append(f"  {el.evaluate('e => e.outerHTML')[:200]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", help="Chay khong hien cua so")
    args = ap.parse_args()

    out_txt = Path("rakuten_auth_dump.txt")
    lines = [
        "Rakuten — phan tich trang dang nhap / dang ky / tim kiem",
        "Chay: python inspect_rakuten_auth.py",
        "",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        for slug, url in PAGES:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2000)
                dump_page(page, slug, lines)
                png = Path(f"rakuten_auth_{slug}.png")
                page.screenshot(path=str(png), full_page=True)
                lines.append(f"\n[Screenshot] {png.resolve()}")
            except Exception as e:
                lines.append(f"\n!! ERROR [{slug}] {url}\n    {e}")

        browser.close()

    out_txt.write_text("\n".join(lines), encoding="utf-8")
    msg = f"Xong -> {out_txt.resolve()}"
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()
