from twocaptcha import TwoCaptcha

solver = TwoCaptcha('YOUR_API_KEY')


def solve_recaptcha_v2(sitekey, page_url):
    result = solver.recaptcha(sitekey=sitekey, url=page_url)
    return result['code']


def solve_recaptcha_v3(sitekey, page_url, action='verify'):
    result = solver.recaptcha(
        sitekey=sitekey,
        url=page_url,
        version='v3',
        action=action,
        score=0.9
    )
    return result['code']


def inject_recaptcha_token(page, token):
    page.evaluate(f'document.getElementById("g-recaptcha-response").innerHTML = "{token}";')
