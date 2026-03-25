import imaplib
import email
import re
import time
import logging

log = logging.getLogger(__name__)


def get_activation_link(email_address, password, sender_domain, retries=5, wait=10):
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(email_address, password)
    mail.select('inbox')

    for _ in range(retries):
        status, messages = mail.search(None, f'(FROM "{sender_domain}" UNSEEN)')
        if status == 'OK' and messages[0].split():
            latest_id = messages[0].split()[-1]
            status, msg_data = mail.fetch(latest_id, '(RFC822)')
            if status != 'OK':
                break

            msg = email.message_from_bytes(msg_data[0][1])
            body = _extract_body(msg)
            link = _find_activation_link(body)
            if link:
                mail.logout()
                return link

        time.sleep(wait)

    mail.logout()
    return None


def _extract_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                return part.get_payload(decode=True).decode(errors='ignore')
    return msg.get_payload(decode=True).decode(errors='ignore')


def _find_activation_link(body):
    urls = re.findall(r'(https?://[^\s\)\"]+)', body)
    keywords = ('activate', 'confirm', 'verify', 'auth', 'registration')
    for url in urls:
        if any(k in url.lower() for k in keywords):
            return url
    return None


def get_rakuten_otp(email_address: str, password: str,
                    target_alias: str = "",
                    retries: int = 18, wait: int = 10,
                    since_uid: int = 0) -> str | None:
    """
    Doc OTP 6 chu so tu email Rakuten (confirm-noreply@rakuten.co.jp).

    Args:
        email_address: Gmail goc (daolinhk18@gmail.com)
        password:      Gmail App Password
        target_alias:  Alias dang ky (daolinhk18+raku001@gmail.com) - loc theo To
        retries:       So lan thu (default 18 = ~3 phut)
        wait:          Giay cho giua moi lan (default 10s)
        since_uid:     Chi lay mail co UID > gia tri nay (tranh OTP cu)
                       Lay gia tri nay bang get_latest_uid() truoc khi gui OTP.
    """
    OTP_PATTERN = re.compile(
        r'【(\d{6})】'
        r'|verification code[^\d]*(\d{6})'
        r'|認証コード[^\d]*(\d{6})'
        r'|\b(\d{6})\b',
        re.IGNORECASE,
    )
    SENDER_EXACT = "confirm-noreply@rakuten.co.jp"
    alias_local  = target_alias.lower() if target_alias else ""
    # Kiem tra ca inbox + thu rac (OTP Rakuten co the bi Gmail loc vao spam)
    FOLDERS      = ['inbox', '[Gmail]/Spam', '[Gmail]/All Mail']

    log.info(f"[IMAP] Connecting ({email_address}, alias={target_alias or 'any'}, since_uid={since_uid})...")
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_address, password)
    except Exception as e:
        log.error(f"[IMAP] Login failed: {e}")
        return None

    def _search_in_folder(folder: str) -> str | None:
        try:
            rv, _ = mail.select(folder, readonly=True)
            if rv != 'OK':
                return None
        except Exception:
            return None

        # Dung UID SEARCH de dam bao chi lay mail MOI (tranh email cu)
        # UID > since_uid: chi mail den sau khi lay since_uid
        try:
            uid_criterion = f'(FROM "{SENDER_EXACT}" UID {since_uid + 1}:*)'
            status, data = mail.uid('SEARCH', None, uid_criterion)
            uids = data[0].split() if status == 'OK' else []
            log.debug(f"[IMAP][{folder}] UID search since {since_uid}: found {len(uids)}")
        except Exception as e:
            log.debug(f"[IMAP][{folder}] UID search error: {e}")
            uids = []

        # Fallback: UNSEEN (neu UID search khong co ket qua)
        if not uids:
            try:
                status, data = mail.uid('SEARCH', None, f'(FROM "{SENDER_EXACT}" UNSEEN)')
                all_uids = data[0].split() if status == 'OK' else []
                # Van phai loc theo since_uid de tranh lay mail cu
                uids = [u for u in all_uids if int(u) > since_uid] if since_uid > 0 else all_uids[-5:]
                log.debug(f"[IMAP][{folder}] UNSEEN fallback: {len(uids)} uid(s)")
            except Exception as e:
                log.debug(f"[IMAP][{folder}] UNSEEN search error: {e}")

        for uid in reversed(uids):
            try:
                status2, msg_data = mail.uid('FETCH', uid, '(RFC822)')
                if status2 != 'OK' or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else None
                if not raw:
                    continue
                msg     = email.message_from_bytes(raw)
                to_addr = str(msg.get('To', '') or msg.get('Delivered-To', '')).lower()
                subject = str(msg.get('Subject', ''))
                body    = _extract_body(msg)
                full    = subject + "\n" + body
                if alias_local and alias_local not in to_addr:
                    log.debug(f"[IMAP][{folder}] To={to_addr[:50]} != alias")
                    continue
                log.info(f"[IMAP][{folder}] Mail khop uid={uid.decode()} to={to_addr[:50]}")
                m = OTP_PATTERN.search(full)
                if m:
                    return next(g for g in m.groups() if g)
            except Exception as e:
                log.debug(f"[IMAP] fetch uid={uid} error: {e}")
        return None

    for attempt in range(retries):
        log.info(f"[IMAP] Attempt {attempt+1}/{retries}...")
        try:
            for folder in FOLDERS:
                otp = _search_in_folder(folder)
                if otp:
                    log.info(f"[IMAP] OTP={otp} (folder={folder})")
                    try: mail.logout()
                    except Exception: pass
                    return otp
        except Exception as e:
            log.warning(f"[IMAP] Error: {e}")

        if attempt < retries - 1:
            log.info(f"[IMAP] OTP chua den, doi {wait}s...")
            time.sleep(wait)

    try:
        mail.logout()
    except Exception:
        pass
    log.error("[IMAP] Khong tim duoc Rakuten OTP")
    return None


def get_latest_uid(email_address: str, password: str) -> int:
    """
    Lay UID THAT lon nhat trong inbox (dung mail.uid() khong phai mail.search()).
    
    QUAN TRONG: mail.search() tra ve sequence number, KHAC voi UID.
    Phai dung mail.uid('SEARCH') de lay UID that, sau do moi so sanh voi
    UID tu mail.uid('FETCH') trong _search_in_folder().
    """
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_address, password)
        mail.select('inbox')
        # Dung uid('SEARCH') de lay UID THAT (khong phai sequence number)
        status, data = mail.uid('SEARCH', None, 'ALL')
        uids = data[0].split() if status == 'OK' and data[0] else []
        uid = int(uids[-1]) if uids else 0
        mail.logout()
        log.info(f"[IMAP] Latest actual UID: {uid}")
        return uid
    except Exception as e:
        log.warning(f"[IMAP] get_latest_uid error: {e}")
        return 0


def get_password_reset_link(email_address, password, sender_domain='pokemoncenter-online.com',
                             retries=10, wait=15):
    """
    Doc IMAP tim link dat lai mat khau (password reset) tu pokemoncenter-online.com.
    """
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(email_address, password)
    mail.select('inbox')

    reset_keywords = ('password', 'reset', 'pass', 'パスワード', 'pw-reset',
                      'passwordreset', 'password-reset')

    for attempt in range(retries):
        status, messages = mail.search(None, f'(FROM "{sender_domain}" UNSEEN)')
        if status == 'OK' and messages[0].split():
            for msg_id in reversed(messages[0].split()):
                status2, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status2 != 'OK':
                    continue
                msg  = email.message_from_bytes(msg_data[0][1])
                body = _extract_body(msg)
                urls = re.findall(r'(https?://[^\s\)\"<>]+)', body)
                for url in urls:
                    if any(k in url.lower() for k in reset_keywords):
                        mail.logout()
                        return url
        if attempt < retries - 1:
            time.sleep(wait)

    mail.logout()
    return None
