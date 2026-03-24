import imaplib
import email
import re
import time


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
