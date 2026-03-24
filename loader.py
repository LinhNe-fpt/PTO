"""
loader.py — Nạp danh sách tài khoản từ file txt hoặc csv.

Định dạng file txt/csv:
    email,app_password
    account1@gmail.com,xxxx xxxx xxxx xxxx
    account2@gmail.com,xxxx xxxx xxxx xxxx

Dòng trống và dòng bắt đầu bằng # sẽ bị bỏ qua.
"""

import csv
import os


def load_accounts_from_file(filepath='accounts.txt'):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File không tồn tại: {filepath}")

    accounts = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            email    = parts[0] if len(parts) > 0 else ''
            app_pass = parts[1] if len(parts) > 1 else ''
            phone    = parts[2] if len(parts) > 2 else ''
            if email:
                accounts.append({'email': email, 'email_password': app_pass, 'phone': phone})

    return accounts
