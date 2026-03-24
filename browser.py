from playwright.sync_api import sync_playwright


def create_browser_context(proxy=None):
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={'width': 1280, 'height': 720},
        locale='ja-JP',
        timezone_id='Asia/Tokyo',
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        proxy={
            "server": f"http://{proxy['ip']}:{proxy['port']}",
            "username": proxy.get('user'),
            "password": proxy.get('pass')
        } if proxy else None
    )
    return playwright, browser, context
