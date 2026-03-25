"""
inspect_rakuten_register.py  v8  -  Auto register + Verify login
=================================================================
Logic:
  - Account "done"              -> kiem tra dang nhap (verify_login_one)
  - Account "pending"/"failed"  -> dang ky moi (register_one)
  - Account "running"           -> reset ve "pending" truoc khi chay

Cach dung:
  python inspect_rakuten_register.py              # tu dong 1 account (verify neu done, dang ky neu pending)
  python inspect_rakuten_register.py --all        # chay het tat ca
  python inspect_rakuten_register.py --n 1        # chi chay account #1
  python inspect_rakuten_register.py --verify     # chi verify cac account da done
  python inspect_rakuten_register.py --register   # chi dang ky cac account pending/failed
  python inspect_rakuten_register.py --dry        # in danh sach, khong chay
"""
import argparse
import json
import logging
import sys
import io
from pathlib import Path
from playwright.sync_api import sync_playwright

from tasks_rakuten_reg import (
    register_one,
    verify_login_one,
    load_accounts,
    save_accounts,
    update_account_status,
)

# ── UTF-8 stdout ─────────────────────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ACCOUNTS_FILE = Path("rakuten_reg_accounts.json")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("rakuten_reg_run.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def reset_running(data: list[dict]) -> int:
    """Reset cac account bi ket o trang thai 'running' ve 'pending'."""
    count = 0
    for acc in data:
        if acc["status"] == "running":
            acc["status"] = "pending"
            acc["note"]   = "Reset tu running -> pending"
            count += 1
    if count:
        save_accounts(data)
        log.info(f"Reset {count} account 'running' -> 'pending'")
    return count


def print_table(data: list[dict]):
    print(f"\n{'#':>4}  {'Email':<45}  {'Ho Ten':<18}  {'Status':<10}  Ghi chu")
    print("-" * 105)
    for acc in data:
        name = f"{acc.get('last_kanji','')} {acc.get('first_kanji','')}"
        print(f"{acc['n']:>4}  {acc['email']:<45}  {name:<18}  {acc['status']:<10}  {acc.get('note','')[:30]}")
    pending    = sum(1 for a in data if a["status"] == "pending")
    done       = sum(1 for a in data if a["status"] == "done")
    failed     = sum(1 for a in data if a["status"] == "failed")
    verified   = sum(1 for a in data if a["status"] == "verified")
    login_fail = sum(1 for a in data if a["status"] == "login_fail")
    print(f"\nTong: {len(data)}  |  Pending:{pending}  Done:{done}  Verified:{verified}  Failed:{failed}  LoginFail:{login_fail}")


def run_one(acc: dict, browser, mode: str) -> tuple[bool, str]:
    """
    Chay 1 account theo mode:
      'register' -> dang ky moi
      'verify'   -> kiem tra dang nhap
    """
    if mode == "verify":
        return verify_login_one(acc, browser)
    else:
        return register_one(acc, browser)


def main():
    parser = argparse.ArgumentParser(description="Rakuten auto register + verify login")
    parser.add_argument("--all",      action="store_true", help="Chay tat ca (pending=register, done=verify)")
    parser.add_argument("--n",        type=int,            help="Chi chay account so N (auto detect mode)")
    parser.add_argument("--verify",   action="store_true", help="Chi verify cac account 'done'")
    parser.add_argument("--register", action="store_true", help="Chi dang ky pending/failed")
    parser.add_argument("--dry",      action="store_true", help="Chi in danh sach, khong chay")
    args = parser.parse_args()

    data = load_accounts()
    if not data:
        log.error(f"Khong tim thay {ACCOUNTS_FILE}. Chay: python gen_rakuten_accounts.py --count 10")
        return

    # Reset "running" ve "pending"
    reset_running(data)
    data = load_accounts()

    if args.dry:
        print_table(data)
        return

    # ── Chon queue ───────────────────────────────────────────────────────────
    VERIFY_STATUSES   = ("done", "login_fail")  # "verified" = da xac nhan, khong test lai
    REGISTER_STATUSES = ("pending", "failed")

    if args.n:
        target = next((a for a in data if a["n"] == args.n), None)
        if not target:
            log.error(f"Khong tim thay account #{args.n}")
            return
        # Auto detect mode theo status
        if target["status"] in VERIFY_STATUSES:
            mode = "verify"
        else:
            mode = "register"
        queue = [(target, mode)]

    elif args.verify:
        queue = [(a, "verify") for a in data if a["status"] in VERIFY_STATUSES]

    elif args.register:
        queue = [(a, "register") for a in data if a["status"] in REGISTER_STATUSES]

    elif args.all:
        queue = []
        for a in data:
            if a["status"] in VERIFY_STATUSES:
                queue.append((a, "verify"))
            elif a["status"] in REGISTER_STATUSES:
                queue.append((a, "register"))

    else:
        # Mac dinh: chay 1 account - uu tien verify done truoc
        verify_accs  = [(a, "verify")   for a in data if a["status"] in VERIFY_STATUSES]
        pending_accs = [(a, "register") for a in data if a["status"] in REGISTER_STATUSES]
        if verify_accs and not args.register:
            queue = [verify_accs[0]]
        elif pending_accs:
            queue = [pending_accs[0]]
        else:
            queue = []

    if not queue:
        log.info("Khong co account nao can xu ly.")
        print_table(data)
        return

    log.info(f"Se chay {len(queue)} account...")
    log.info("  " + ", ".join(
        f"#{a['n']}({m})" for a, m in queue[:10]
    ) + ("..." if len(queue) > 10 else ""))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        for acc, mode in queue:
            n = acc["n"]
            log.info(f"\n{'='*60}")
            log.info(f"[#{n:03d}] MODE={mode.upper()}  email={acc['email']}")

            # Danh dau dang xu ly
            if mode == "register":
                update_account_status(n, "running")

            success, note = run_one(acc, browser, mode)

            if mode == "register":
                status = "done" if success else "failed"
            else:
                # Verify: neu login OK -> "verified" (khong test lai lan sau)
                #         neu login fail -> "login_fail" (con trong queue verify)
                status = "verified" if success else "login_fail"

            update_account_status(n, status, note=note)
            icon = "✓" if success else "✗"
            log.info(f"[#{n:03d}] {icon} {status.upper()}: {note}")

        try:
            browser.close()
        except Exception:
            pass

    # Tong ket
    data = load_accounts()
    print("\n")
    print_table(data)


if __name__ == "__main__":
    main()
