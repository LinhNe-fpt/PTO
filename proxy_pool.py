import random

# Điền thông tin proxy vào đây
PROXY_LIST = [
    {'ip': '1.2.3.4', 'port': 8080, 'user': 'user1', 'pass': 'pass1'},
    {'ip': '5.6.7.8', 'port': 8080, 'user': 'user2', 'pass': 'pass2'},
]


def get_random_proxy():
    if not PROXY_LIST:
        return None
    return random.choice(PROXY_LIST)
