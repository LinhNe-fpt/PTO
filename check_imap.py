"""
check_imap.py  -  Kiem tra IMAP lay OTP Rakuten
Chay: python check_imap.py
"""
import imaplib
import email as em
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EMAIL_ADDR = "daolinhk18@gmail.com"
EMAIL_PASS = "qump adnl hcbo ytmo"
SENDER     = "confirm-noreply@rakuten.co.jp"
OTP_PAT    = re.compile(r'【(\d{6})】|認証コード[^\d]*(\d{6})|\b(\d{6})\b')


def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    return msg.get_payload(decode=True).decode(errors="ignore") or ""


def main():
    print(f"Connecting {EMAIL_ADDR}...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL_ADDR, EMAIL_PASS)
    mail.select("inbox")

    # Tim tat ca mail tu Rakuten (ca da doc)
    status, msgs = mail.search(None, f'FROM "{SENDER}"')
    ids = msgs[0].split() if msgs[0] else []
    print(f"Tong mail tu {SENDER}: {len(ids)}")

    for mid in reversed(ids[-5:]):
        _, data = mail.fetch(mid, "(RFC822)")
        msg  = em.message_from_bytes(data[0][1])
        to   = msg.get("To", "")
        subj = msg.get("Subject", "")
        body = get_body(msg)
        m    = OTP_PAT.search(subj + "\n" + body)
        otp  = next((g for g in (m.groups() if m else []) if g), "(khong co)")
        print(f"  To     : {to}")
        print(f"  Subject: {subj}")
        print(f"  OTP    : {otp}")
        print(f"  Body   : {body[:200]}")
        print()

    # UNSEEN rieng
    status2, msgs2 = mail.search(None, f'FROM "{SENDER}" UNSEEN')
    unseen_ids = msgs2[0].split() if msgs2[0] else []
    print(f"UNSEEN tu Rakuten: {len(unseen_ids)}")

    mail.logout()
    print("Done.")


if __name__ == "__main__":
    main()
