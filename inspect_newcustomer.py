import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

URL = 'https://www.pokemoncenter-online.com/new-customer/?token=wVLDO7h%2Bs20KtcSEzvoxfQNkrNsSwzyeoPf0O4NtrL0%3D'

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale='ja-JP', timezone_id='Asia/Tokyo',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        page = context.new_page()
        Stealth().apply_stealth_sync(page)
        page.goto(URL, wait_until='networkidle', timeout=30000)

        lines = []
        lines.append(f'URL: {page.url}')
        lines.append(f'Title: {page.title()}')

        lines.append('\n[INPUT FIELDS]')
        for el in page.query_selector_all('input'):
            t = el.get_attribute('type') or 'text'
            n = el.get_attribute('name') or ''
            i = el.get_attribute('id') or ''
            p2 = el.get_attribute('placeholder') or ''
            lines.append(f'  type={t:<12} name={n:<50} id={i:<40} placeholder={p2}')

        lines.append('\n[SELECT / DROPDOWN]')
        for el in page.query_selector_all('select'):
            n = el.get_attribute('name') or ''
            i = el.get_attribute('id') or ''
            opts = [o.get_attribute('value') or '' for o in el.query_selector_all('option')]
            lines.append(f'  name={n:<50} id={i}')
            lines.append(f'    values={opts[:15]}')

        lines.append('\n[BUTTONS]')
        for el in page.query_selector_all('button, input[type="submit"]'):
            t = el.get_attribute('type') or ''
            text = (el.inner_text() or '').strip().replace('\n', ' ')
            i = el.get_attribute('id') or ''
            lines.append(f'  type={t:<10} id={i:<30} text={text[:60]}')

        lines.append('\n[FORMS]')
        for el in page.query_selector_all('form'):
            lines.append(f'  action={el.get_attribute("action")}  method={el.get_attribute("method")}')

        with open('newcustomer_dump.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        page.screenshot(path='newcustomer_form.png', full_page=True)
        browser.close()
        print('Done -> newcustomer_dump.txt + newcustomer_form.png')

if __name__ == '__main__':
    main()
