import json
import os

ACCOUNTS_FILE = 'accounts.json'


def save_account(account_data, filename=ACCOUNTS_FILE):
    accounts = load_accounts(filename)
    accounts.append(account_data)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)


def load_accounts(filename=ACCOUNTS_FILE):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []
