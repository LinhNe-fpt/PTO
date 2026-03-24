"""
notifier.py — Thông báo kết quả đăng ký/xác thực tài khoản.
Hỗ trợ:
  - In màu ra terminal
  - Ghi vào file log (success.log / failed.log)
  - Popup thông báo Windows (không cần cài thêm thư viện)
"""

import ctypes
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# ── ANSI màu terminal ─────────────────────────────────────────────────────────
GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
CYAN   = '\033[96m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

SUCCESS_LOG = 'success.log'
FAILED_LOG  = 'failed.log'


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _append_to_file(filepath, line):
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def _windows_popup(title, message):
    """Hiện popup thông báo Windows (MessageBox). Không block luồng chính."""
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40 | 0x1000)
    except Exception:
        pass  # Bỏ qua nếu không chạy trên Windows


# ── Public API ────────────────────────────────────────────────────────────────

def notify_task_success(email, task_name):
    """Thông báo 1 tác vụ hoàn thành."""
    msg = f"[{_now()}] ✔ {email} — {task_name}"
    print(f"{GREEN}{msg}{RESET}")
    log.info(msg)


def notify_task_failure(email, task_name, error):
    """Thông báo 1 tác vụ thất bại."""
    msg = f"[{_now()}] ✘ {email} — {task_name}: {error}"
    print(f"{RED}{msg}{RESET}")
    log.error(msg)


def notify_account_success(email, index, total):
    """Thông báo 1 tài khoản hoàn thành toàn bộ pipeline."""
    line = f"[{_now()}] SUCCESS [{index}/{total}] {email}"
    print(f"\n{BOLD}{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}{GREEN}  ✔ THÀNH CÔNG [{index}/{total}]: {email}{RESET}")
    print(f"{BOLD}{GREEN}{'='*60}{RESET}\n")
    _append_to_file(SUCCESS_LOG, line)


def notify_account_failure(email, index, total, failed_task):
    """Thông báo 1 tài khoản thất bại."""
    line = f"[{_now()}] FAILED  [{index}/{total}] {email} (dừng tại: {failed_task})"
    print(f"\n{BOLD}{RED}{'='*60}{RESET}")
    print(f"{BOLD}{RED}  ✘ THẤT BẠI [{index}/{total}]: {email}{RESET}")
    print(f"{BOLD}{RED}  Dừng tại task: {failed_task}{RESET}")
    print(f"{BOLD}{RED}{'='*60}{RESET}\n")
    _append_to_file(FAILED_LOG, line)


def notify_summary(success, total, failed_list, popup=True):
    """In tổng kết cuối cùng và hiện popup Windows."""
    print(f"\n{BOLD}{CYAN}{'='*60}")
    print(f"  KẾT QUẢ: {success}/{total} tài khoản thành công")
    print(f"{'='*60}{RESET}")

    if failed_list:
        print(f"{YELLOW}Tài khoản thất bại:{RESET}")
        for f in failed_list:
            print(f"{YELLOW}  - {f['email']} (dừng tại: {f['failed_at']}){RESET}")

    print(f"{CYAN}  Log thành công : {SUCCESS_LOG}")
    print(f"  Log thất bại   : {FAILED_LOG}{RESET}\n")

    if popup:
        msg = (
            f"Hoàn thành: {success}/{total} tài khoản thành công.\n\n"
            + (f"Thất bại ({len(failed_list)}):\n" +
               '\n'.join(f"  {f['email']}" for f in failed_list)
               if failed_list else "Tất cả thành công!")
        )
        _windows_popup("PTO — Kết quả đăng ký", msg)
