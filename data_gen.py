import random
import hashlib
import string
import json
import os
from faker import Faker

fake = Faker('ja_JP')

ADDRESSES_FILE = os.path.join(os.path.dirname(__file__), 'addresses.json')

# Danh sach nickname tieng Nhat hop le (toan goc)
NICKNAMES = [
    'ピカチュウ', 'リザードン', 'ミュウ', 'イーブイ', 'ゲンガー',
    'カビゴン', 'ルカリオ', 'ガブリアス', 'ミミッキュ', 'ヒトカゲ',
    'フシギダネ', 'ゼニガメ', 'コイキング', 'ミュウツー', 'ラプラス',
    'サーナイト', 'メタグロス', 'バンギラス', 'ドラゴナイト', 'ウインディ',
]


def generate_pto_password(email: str = '') -> str:
    """
    Tao mat khau doc lap cho tung email, xac dinh theo email (cung email -> cung password).
    Dap ung yeu cau PTO: 12 ky tu, co chu hoa, chu thuong, so, ky tu dac biet.
    """
    seed = int(hashlib.md5(email.lower().encode('utf-8')).hexdigest(), 16) if email else None
    rng  = random.Random(seed)

    upper   = rng.choices(string.ascii_uppercase, k=2)
    lower   = rng.choices(string.ascii_lowercase, k=5)
    digits  = rng.choices(string.digits,          k=3)
    special = rng.choices('!@#$%',                k=2)

    chars = upper + lower + digits + special   # 12 ky tu
    rng.shuffle(chars)
    return ''.join(chars)


def load_addresses():
    if os.path.exists(ADDRESSES_FILE):
        with open(ADDRESSES_FILE, 'r', encoding='utf-8') as f:
            addrs = json.load(f)
            if addrs:
                return addrs
    return [{"postal_code": "1060032", "prefecture": "東京都",
             "city": "港区六本木", "street": "６−１０−１", "building": ""}]


def generate_japanese_profile():
    # Ten (ho + ten) tieng Nhat
    last_name  = fake.last_name()
    first_name = fake.first_name()
    full_name  = f'{last_name}　{first_name}'   # dung 全角 space

    # Furigana katakana
    last_kana  = fake.last_kana_name()
    first_kana = fake.first_kana_name()
    full_kana  = f'{last_kana}　{first_kana}'

    # Nickname ngau nhien
    nickname = random.choice(NICKNAMES) + str(random.randint(10, 999))

    # Ngay sinh (tuoi 18-26, nam 2000-2006)
    year  = str(random.randint(2000, 2006))
    month = str(random.randint(1, 12)).zfill(2)
    day   = str(random.randint(1, 28)).zfill(2)

    # Gioi tinh (1=nam, 2=nu)
    gender = random.choice(['1', '2'])

    # Dia chi (lay ngau nhien tu pool)
    addr = random.choice(load_addresses())

    # So dien thoai Nhat (neu khong co trong account)
    phone = f'0{random.randint(70,90)}{random.randint(10000000,99999999)}'

    return {
        'nickname':       nickname,
        'full_name':      full_name,
        'full_kana':      full_kana,
        'birthday_year':  year,
        'birthday_month': month,
        'birthday_day':   day,
        'gender':         gender,
        'postal_code':    addr['postal_code'],
        'prefecture':     addr['prefecture'],
        'city':           addr['city'],
        'street':         addr['street'],
        'building':       addr.get('building', ''),
        'phone_gen':      phone,
    }
