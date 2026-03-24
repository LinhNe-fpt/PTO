"""
runner.py — Chạy toàn bộ pipeline tác vụ cho một tài khoản
trong một browser session duy nhất.
"""

import logging
from playwright_stealth import Stealth
from browser import create_browser_context
from tasks import DEFAULT_PIPELINE
from notifier import notify_task_success, notify_task_failure

log = logging.getLogger(__name__)


def run_pipeline(account, pipeline=None, proxy=None, index=0, total=0):
    """
    Chạy lần lượt từng tác vụ trong pipeline cho một tài khoản.
    Browser mở 1 lần, đóng sau khi pipeline kết thúc (dù thành công hay lỗi).

    :param account:  dict thông tin tài khoản
    :param pipeline: list các hàm task, mặc định dùng DEFAULT_PIPELINE
    :param proxy:    dict proxy hoặc None
    :param index:    thứ tự tài khoản (để log)
    :param total:    tổng số tài khoản (để log)
    :return:         (success: bool, failed_task: str | None)
    """
    if pipeline is None:
        pipeline = DEFAULT_PIPELINE

    email = account['email']
    playwright, browser, context = create_browser_context(proxy=proxy)
    page = context.new_page()
    Stealth().apply_stealth_sync(page)

    task_fn = None
    try:
        for task_fn in pipeline:
            task_name = task_fn.__name__
            log.info(f"▶ [{index}/{total}] {email} — {task_name}")
            task_fn(page, context, account)
            notify_task_success(email, task_name)

        return True, None

    except Exception as e:
        failed = task_fn.__name__ if task_fn else 'unknown'
        notify_task_failure(email, failed, e)
        return False, failed

    finally:
        browser.close()
        playwright.stop()
