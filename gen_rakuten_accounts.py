"""
gen_rakuten_accounts.py
Sinh danh sach tai khoan Rakuten cho bot tu dong dang ky.

Cach dung Gmail +alias:
  base email: daolinhk18@gmail.com
  alias 1:    daolinhk18+raku001@gmail.com  (tat ca ve cung hop thu)
  alias 2:    daolinhk18+raku002@gmail.com
  ...

Rakuten chap nhan +alias nen moi alias la 1 tai khoan rieng biet.
OTP gui ve alias se hien trong hop thu cua email goc.

Chay:
  python gen_rakuten_accounts.py --count 10
  python gen_rakuten_accounts.py --count 5 --start 11   (them tiep tu so 11)
  python gen_rakuten_accounts.py --list                  (xem danh sach hien co)
  python gen_rakuten_accounts.py --reset                 (xoa het, tao moi)
"""
import argparse
import json
import sys
import io
from pathlib import Path
from data_gen import generate_japanese_profile, generate_pto_password

# Boc stdout de hien thi UTF-8 an toan tren Windows PowerShell
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Config ──────────────────────────────────────────────────────────────────
BASE_EMAIL   = "daolinhk18@gmail.com"        # Email goc nhan OTP
EMAIL_PASS   = "qump adnl hcbo ytmo"         # Gmail App Password (khong doi)
ALIAS_PREFIX = "raku"                         # daolinhk18+raku001@gmail.com
OUT_FILE     = Path("rakuten_reg_accounts.json")

# Trang thai tai khoan
STATUS_PENDING  = "pending"    # Chua dang ky
STATUS_DONE     = "done"       # Da dang ky thanh cong
STATUS_FAILED   = "failed"     # That bai


def _make_alias(base: str, n: int, prefix: str) -> str:
    """Tao Gmail alias: user+prefix001@gmail.com"""
    local, domain = base.split("@")
    return f"{local}+{prefix}{n:03d}@{domain}"


def _load() -> list[dict]:
    if OUT_FILE.exists():
        return json.loads(OUT_FILE.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]):
    OUT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(data)} accounts -> {OUT_FILE.resolve()}")


def generate(count: int, start: int):
    """Them moi 'count' account bat dau tu so 'start'."""
    data = _load()

    # Tim so lon nhat hien co de khong bi trung
    existing_nums = set()
    for acc in data:
        alias = acc.get("email", "")
        # Trich so tu alias: +raku001 -> 1
        import re
        m = re.search(rf'\+{ALIAS_PREFIX}(\d+)@', alias)
        if m:
            existing_nums.add(int(m.group(1)))

    added = 0
    n = start
    while added < count:
        if n in existing_nums:
            n += 1
            continue

        alias    = _make_alias(BASE_EMAIL, n, ALIAS_PREFIX)
        profile  = generate_japanese_profile()
        password = generate_pto_password(alias)

        acc = {
            "n":            n,
            "email":        alias,
            "email_pass":   EMAIL_PASS,
            "password":     password,
            "last_kanji":   profile["full_name"].split()[0],
            "first_kanji":  profile["full_name"].split()[-1],
            "last_kana":    profile["full_kana"].split()[0],
            "first_kana":   profile["full_kana"].split()[-1],
            "birthday":     f"{profile['birthday_year']}-{profile['birthday_month']}-{profile['birthday_day']}",
            "gender":       profile["gender"],    # "1"=nam "2"=nu
            "phone":        profile["phone_gen"],
            "postal_code":  profile["postal_code"],
            "prefecture":   profile["prefecture"],
            "city":         profile["city"],
            "street":       profile["street"],
            "building":     profile.get("building", ""),
            "status":       STATUS_PENDING,
            "rakuten_id":   "",     # user ID sau khi dang ky thanh cong
            "note":         "",
        }
        data.append(acc)
        print(f"  [{n:03d}] {alias:<45} {profile['full_name']}")
        existing_nums.add(n)
        added += 1
        n += 1

    data.sort(key=lambda x: x["n"])
    _save(data)


def show_list():
    data = _load()
    if not data:
        print("(khong co account nao)")
        return
    print(f"{'#':>4}  {'Email':<45}  {'Ho Ten':<20}  {'Status'}")
    print("-" * 85)
    for acc in data:
        name = f"{acc['last_kanji']} {acc['first_kanji']}"
        print(f"{acc['n']:>4}  {acc['email']:<45}  {name:<20}  {acc['status']}")
    pending = sum(1 for a in data if a["status"] == STATUS_PENDING)
    done    = sum(1 for a in data if a["status"] == STATUS_DONE)
    failed  = sum(1 for a in data if a["status"] == STATUS_FAILED)
    print(f"\nTong: {len(data)}  |  Pending: {pending}  Done: {done}  Failed: {failed}")


def reset():
    if OUT_FILE.exists():
        OUT_FILE.unlink()
        print("Da xoa het.")


def main():
    parser = argparse.ArgumentParser(description="Quan ly danh sach account dang ky Rakuten")
    parser.add_argument("--count",  type=int, default=10,  help="So account can tao (default 10)")
    parser.add_argument("--start",  type=int, default=1,   help="Bat dau tu so thu may (default 1)")
    parser.add_argument("--list",   action="store_true",   help="Hien danh sach")
    parser.add_argument("--reset",  action="store_true",   help="Xoa tat ca")
    args = parser.parse_args()

    if args.reset:
        reset()
    elif args.list:
        show_list()
    else:
        print(f"Tao {args.count} account bat dau tu so {args.start}...")
        generate(args.count, args.start)
        print()
        show_list()


if __name__ == "__main__":
    main()
