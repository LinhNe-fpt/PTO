"""
PTO Bot GUI
Tab 1 : Tai khoan  – moi hang co URL dang ky rieng, bot tu chay khong can gian doan
Tab 2 : Dia chi    – quan ly pool dia chi Nhat Ban
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, queue, json, os, logging
from datetime import datetime

from storage import save_account
from data_gen import generate_pto_password, gen_matrix_password

ACCOUNTS_FILE         = 'accounts.json'
ADDRESSES_FILE        = 'addresses.json'
RAKUTEN_ACCOUNTS_FILE = 'rakuten_accounts.json'
RAKUTEN_REG_FILE      = 'rakuten_reg_accounts.json'
EMAIL_POOL_FILE       = 'email_pool.json'
PASSWORD              = 'SecurePass123!'

# Queues bot <-> GUI (chi dung khi khong co URL san, fallback)
otp_req_q  = queue.Queue()
otp_res_q  = queue.Queue()
link_req_q = queue.Queue()
link_res_q = queue.Queue()

ALL_PREFECTURES = [
    '北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県',
    '茨城県','栃木県','群馬県','埼玉県','千葉県','東京都','神奈川県',
    '新潟県','富山県','石川県','福井県','山梨県','長野県','岐阜県',
    '静岡県','愛知県','三重県','滋賀県','京都府','大阪府','兵庫県',
    '奈良県','和歌山県','鳥取県','島根県','岡山県','広島県','山口県',
    '徳島県','香川県','愛媛県','高知県','福岡県','佐賀県','長崎県',
    '熊本県','大分県','宮崎県','鹿児島県','沖縄県',
]

STATUS_COLORS_REG = {
    'pending':     '#888888',
    'done':        '#27ae60',  # xanh la - da dang ky, chua verify
    'verified':    '#1abc9c',  # xanh ngoc - da dang ky VA login OK (khong test lai)
    'failed':      '#e74c3c',
    'running':     '#3498db',
    'login_fail':  '#e67e22',  # cam - da dang ky nhung login that bai
}

STATUS_COLORS = {
    'Cho':          '#888888',
    'Dang chay':    '#3498db',
    'Dien form':    '#9b59b6',
    'Thanh cong':   '#27ae60',
    'That bai':     '#e74c3c',
    # Rakuten-specific
    'Dang nhap':    '#2980b9',
    'Tim san pham': '#8e44ad',
    'Them gio hang':'#d35400',
    'Thanh toan':   '#c0392b',
    'Dat hang':     '#16a085',
}


# ── Log handler ───────────────────────────────────────────────────────────────
class GUILogHandler(logging.Handler):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def emit(self, record):
        msg = self.format(record) + '\n'
        self.widget.after(0, self._append, msg)

    def _append(self, msg):
        self.widget.configure(state='normal')
        self.widget.insert('end', msg)
        self.widget.see('end')
        self.widget.configure(state='disabled')


# ── Dialog: Them/Sua tai khoan ────────────────────────────────────────────────
class AccountDialog(tk.Toplevel):
    def __init__(self, parent, account=None):
        super().__init__(parent)
        self.title('Them tai khoan' if account is None else 'Sua tai khoan')
        self.resizable(False, False)
        self.result    = None
        self._is_new   = (account is None)
        self._show_pwd = False

        fields = [
            ('Email',                'email',          False, 40),
            ('Mat khau PTO',         'pto_password',   True,  40),
            ('App Password Gmail',   'email_password', True,  40),
            ('So dien thoai',        'phone',          False, 40),
            ('URL dang ky (token)',  'reg_url',        False, 40),
        ]
        self._vars    = {}
        self._entries = {}
        for r, (lbl, key, secret, width) in enumerate(fields):
            tk.Label(self, text=lbl+':').grid(row=r, column=0, sticky='e', padx=10, pady=6)
            default = account.get(key, '') if account else ''
            # Neu them moi va pto_password chua co -> tu sinh
            if key == 'pto_password' and self._is_new and not default:
                default = generate_pto_password('')   # email chua biet, se cap nhat sau
            var = tk.StringVar(value=default)
            self._vars[key] = var
            show = '*' if secret else ''
            entry = tk.Entry(self, textvariable=var, width=width, show=show)
            entry.grid(row=r, column=1, padx=(10, 2), pady=6, sticky='w')
            self._entries[key] = (entry, secret)

            # Nut xem/an mat khau + nut sinh lai
            if key == 'pto_password':
                btn_frame = tk.Frame(self)
                btn_frame.grid(row=r, column=2, padx=(0, 6), sticky='w')
                self._eye_btn = tk.Button(btn_frame, text='👁', width=3,
                                          command=self._toggle_pwd)
                self._eye_btn.pack(side='left', padx=1)
                tk.Button(btn_frame, text='↻', width=3,
                          command=self._regen_pwd).pack(side='left', padx=1)

        # Khi email thay doi -> tu cap nhat password neu dang them moi
        self._vars['email'].trace_add('write', self._on_email_change)

        hint = tk.Label(self,
            text='URL dang ky: https://www.pokemoncenter-online.com/new-customer/?token=...',
            fg='gray', font=('', 8))
        hint.grid(row=len(fields), column=0, columnspan=3, padx=10, sticky='w')

        bf = tk.Frame(self)
        bf.grid(row=len(fields)+1, column=0, columnspan=3, pady=10)
        tk.Button(bf, text='Luu', width=10, bg='#27ae60', fg='white',
                  command=self._save).pack(side='left', padx=4)
        tk.Button(bf, text='Huy', width=10, command=self.destroy).pack(side='left', padx=4)
        self.grab_set()
        self.wait_window()

    def _on_email_change(self, *_):
        if not self._is_new:
            return
        email = self._vars['email'].get().strip()
        # Chi tu cap nhat neu password chua bi chinh sua tay
        generated = generate_pto_password(email)
        self._vars['pto_password'].set(generated)

    def _toggle_pwd(self):
        self._show_pwd = not self._show_pwd
        entry, _ = self._entries['pto_password']
        entry.config(show='' if self._show_pwd else '*')
        self._eye_btn.config(relief='sunken' if self._show_pwd else 'raised')

    def _regen_pwd(self):
        email = self._vars['email'].get().strip()
        import random as _r
        # Sinh lai ngau nhien (khong can xac dinh theo email)
        rng = _r.Random()
        import string as _s
        chars = (
            _r.choices(_s.ascii_uppercase, k=2) +
            _r.choices(_s.ascii_lowercase, k=5) +
            _r.choices(_s.digits,          k=3) +
            _r.choices('!@#$%',            k=2)
        )
        rng.shuffle(chars)
        self._vars['pto_password'].set(''.join(chars))

    def _save(self):
        if not self._vars['email'].get().strip():
            messagebox.showwarning('', 'Email khong duoc de trong!', parent=self)
            return
        if not self._vars['pto_password'].get().strip():
            messagebox.showwarning('', 'Mat khau PTO khong duoc de trong!', parent=self)
            return
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


# ── Dialog: Them/Sua dia chi ──────────────────────────────────────────────────
class AddressDialog(tk.Toplevel):
    def __init__(self, parent, addr=None):
        super().__init__(parent)
        self.title('Them dia chi' if addr is None else 'Sua dia chi')
        self.resizable(False, False)
        self.result = None
        fields = [
            ('Ma buu chinh (7 so)',     'postal_code'),
            ('Quan / Phuong (toi da 12 ky tu)', 'city'),
            ('So nha / Duong',          'street'),
            ('Toa nha (tuy chon)',      'building'),
        ]
        self._vars = {}
        for r, (lbl, key) in enumerate(fields):
            tk.Label(self, text=lbl+':').grid(row=r, column=0, sticky='e', padx=10, pady=5)
            var = tk.StringVar(value=addr.get(key,'') if addr else '')
            self._vars[key] = var
            tk.Entry(self, textvariable=var, width=36).grid(row=r, column=1, padx=10, pady=5)
        r = len(fields)
        tk.Label(self, text='Tinh / Thanh pho:').grid(row=r, column=0, sticky='e', padx=10, pady=5)
        self._pref = tk.StringVar(value=addr.get('prefecture','東京都') if addr else '東京都')
        ttk.Combobox(self, textvariable=self._pref, values=ALL_PREFECTURES,
                     state='readonly', width=34).grid(row=r, column=1, padx=10, pady=5)
        bf = tk.Frame(self)
        bf.grid(row=r+1, column=0, columnspan=2, pady=10)
        tk.Button(bf, text='Luu', width=10, bg='#27ae60', fg='white',
                  command=self._save).pack(side='left', padx=4)
        tk.Button(bf, text='Huy', width=10, command=self.destroy).pack(side='left', padx=4)
        self.grab_set()
        self.wait_window()

    def _save(self):
        if not self._vars['postal_code'].get().strip():
            messagebox.showwarning('', 'Ma buu chinh khong duoc de trong!', parent=self)
            return
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.result['prefecture'] = self._pref.get()
        self.destroy()


# ── Dialog: OTP ───────────────────────────────────────────────────────────────
class OTPDialog(tk.Toplevel):
    def __init__(self, parent, email, prompt):
        super().__init__(parent)
        self.title('Nhap ma OTP')
        self.resizable(False, False)
        self.result = None
        self.attributes('-topmost', True)
        tk.Label(self, text=f'Tai khoan: {email}',
                 font=('',10,'bold')).pack(padx=16, pady=(14,4))
        tk.Label(self, text=prompt, wraplength=320).pack(padx=16, pady=4)
        self._var = tk.StringVar()
        e = tk.Entry(self, textvariable=self._var, width=20,
                     font=('',14), justify='center')
        e.pack(padx=16, pady=8)
        e.focus_set()
        tk.Button(self, text='Xac nhan', width=12, bg='#2980b9', fg='white',
                  font=('',10,'bold'), command=self._ok).pack(pady=(0,14))
        self.bind('<Return>', lambda _: self._ok())
        self.grab_set()
        self.wait_window()

    def _ok(self):
        self.result = self._var.get().strip()
        self.destroy()


# ── Tab: Tai khoan ────────────────────────────────────────────────────────────
class AccountTab(tk.Frame):
    COLS = ('#', 'Email', 'SDT', 'URL dang ky', 'Trang thai', 'Ghi chu')

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._accounts = []
        self._build()
        self._load()

    def _build(self):
        # Toolbar
        tb = tk.Frame(self, bd=1, relief='raised')
        tb.pack(fill='x')
        tk.Button(tb, text='+ Them',       command=self._add).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Sua',          command=self._edit).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Xoa',          command=self._delete).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Import JSON',  command=self._import_json).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Import TXT',   command=self._import_txt).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Reset trang thai', command=self._reset_status).pack(side='left', padx=6, pady=3)
        tk.Button(tb, text='🔍 Inspect Login',  command=self.app.inspect_login,
                  fg='#8e44ad').pack(side='left', padx=2, pady=3)
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=6)
        self.run_btn = tk.Button(tb, text='▶  CHAY BOT',
                                 bg='#27ae60', fg='white', font=('',10,'bold'),
                                 command=self.app.start_bot)
        self.run_btn.pack(side='left', padx=4, pady=3)
        self.stop_btn = tk.Button(tb, text='■  DUNG',
                                  bg='#e74c3c', fg='white', font=('',10,'bold'),
                                  command=self.app.stop_bot, state='disabled')
        self.stop_btn.pack(side='left', padx=2, pady=3)
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=6)
        self.login_btn = tk.Button(tb, text='🔑  DANG NHAP',
                                   bg='#2980b9', fg='white', font=('',10,'bold'),
                                   command=self.app.start_login_bot)
        self.login_btn.pack(side='left', padx=4, pady=3)
        self.login_stop_btn = tk.Button(tb, text='■  DUNG DN',
                                        bg='#e74c3c', fg='white', font=('',10,'bold'),
                                        command=self.app.stop_login_bot, state='disabled')
        self.login_stop_btn.pack(side='left', padx=2, pady=3)
        self.status_lbl = tk.Label(tb, text='San sang', fg='gray')
        self.status_lbl.pack(side='right', padx=10)

        # Huong dan
        hint = tk.Frame(self, bg='#eaf4fb')
        hint.pack(fill='x', padx=4, pady=(2,0))
        tk.Label(hint,
            text='Tip: Dien san URL dang ky cho tung tai khoan → bam CHAY BOT → bot tu dong dien form toan bo, khong can gian doan.',
            bg='#eaf4fb', fg='#2980b9', font=('',8)).pack(anchor='w', padx=8, pady=3)

        # Bang du lieu
        tf = tk.Frame(self)
        tf.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(tf, columns=self.COLS, show='headings', selectmode='browse')
        self.tree.heading('#',           text='#')
        self.tree.heading('Email',       text='Email')
        self.tree.heading('SDT',         text='SDT')
        self.tree.heading('URL dang ky', text='URL dang ky')
        self.tree.heading('Trang thai',  text='Trang thai')
        self.tree.heading('Ghi chu',     text='Ghi chu')
        self.tree.column('#',           width=32,  stretch=False)
        self.tree.column('Email',       width=220, stretch=False)
        self.tree.column('SDT',         width=100, stretch=False)
        self.tree.column('URL dang ky', width=320)
        self.tree.column('Trang thai',  width=100, stretch=False)
        self.tree.column('Ghi chu',     width=160)
        vsb = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        for tag, color in STATUS_COLORS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.bind('<Double-1>', self._on_double_click)

        # Thanh nhap nhanh URL (click hang roi dan URL o duoi)
        url_bar = tk.Frame(self, bd=1, relief='sunken', bg='#f8f8f8')
        url_bar.pack(fill='x', padx=4, pady=(2,2))
        tk.Label(url_bar, text='Dan URL cho hang dang chon:', bg='#f8f8f8',
                 font=('',8,'bold')).pack(side='left', padx=6, pady=4)
        self._url_var = tk.StringVar()
        self._url_entry = tk.Entry(url_bar, textvariable=self._url_var,
                                   font=('Consolas',8), width=62)
        self._url_entry.pack(side='left', fill='x', expand=True, padx=(0,4), pady=4)
        tk.Button(url_bar, text='Gan URL', bg='#2980b9', fg='white',
                  font=('',8,'bold'), command=self._assign_url).pack(side='left', padx=(0,6), pady=4)
        self._url_entry.bind('<Return>', lambda _: self._assign_url())
        tk.Label(url_bar, text='(Chon hang truoc, dan URL, Enter)',
                 bg='#f8f8f8', fg='gray', font=('',8)).pack(side='left', padx=4)

    # ── Refresh ────────────────────────────────────────────────────────────────
    def _refresh(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for i, a in enumerate(self._accounts, 1):
            s    = a.get('status', 'Cho')
            url  = a.get('reg_url', '')
            url_short = (url[:40] + '...') if len(url) > 43 else url
            note = a.get('note', '')
            self.tree.insert('', 'end',
                             values=(i, a['email'], a.get('phone',''), url_short, s, note),
                             tags=(s,))

    def set_status(self, email, status, note=''):
        for a in self._accounts:
            if a['email'] == email:
                a['status'] = status
                if note:
                    a['note'] = note
        self.after(0, self._refresh)

    def _sel_idx(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    # ── Gan URL nhanh ──────────────────────────────────────────────────────────
    def _assign_url(self):
        idx = self._sel_idx()
        if idx is None:
            messagebox.showwarning('', 'Chon mot hang tai khoan truoc!'); return
        url = self._url_var.get().strip()
        if not url:
            messagebox.showwarning('', 'Chua nhap URL!'); return
        if 'token' not in url and 'new-customer' not in url:
            messagebox.showwarning('', 'URL khong hop le.\nPhai co dang: .../new-customer/?token=...'); return
        self._accounts[idx]['reg_url'] = url
        self._accounts[idx]['status']  = 'Cho'
        self._accounts[idx]['note']    = ''
        self._url_var.set('')
        self._save(); self._refresh()

    def _on_double_click(self, event):
        self._edit()

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def _add(self):
        dlg = AccountDialog(self)
        if dlg.result:
            dlg.result.update({'status': 'Cho', 'note': ''})
            self._accounts.append(dlg.result)
            self._save(); self._refresh()

    def _edit(self):
        idx = self._sel_idx()
        if idx is None: return
        dlg = AccountDialog(self, self._accounts[idx])
        if dlg.result:
            dlg.result['status'] = self._accounts[idx].get('status', 'Cho')
            dlg.result['note']   = self._accounts[idx].get('note', '')
            self._accounts[idx]  = dlg.result
            self._save(); self._refresh()

    def _delete(self):
        idx = self._sel_idx()
        if idx is None: return
        if messagebox.askyesno('Xoa', f'Xoa: {self._accounts[idx]["email"]}?'):
            self._accounts.pop(idx); self._save(); self._refresh()

    def _reset_status(self):
        for a in self._accounts:
            if a.get('status') == 'That bai':
                a['status'] = 'Cho'; a['note'] = ''
        self._save(); self._refresh()

    # ── Import ─────────────────────────────────────────────────────────────────
    def _import_json(self):
        """Import tu file JSON: [{email, email_password, phone, reg_url}, ...]"""
        path = filedialog.askopenfilename(
            filetypes=[('JSON','*.json'), ('All','*.*')])
        if not path: return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            existing = {a['email'] for a in self._accounts}
            added = 0
            for a in data:
                if isinstance(a, dict) and 'email' in a and a['email'] not in existing:
                    a.setdefault('status', 'Cho')
                    a.setdefault('note', '')
                    a.setdefault('reg_url', '')
                    if not a.get('pto_password', '').strip():
                        a['pto_password'] = generate_pto_password(a['email'])
                    self._accounts.append(a); added += 1
            self._save(); self._refresh()
            messagebox.showinfo('Import', f'Da them {added} tai khoan.')
        except Exception as e:
            messagebox.showerror('Loi import JSON', str(e))

    def _import_txt(self):
        """
        Import tu file TXT/CSV.
        Ho tro 2 dinh dang:
          email,app_password,phone
          email,app_password,phone,reg_url
        """
        path = filedialog.askopenfilename(
            filetypes=[('Text/CSV','*.txt *.csv'), ('All','*.*')])
        if not path: return
        try:
            existing = {a['email'] for a in self._accounts}
            added = 0
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) < 1: continue
                    a = {
                        'email':          parts[0],
                        'pto_password':   parts[1] if len(parts) > 1 else '',
                        'email_password': parts[2] if len(parts) > 2 else '',
                        'phone':          parts[3] if len(parts) > 3 else '',
                        'reg_url':        parts[4] if len(parts) > 4 else '',
                        'status': 'Cho', 'note': '',
                    }
                    if not a['pto_password'].strip():
                        a['pto_password'] = generate_pto_password(a['email'])
                    if a['email'] and a['email'] not in existing:
                        self._accounts.append(a); added += 1
            self._save(); self._refresh()
            messagebox.showinfo('Import', f'Da them {added} tai khoan.')
        except Exception as e:
            messagebox.showerror('Loi import TXT', str(e))

    # ── Load / Save ────────────────────────────────────────────────────────────
    def _load(self):
        if not os.path.exists(ACCOUNTS_FILE): return
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                self._accounts = json.load(f)
            for a in self._accounts:
                a.setdefault('status', 'Cho')
                a.setdefault('note', '')
                a.setdefault('reg_url', '')
                # Chi sinh password cho tai khoan moi chua dang ky
                # Tai khoan da Thanh cong giu nguyen (hoac de trong -> fallback PASSWORD)
                if not a.get('pto_password', '').strip():
                    if a.get('status') != 'Thanh cong':
                        a['pto_password'] = generate_pto_password(a.get('email', ''))
            self._refresh()
        except Exception:
            pass

    def _save(self):
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._accounts, f, ensure_ascii=False, indent=2)

    def get_pending(self):
        return [a for a in self._accounts if a.get('status') not in ('Thanh cong',)]

    def get_registered(self):
        return [a for a in self._accounts if a.get('status') == 'Thanh cong']

    def save_file(self):
        self._save()


# ── Tab: Dia chi ──────────────────────────────────────────────────────────────
class AddressTab(tk.Frame):
    COLS = ('Tinh/TP', 'Ma buu chinh', 'Quan / Phuong', 'So nha', 'Toa nha')

    def __init__(self, parent):
        super().__init__(parent)
        self._addresses = []
        self._build()
        self._load()

    def _build(self):
        tb = tk.Frame(self, bd=1, relief='raised')
        tb.pack(fill='x')
        tk.Button(tb, text='+ Them',     command=self._add).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Sua',        command=self._edit).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Xoa',        command=self._delete).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Import CSV', command=self._import_csv).pack(side='left', padx=6, pady=3)
        tk.Label(tb, text='Bot chon ngau nhien 1 dia chi cho moi tai khoan',
                 fg='gray').pack(side='right', padx=10)

        tf = tk.Frame(self)
        tf.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(tf, columns=self.COLS, show='headings', selectmode='browse')
        for col, w in zip(self.COLS, [110, 105, 200, 160, 140]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w)
        vsb = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        self.count_lbl = tk.Label(self, text='0 dia chi', fg='gray')
        self.count_lbl.pack(anchor='w', padx=8, pady=2)

    def _refresh(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for a in self._addresses:
            self.tree.insert('', 'end', values=(
                a.get('prefecture', ''), a.get('postal_code', ''),
                a.get('city', ''), a.get('street', ''), a.get('building', '')))
        self.count_lbl.config(text=f'{len(self._addresses)} dia chi')

    def _sel_idx(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    def _add(self):
        dlg = AddressDialog(self)
        if dlg.result:
            self._addresses.append(dlg.result); self._save(); self._refresh()

    def _edit(self):
        idx = self._sel_idx()
        if idx is None: return
        dlg = AddressDialog(self, self._addresses[idx])
        if dlg.result:
            self._addresses[idx] = dlg.result; self._save(); self._refresh()

    def _delete(self):
        idx = self._sel_idx()
        if idx is None: return
        a = self._addresses[idx]
        if messagebox.askyesno('Xoa', f'Xoa: {a.get("prefecture")} {a.get("city")}?'):
            self._addresses.pop(idx); self._save(); self._refresh()

    def _import_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[('CSV', '*.csv'), ('Text', '*.txt'), ('All', '*.*')])
        if not path: return
        added = 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    p = [x.strip() for x in line.split(',')]
                    if len(p) >= 4:
                        self._addresses.append({
                            'postal_code': p[0], 'prefecture': p[1],
                            'city': p[2], 'street': p[3],
                            'building': p[4] if len(p) > 4 else ''})
                        added += 1
            self._save(); self._refresh()
            messagebox.showinfo('Import', f'Da them {added} dia chi.')
        except Exception as e:
            messagebox.showerror('Loi', str(e))

    def _load(self):
        if not os.path.exists(ADDRESSES_FILE): return
        try:
            with open(ADDRESSES_FILE, 'r', encoding='utf-8') as f:
                self._addresses = json.load(f)
            self._refresh()
        except Exception:
            pass

    def _save(self):
        with open(ADDRESSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._addresses, f, ensure_ascii=False, indent=2)


# ── Dialog: Them/Sua tai khoan Rakuten ───────────────────────────────────────
class RakutenAccountDialog(tk.Toplevel):
    def __init__(self, parent, account=None):
        super().__init__(parent)
        self.title('Them tai khoan Rakuten' if account is None else 'Sua tai khoan Rakuten')
        self.resizable(False, False)
        self.result = None
        fields = [
            ('Rakuten ID (email)',    'rakuten_id',       False, 44),
            ('Mat khau Rakuten',      'rakuten_password', True,  44),
        ]
        self._vars = {}
        for r, (lbl, key, secret, w) in enumerate(fields):
            tk.Label(self, text=lbl+':').grid(row=r, column=0, sticky='e', padx=10, pady=6)
            var = tk.StringVar(value=account.get(key, '') if account else '')
            self._vars[key] = var
            tk.Entry(self, textvariable=var, width=w,
                     show='*' if secret else '').grid(row=r, column=1, padx=10, pady=6)
        bf = tk.Frame(self)
        bf.grid(row=len(fields), column=0, columnspan=2, pady=10)
        tk.Button(bf, text='Luu', width=10, bg='#27ae60', fg='white',
                  command=self._save).pack(side='left', padx=4)
        tk.Button(bf, text='Huy', width=10, command=self.destroy).pack(side='left', padx=4)
        self.grab_set()
        self.wait_window()

    def _save(self):
        if not self._vars['rakuten_id'].get().strip():
            messagebox.showwarning('', 'Rakuten ID khong duoc de trong!', parent=self)
            return
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


# ── Tab: Rakuten Orders ───────────────────────────────────────────────────────
class RakutenTab(tk.Frame):
    ACC_COLS = ('#', 'Rakuten ID', 'Trang thai', 'Ghi chu')

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._accounts = []
        self._running  = False
        self._build()
        self._load()

    def _build(self):
        # Toolbar
        tb = tk.Frame(self, bd=1, relief='raised')
        tb.pack(fill='x')
        tk.Button(tb, text='+ Them',       command=self._add).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Sua',          command=self._edit).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Xoa',          command=self._delete).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Import TXT',   command=self._import_txt).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Reset trang thai', command=self._reset).pack(side='left', padx=6, pady=3)
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=6)
        self.run_btn = tk.Button(tb, text='▶  CHAY RAKUTEN',
                                 bg='#e67e22', fg='white', font=('', 10, 'bold'),
                                 command=self.app.start_rakuten_bot)
        self.run_btn.pack(side='left', padx=4, pady=3)
        self.stop_btn = tk.Button(tb, text='■  DUNG',
                                  bg='#e74c3c', fg='white', font=('', 10, 'bold'),
                                  command=self.app.stop_rakuten_bot, state='disabled')
        self.stop_btn.pack(side='left', padx=2, pady=3)

        # So luong browser song song
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=6)
        tk.Label(tb, text='So browser song song:').pack(side='left', padx=(0, 2))
        self._max_concurrent = tk.IntVar(value=3)
        sb = ttk.Spinbox(tb, from_=1, to=20, textvariable=self._max_concurrent,
                         width=4, font=('Consolas', 9))
        sb.pack(side='left', padx=(0, 4))
        tk.Label(tb, text='(moi TK = 1 browser rieng)', fg='gray',
                 font=('', 8)).pack(side='left')

        self.status_lbl = tk.Label(tb, text='San sang', fg='gray')
        self.status_lbl.pack(side='right', padx=10)

        # Progress label
        self.progress_lbl = tk.Label(tb, text='', fg='#2980b9', font=('', 8, 'bold'))
        self.progress_lbl.pack(side='right', padx=6)

        # Body: bang tai khoan (trai) + cau hinh san pham (phai)
        body = tk.Frame(self)
        body.pack(fill='both', expand=True)

        # --- Trai: Bang tai khoan ---
        left = tk.Frame(body)
        left.pack(side='left', fill='both', expand=True)
        tk.Label(left, text='Tai khoan Rakuten', font=('', 9, 'bold')).pack(anchor='w', padx=6, pady=(4, 0))
        tf = tk.Frame(left)
        tf.pack(fill='both', expand=True, padx=4, pady=4)
        self.tree = ttk.Treeview(tf, columns=self.ACC_COLS, show='headings', selectmode='browse')
        self.tree.heading('#',           text='#')
        self.tree.heading('Rakuten ID',  text='Rakuten ID')
        self.tree.heading('Trang thai',  text='Trang thai')
        self.tree.heading('Ghi chu',     text='Ghi chu')
        self.tree.column('#',           width=32,  stretch=False)
        self.tree.column('Rakuten ID',  width=230)
        self.tree.column('Trang thai',  width=100, stretch=False)
        self.tree.column('Ghi chu',     width=160)
        vsb = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        for tag, color in STATUS_COLORS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.bind('<Double-1>', lambda _: self._edit())

        # --- Phai: Cau hinh san pham ---
        right = tk.LabelFrame(body, text='  Cau hinh san pham  ', font=('', 9, 'bold'))
        right.pack(side='left', fill='y', padx=(0, 4), pady=4, ipadx=4, ipady=4)

        def lbl_entry(parent, text, key, default='', width=32, row=0):
            tk.Label(parent, text=text, anchor='w').grid(row=row, column=0, sticky='w', padx=8, pady=5)
            var = tk.StringVar(value=default)
            tk.Entry(parent, textvariable=var, width=width).grid(row=row, column=1, padx=(0,8), pady=5)
            return var

        self._keyword_var  = lbl_entry(right, 'Keyword tim kiem:', 'keyword', 'Rakuen', row=0)
        self._url_var      = lbl_entry(right, 'URL san pham (uu tien):', 'url', '', row=1)
        self._quantity_var = lbl_entry(right, 'So luong:', 'qty', '1', width=6, row=2)

        # Checkbox tu chon bien the
        self._auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(right, text='Tu dong chon bien the dau tien\n(kich co, mau sac)',
                       variable=self._auto_var, anchor='w',
                       justify='left').grid(row=3, column=0, columnspan=2,
                                            sticky='w', padx=8, pady=(2, 8))

        ttk.Separator(right, orient='horizontal').grid(
            row=4, column=0, columnspan=2, sticky='ew', pady=4)

        ttk.Separator(right, orient='horizontal').grid(
            row=4, column=0, columnspan=2, sticky='ew', pady=(8, 4))

        # ── Sniper Settings ────────────────────────────────────────────────
        tk.Label(right, text='Sniper / Flash Sale', font=('', 9, 'bold'),
                 fg='#c0392b').grid(row=5, column=0, columnspan=2,
                                    sticky='w', padx=8, pady=(4, 2))

        # Mode radio
        self._snipe_mode = tk.StringVar(value='normal')
        modes = [
            ('Dat hang ngay (binh thuong)',  'normal'),
            ('Theo doi san pham (auto snipe)', 'monitor'),
            ('Dat gio + theo doi',            'snipe'),
        ]
        for row_i, (txt, val) in enumerate(modes):
            tk.Radiobutton(right, text=txt, variable=self._snipe_mode,
                           value=val, command=self._on_mode_change,
                           anchor='w').grid(row=6+row_i, column=0, columnspan=2,
                                            sticky='w', padx=16)

        # Target datetime
        dt_frame = tk.Frame(right)
        dt_frame.grid(row=9, column=0, columnspan=2, sticky='w', padx=16, pady=4)
        tk.Label(dt_frame, text='Gio mo ban:', font=('', 8)).pack(side='left')
        # Date
        self._target_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        tk.Entry(dt_frame, textvariable=self._target_date, width=11,
                 font=('Consolas', 9)).pack(side='left', padx=(4, 2))
        tk.Label(dt_frame, text='  ').pack(side='left')
        # Time HH:MM:SS
        self._target_time = tk.StringVar(value='10:00:00')
        tk.Entry(dt_frame, textvariable=self._target_time, width=9,
                 font=('Consolas', 9)).pack(side='left', padx=(0, 4))
        tk.Label(dt_frame, text='(YYYY-MM-DD  HH:MM:SS)',
                 fg='gray', font=('', 7)).pack(side='left')

        # Interval
        intv_frame = tk.Frame(right)
        intv_frame.grid(row=10, column=0, columnspan=2, sticky='w', padx=16, pady=(0, 4))
        tk.Label(intv_frame, text='Reload moi:', font=('', 8)).pack(side='left')
        self._interval_var = tk.StringVar(value='5')
        tk.Entry(intv_frame, textvariable=self._interval_var, width=4,
                 font=('Consolas', 9)).pack(side='left', padx=4)
        tk.Label(intv_frame, text='giay', font=('', 8)).pack(side='left')

        # Sniper status label
        self._snipe_status = tk.Label(right, text='', fg='#c0392b',
                                      font=('', 8), wraplength=220, justify='left')
        self._snipe_status.grid(row=11, column=0, columnspan=2,
                                sticky='w', padx=8, pady=(4, 2))

        # Tat widgets datetime khi khong dung
        self._dt_frame   = dt_frame
        self._intv_frame = intv_frame
        self._on_mode_change()

        # Hint
        tk.Label(right,
            text='Tip:\n- Neu co URL san pham cu the → nhap vao o URL\n'
                 '- Neu chi co tu khoa → nhap Keyword\n'
                 '  Bot se search va chon ket qua dau tien\n\n'
                 'Bot dung the tin dung da luu san trong\ntai khoan Rakuten.',
            justify='left', fg='gray', font=('', 8)).grid(
            row=12, column=0, columnspan=2, sticky='w', padx=8, pady=4)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _refresh(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for i, a in enumerate(self._accounts, 1):
            s = a.get('status', 'Cho')
            self.tree.insert('', 'end',
                             values=(i, a['rakuten_id'], s, a.get('note', '')),
                             tags=(s,))

    def set_status(self, rakuten_id, status, note=''):
        for a in self._accounts:
            if a['rakuten_id'] == rakuten_id:
                a['status'] = status
                if note: a['note'] = note
        self.after(0, self._refresh)

    def _sel_idx(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def _add(self):
        dlg = RakutenAccountDialog(self)
        if dlg.result:
            dlg.result.update({'status': 'Cho', 'note': ''})
            self._accounts.append(dlg.result)
            self._save(); self._refresh()

    def _edit(self):
        idx = self._sel_idx()
        if idx is None: return
        dlg = RakutenAccountDialog(self, self._accounts[idx])
        if dlg.result:
            dlg.result['status'] = self._accounts[idx].get('status', 'Cho')
            dlg.result['note']   = self._accounts[idx].get('note', '')
            self._accounts[idx]  = dlg.result
            self._save(); self._refresh()

    def _delete(self):
        idx = self._sel_idx()
        if idx is None: return
        if messagebox.askyesno('Xoa', f'Xoa: {self._accounts[idx]["rakuten_id"]}?'):
            self._accounts.pop(idx); self._save(); self._refresh()

    def _reset(self):
        for a in self._accounts:
            if a.get('status') in ('That bai', 'Loi'):
                a['status'] = 'Cho'; a['note'] = ''
        self._save(); self._refresh()

    def _import_txt(self):
        """
        Import tu file TXT/CSV.
        Dinh dang: rakuten_id,rakuten_password
        """
        path = filedialog.askopenfilename(
            filetypes=[('Text/CSV', '*.txt *.csv'), ('All', '*.*')])
        if not path: return
        existing = {a['rakuten_id'] for a in self._accounts}
        added = 0
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) < 1: continue
                    a = {
                        'rakuten_id':       parts[0],
                        'rakuten_password': parts[1] if len(parts) > 1 else '',
                        'status': 'Cho', 'note': '',
                    }
                    if a['rakuten_id'] and a['rakuten_id'] not in existing:
                        self._accounts.append(a); added += 1
            self._save(); self._refresh()
            messagebox.showinfo('Import', f'Da them {added} tai khoan Rakuten.')
        except Exception as e:
            messagebox.showerror('Loi', str(e))

    # ── Load / Save ────────────────────────────────────────────────────────────
    def _load(self):
        if not os.path.exists(RAKUTEN_ACCOUNTS_FILE): return
        try:
            with open(RAKUTEN_ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                self._accounts = json.load(f)
            for a in self._accounts:
                a.setdefault('status', 'Cho')
                a.setdefault('note', '')
            self._refresh()
        except Exception:
            pass

    def _save(self):
        with open(RAKUTEN_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._accounts, f, ensure_ascii=False, indent=2)

    def get_pending(self):
        return [a for a in self._accounts if a.get('status') not in ('Thanh cong',)]

    def _on_mode_change(self):
        mode = self._snipe_mode.get()
        state = 'normal' if mode in ('snipe',) else 'disabled'
        for child in self._dt_frame.winfo_children():
            try: child.config(state=state)
            except Exception: pass
        intv_state = 'normal' if mode in ('monitor', 'snipe') else 'disabled'
        for child in self._intv_frame.winfo_children():
            try: child.config(state=intv_state)
            except Exception: pass

    def update_snipe_status(self, msg):
        self._snipe_status.config(text=msg)

    def get_product_config(self):
        return {
            'keyword':             self._keyword_var.get().strip(),
            'product_url':         self._url_var.get().strip(),
            'quantity':            int(self._quantity_var.get() or '1'),
            'auto_select_variant': self._auto_var.get(),
        }

    def get_max_concurrent(self):
        return max(1, self._max_concurrent.get())

    def update_progress(self, done, total, success):
        self.progress_lbl.config(
            text=f'[{done}/{total}]  OK:{success}  Loi:{done-success}')

    def get_sniper_config(self):
        mode = self._snipe_mode.get()
        cfg  = {'mode': mode, 'monitor_interval': int(self._interval_var.get() or '5')}
        if mode == 'snipe':
            date_str = self._target_date.get().strip()
            time_str = self._target_time.get().strip()
            try:
                cfg['target_datetime'] = datetime.strptime(
                    f'{date_str} {time_str}', '%Y-%m-%d %H:%M:%S')
            except ValueError as e:
                raise ValueError(f'Sai dinh dang gio mo ban: {e}')
        return cfg

    def save_file(self):
        self._save()


# ── Dialog: Them/Sua Email trong pool ────────────────────────────────────────
class EmailPoolDialog(tk.Toplevel):
    def __init__(self, parent, entry=None):
        super().__init__(parent)
        self.title('Them Email' if entry is None else 'Sua Email')
        self.resizable(False, False)
        self.result = None

        tk.Label(self, text='Gmail:', font=('', 9)).grid(
            row=0, column=0, padx=10, pady=8, sticky='e')
        self._email = tk.StringVar(value=entry.get('email', '') if entry else '')
        tk.Entry(self, textvariable=self._email, width=36,
                 font=('Consolas', 9)).grid(row=0, column=1, padx=(2, 10), pady=8)

        tk.Label(self, text='App Password:', font=('', 9)).grid(
            row=1, column=0, padx=10, pady=8, sticky='e')
        self._pass = tk.StringVar(value=entry.get('app_pass', '') if entry else '')
        self._pass_entry = tk.Entry(self, textvariable=self._pass, width=36,
                                    show='*', font=('Consolas', 9))
        self._pass_entry.grid(row=1, column=1, padx=(2, 10), pady=8)

        tk.Label(self, text='Prefix alias (tuy chon):', font=('', 9)).grid(
            row=2, column=0, padx=10, pady=8, sticky='e')
        self._prefix = tk.StringVar(value=entry.get('prefix', 'raku') if entry else 'raku')
        tk.Entry(self, textvariable=self._prefix, width=14,
                 font=('Consolas', 9)).grid(row=2, column=1, padx=(2, 10),
                                            pady=8, sticky='w')
        tk.Label(self, text='user+PREFIX001@gmail.com',
                 fg='gray', font=('', 7)).grid(row=2, column=1, sticky='e', padx=10)

        show_btn = tk.Button(self, text='Hien/An password',
                             command=self._toggle)
        show_btn.grid(row=3, column=1, sticky='w', padx=2, pady=(0, 4))

        tk.Label(self, text='Luu y: Bat App Password trong Google Account truoc.',
                 fg='#c0392b', font=('', 7)).grid(
            row=4, column=0, columnspan=2, padx=10, pady=(0, 6), sticky='w')

        bf = tk.Frame(self)
        bf.grid(row=5, column=0, columnspan=2, pady=8)
        tk.Button(bf, text='Luu', width=10, bg='#27ae60', fg='white',
                  command=self._save).pack(side='left', padx=4)
        tk.Button(bf, text='Huy', width=10, command=self.destroy).pack(side='left', padx=4)
        self.grab_set()
        self.wait_window()

    def _toggle(self):
        self._pass_entry.config(
            show='' if self._pass_entry.cget('show') == '*' else '*')

    def _save(self):
        e = self._email.get().strip()
        p = self._pass.get().strip()
        x = self._prefix.get().strip() or 'raku'
        if not e or '@' not in e:
            messagebox.showwarning('', 'Gmail khong hop le!', parent=self); return
        if not p:
            messagebox.showwarning('', 'App Password khong duoc de trong!', parent=self); return
        self.result = {'email': e, 'app_pass': p, 'prefix': x}
        self.destroy()


# ── Tab: Rakuten Dang ky ──────────────────────────────────────────────────────
class RakutenRegTab(tk.Frame):
    COLS = ('#', 'Email', 'Ho Ten', 'Password', 'Trang thai', 'Ghi chu')

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app      = app
        self._accounts: list[dict] = []
        self._pool:     list[dict] = []   # [{email, app_pass, prefix}, ...]
        self._build()
        self._load()
        self._load_pool()

    # ── Build UI ───────────────────────────────────────────────────────────────
    def _build(self):
        # ── Toolbar ────────────────────────────────────────────────────────
        tb = tk.Frame(self, bd=1, relief='raised')
        tb.pack(fill='x')
        tk.Button(tb, text='+ Tao account',
                  command=self._gen_accounts).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Xoa chon',
                  command=self._delete).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Xoa done',
                  command=self._delete_done).pack(side='left', padx=2, pady=3)
        tk.Button(tb, text='Reset that bai',
                  command=self._reset_failed).pack(side='left', padx=6, pady=3)
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=6)
        self.run_btn = tk.Button(tb, text='▶  DANG KY',
                                 bg='#8e44ad', fg='white', font=('', 10, 'bold'),
                                 command=self.app.start_rakuten_reg_bot)
        self.run_btn.pack(side='left', padx=4, pady=3)
        self.verify_btn = tk.Button(tb, text='✓  VERIFY LOGIN',
                                    bg='#27ae60', fg='white', font=('', 10, 'bold'),
                                    command=self.app.start_rakuten_verify_bot)
        self.verify_btn.pack(side='left', padx=2, pady=3)
        self.stop_btn = tk.Button(tb, text='■  DUNG',
                                  bg='#e74c3c', fg='white', font=('', 10, 'bold'),
                                  command=self.app.stop_rakuten_reg_bot, state='disabled')
        self.stop_btn.pack(side='left', padx=2, pady=3)
        ttk.Separator(tb, orient='vertical').pack(side='left', fill='y', padx=6)
        tk.Label(tb, text='Song song:').pack(side='left', padx=(0, 2))
        self._max_concurrent = tk.IntVar(value=1)
        ttk.Spinbox(tb, from_=1, to=10, textvariable=self._max_concurrent,
                    width=3, font=('Consolas', 9)).pack(side='left', padx=(0, 4))
        self.status_lbl = tk.Label(tb, text='San sang', fg='gray')
        self.status_lbl.pack(side='right', padx=10)
        self.progress_lbl = tk.Label(tb, text='', fg='#8e44ad', font=('', 8, 'bold'))
        self.progress_lbl.pack(side='right', padx=6)

        # ── Body: Pool (trai) + Config (giua) + Bang TK (phai) ────────────
        body = tk.Frame(self)
        body.pack(fill='both', expand=True)

        # ── LEFT: Email Pool ────────────────────────────────────────────────
        pool_frame = tk.LabelFrame(body, text='  Email Pool  ',
                                   font=('', 9, 'bold'), fg='#2980b9')
        pool_frame.pack(side='left', fill='y', padx=(4, 0), pady=4, ipadx=2, ipady=2)

        pool_tb = tk.Frame(pool_frame)
        pool_tb.pack(fill='x')
        tk.Button(pool_tb, text='+ Them', font=('', 8),
                  command=self._pool_add).pack(side='left', padx=2, pady=2)
        tk.Button(pool_tb, text='Sua', font=('', 8),
                  command=self._pool_edit).pack(side='left', padx=2, pady=2)
        tk.Button(pool_tb, text='Xoa', font=('', 8),
                  command=self._pool_delete).pack(side='left', padx=2, pady=2)

        pool_cols = ('Gmail', 'Prefix')
        self.pool_tree = ttk.Treeview(pool_frame, columns=pool_cols,
                                      show='headings', height=8, selectmode='browse')
        self.pool_tree.heading('Gmail',  text='Gmail')
        self.pool_tree.heading('Prefix', text='Prefix')
        self.pool_tree.column('Gmail',  width=190)
        self.pool_tree.column('Prefix', width=55, stretch=False)
        pool_vsb = ttk.Scrollbar(pool_frame, orient='vertical',
                                  command=self.pool_tree.yview)
        self.pool_tree.configure(yscrollcommand=pool_vsb.set)
        self.pool_tree.pack(side='left', fill='both', expand=True, padx=(2, 0), pady=2)
        pool_vsb.pack(side='left', fill='y', pady=2)

        pool_hint = tk.Label(pool_frame,
            text='OTP gui ve alias:\nuser+PREFIX001@gmail.com\n'
                 'Moi email duoc phan bo deu\nkhi tao account.',
            justify='left', fg='gray', font=('', 7))
        pool_hint.pack(anchor='w', padx=6, pady=(2, 4))

        # ── MIDDLE: Cau hinh sinh account ──────────────────────────────────
        mid = tk.LabelFrame(body, text='  Cau hinh sinh account  ',
                            font=('', 9, 'bold'))
        mid.pack(side='left', fill='y', padx=6, pady=4, ipadx=6, ipady=4)

        def _row(lbl, var, r, w=16, show=''):
            tk.Label(mid, text=lbl, anchor='e').grid(
                row=r, column=0, sticky='e', padx=(8, 2), pady=5)
            tk.Entry(mid, textvariable=var, width=w, show=show,
                     font=('Consolas', 9)).grid(
                row=r, column=1, padx=(0, 8), pady=5, sticky='w')

        tk.Label(mid, text='So luong tao:', anchor='e').grid(
            row=0, column=0, sticky='e', padx=(8, 2), pady=5)
        self._gen_count = tk.IntVar(value=10)
        ttk.Spinbox(mid, from_=1, to=500, textvariable=self._gen_count,
                    width=6, font=('Consolas', 9)).grid(
            row=0, column=1, padx=(0, 8), pady=5, sticky='w')

        # Seed Key cho ma tran mat khau
        tk.Label(mid, text='Seed Key (ma tran):', anchor='e').grid(
            row=1, column=0, sticky='e', padx=(8, 2), pady=5)
        self._seed_key = tk.StringVar(value='PTO2026')
        seed_entry = tk.Entry(mid, textvariable=self._seed_key, width=16,
                              font=('Consolas', 9))
        seed_entry.grid(row=1, column=1, padx=(0, 8), pady=5, sticky='w')

        tk.Label(mid, text='(doi seed → bo mat khau\nhoan toan khac nhau)',
                 fg='gray', font=('', 7), justify='left').grid(
            row=2, column=0, columnspan=2, sticky='w', padx=8, pady=(0, 6))

        # Preview mat khau ma tran
        tk.Label(mid, text='Preview mat khau:', font=('', 8, 'bold')).grid(
            row=3, column=0, columnspan=2, sticky='w', padx=8, pady=(4, 0))
        self._preview_text = tk.Text(mid, height=6, width=22, state='disabled',
                                     font=('Consolas', 8), bg='#f8f8f8')
        self._preview_text.grid(row=4, column=0, columnspan=2,
                                padx=8, pady=(0, 4), sticky='w')
        tk.Button(mid, text='Xem truoc mat khau',
                  font=('', 8), command=self._preview_pwd).grid(
            row=5, column=0, columnspan=2, padx=8, pady=2)

        ttk.Separator(mid, orient='horizontal').grid(
            row=6, column=0, columnspan=2, sticky='ew', pady=6)

        # ── Vision AI CAPTCHA config ─────────────────────────────────────────
        tk.Label(mid, text='Vision AI (CAPTCHA):', font=('', 8, 'bold'),
                 fg='#8e44ad').grid(row=7, column=0, columnspan=2,
                                    sticky='w', padx=8, pady=(4, 0))

        tk.Label(mid, text='Provider:', anchor='e').grid(
            row=8, column=0, sticky='e', padx=(8, 2), pady=2)
        self._vision_provider = tk.StringVar(value='gemini')
        ttk.Combobox(mid, textvariable=self._vision_provider,
                     values=['gemini', 'openai'], state='readonly',
                     width=8).grid(row=8, column=1, sticky='w', padx=(0, 8), pady=2)

        tk.Label(mid, text='API Key:', anchor='e').grid(
            row=9, column=0, sticky='e', padx=(8, 2), pady=2)
        self._vision_api_key = tk.StringVar()
        tk.Entry(mid, textvariable=self._vision_api_key, width=16,
                 show='*', font=('Consolas', 8)).grid(
            row=9, column=1, sticky='w', padx=(0, 8), pady=2)

        tk.Button(mid, text='Luu API Key',
                  font=('', 8), command=self._save_vision_config).grid(
            row=10, column=0, columnspan=2, padx=8, pady=(2, 4), sticky='ew')

        # Load key hien tai
        self._load_vision_config()

        ttk.Separator(mid, orient='horizontal').grid(
            row=11, column=0, columnspan=2, sticky='ew', pady=6)

        tk.Button(mid, text='⚡  TAO ACCOUNT',
                  bg='#8e44ad', fg='white', font=('', 10, 'bold'),
                  command=self._gen_accounts).grid(
            row=12, column=0, columnspan=2, padx=8, pady=4, sticky='ew')

        tk.Label(mid, text='(Luu vao rakuten_reg_accounts.json)',
                 fg='gray', font=('', 7)).grid(
            row=8, column=0, columnspan=2, padx=8, pady=(0, 4))

        # Seed key thay doi -> cap nhat preview
        self._seed_key.trace_add('write', lambda *_: self.after(200, self._preview_pwd))

        # ── RIGHT: Bang tai khoan ───────────────────────────────────────────
        right = tk.Frame(body)
        right.pack(side='left', fill='both', expand=True, pady=4, padx=(0, 4))

        tk.Label(right, text='Danh sach account dang ky',
                 font=('', 9, 'bold')).pack(anchor='w', padx=6, pady=(4, 0))
        tf = tk.Frame(right)
        tf.pack(fill='both', expand=True, padx=4, pady=4)
        self.tree = ttk.Treeview(tf, columns=self.COLS,
                                 show='headings', selectmode='browse')
        for col, w, stretch in [
            ('#',          32,  False),
            ('Email',      240, False),
            ('Ho Ten',     120, False),
            ('Password',   115, False),
            ('Trang thai', 75,  False),
            ('Ghi chu',    240, True),
        ]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, stretch=stretch)
        vsb = ttk.Scrollbar(tf, orient='vertical',   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)
        for tag, color in STATUS_COLORS_REG.items():
            self.tree.tag_configure(tag, foreground=color)

    # ── Email Pool CRUD ────────────────────────────────────────────────────────
    def _pool_refresh(self):
        for r in self.pool_tree.get_children():
            self.pool_tree.delete(r)
        for p in self._pool:
            self.pool_tree.insert('', 'end', values=(p['email'], p.get('prefix', 'raku')))

    def _pool_sel(self):
        sel = self.pool_tree.selection()
        return self.pool_tree.index(sel[0]) if sel else None

    def _pool_add(self):
        dlg = EmailPoolDialog(self)
        if dlg.result:
            self._pool.append(dlg.result)
            self._save_pool(); self._pool_refresh()

    def _pool_edit(self):
        idx = self._pool_sel()
        if idx is None: return
        dlg = EmailPoolDialog(self, self._pool[idx])
        if dlg.result:
            self._pool[idx] = dlg.result
            self._save_pool(); self._pool_refresh()

    def _pool_delete(self):
        idx = self._pool_sel()
        if idx is None: return
        e = self._pool[idx]['email']
        if messagebox.askyesno('Xoa', f'Xoa {e} khoi pool?'):
            self._pool.pop(idx); self._save_pool(); self._pool_refresh()

    # ── Preview mat khau ───────────────────────────────────────────────────────
    def _preview_pwd(self):
        seed = self._seed_key.get().strip() or 'PTO2026'
        lines = [f'#{n:03d}: {gen_matrix_password(n, seed)}' for n in range(1, 7)]
        self._preview_text.config(state='normal')
        self._preview_text.delete('1.0', 'end')
        self._preview_text.insert('end', '\n'.join(lines))
        self._preview_text.config(state='disabled')

    def _load_vision_config(self):
        """Load API key hien tai tu captcha_config.json."""
        try:
            p = Path('captcha_config.json')
            if p.exists():
                cfg = json.loads(p.read_text(encoding='utf-8'))
                self._vision_provider.set(cfg.get('provider', 'gemini'))
                key = cfg.get('gemini_api_key', '') or cfg.get('openai_api_key', '')
                self._vision_api_key.set(key)
        except Exception:
            pass

    def _save_vision_config(self):
        """Luu API key vao captcha_config.json."""
        provider = self._vision_provider.get()
        key      = self._vision_api_key.get().strip()
        if not key:
            messagebox.showwarning('', 'Chua nhap API Key!'); return
        cfg = {
            'provider': provider,
            'gemini_api_key':  key if provider == 'gemini'  else '',
            'openai_api_key':  key if provider == 'openai'  else '',
            'openai_model':    'gpt-4o-mini',
        }
        Path('captcha_config.json').write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8'
        )
        messagebox.showinfo('', f'Da luu API Key ({provider})!\n\nBot se tu dong giai CAPTCHA bang Vision AI.')

    # ── Refresh bang account ───────────────────────────────────────────────────
    def _refresh(self):
        for r in self.tree.get_children():
            self.tree.delete(r)
        for acc in self._accounts:
            name = f"{acc.get('last_kanji','')} {acc.get('first_kanji','')}"
            s    = acc.get('status', 'pending')
            self.tree.insert('', 'end', values=(
                acc['n'], acc['email'], name,
                acc.get('password', ''), s, acc.get('note', '')
            ), tags=(s,))
        pending    = sum(1 for a in self._accounts if a.get('status') == 'pending')
        done       = sum(1 for a in self._accounts if a.get('status') == 'done')
        verified   = sum(1 for a in self._accounts if a.get('status') == 'verified')
        failed     = sum(1 for a in self._accounts if a.get('status') == 'failed')
        login_fail = sum(1 for a in self._accounts if a.get('status') == 'login_fail')
        self.progress_lbl.config(
            text=f'Tong: {len(self._accounts)}  |  '
                 f'Pending:{pending}  Done:{done}  Verified:{verified}  '
                 f'Failed:{failed}  LoginFail:{login_fail}')

    def set_status(self, n: int, status: str, note: str = ''):
        for acc in self._accounts:
            if acc['n'] == n:
                acc['status'] = status
                if note: acc['note'] = note
        self._save()
        self.after(0, self._refresh)

    def _sel_idx(self):
        sel = self.tree.selection()
        return self.tree.index(sel[0]) if sel else None

    # ── Generate accounts ──────────────────────────────────────────────────────
    def _gen_accounts(self):
        import re as _re
        from data_gen import generate_japanese_profile

        pool  = self._pool
        count = self._gen_count.get()
        seed  = self._seed_key.get().strip() or 'PTO2026'

        if not pool:
            messagebox.showwarning(
                '', 'Chua co Email nao trong Pool!\n'
                    'Bam "+ Them" trong Email Pool de them Gmail + App Password.')
            return

        # Tim so thu tu (n) lon nhat hien co de tiep tuc
        existing_nums = set()
        for acc in self._accounts:
            existing_nums.add(acc.get('n', 0))

        added  = 0
        n      = max(existing_nums, default=0) + 1
        pool_i = 0   # phan bo xoay vong qua cac email trong pool

        while added < count:
            while n in existing_nums:
                n += 1

            # Chon email tu pool theo vong tron
            ep     = pool[pool_i % len(pool)]
            prefix = ep.get('prefix', 'raku')
            local, domain = ep['email'].split('@', 1)
            alias  = f"{local}+{prefix}{n:03d}@{domain}"

            profile = generate_japanese_profile()
            pwd     = gen_matrix_password(n, seed)   # ← MA TRAN

            acc = {
                'n':           n,
                'email':       alias,
                'email_pass':  ep['app_pass'],
                'password':    pwd,
                'seed':        seed,
                'last_kanji':  profile['full_name'].split()[0],
                'first_kanji': profile['full_name'].split()[-1],
                'last_kana':   profile['full_kana'].split()[0],
                'first_kana':  profile['full_kana'].split()[-1],
                'birthday':    (f"{profile['birthday_year']}-"
                                f"{profile['birthday_month']}-"
                                f"{profile['birthday_day']}"),
                'gender':      profile['gender'],
                'phone':       profile['phone_gen'],
                'postal_code': profile['postal_code'],
                'prefecture':  profile['prefecture'],
                'city':        profile['city'],
                'street':      profile['street'],
                'building':    profile.get('building', ''),
                'status':      'pending',
                'rakuten_id':  '',
                'note':        '',
            }
            self._accounts.append(acc)
            existing_nums.add(n)
            added  += 1
            pool_i += 1
            n      += 1

        self._accounts.sort(key=lambda x: x['n'])
        self._save(); self._refresh()
        messagebox.showinfo(
            'Tao account',
            f'Da tao {added} account (seed: {seed}).\n'
            f'Tong: {len(self._accounts)} account.')

    def _delete(self):
        idx = self._sel_idx()
        if idx is None: return
        acc = self._accounts[idx]
        if messagebox.askyesno('Xoa', f'Xoa #{acc["n"]}: {acc["email"]}?'):
            self._accounts.pop(idx); self._save(); self._refresh()

    def _delete_done(self):
        before = len(self._accounts)
        self._accounts = [a for a in self._accounts if a.get('status') != 'done']
        self._save(); self._refresh()
        messagebox.showinfo('', f'Da xoa {before - len(self._accounts)} account done.')

    def _reset_failed(self):
        for acc in self._accounts:
            if acc.get('status') == 'failed':
                acc['status'] = 'pending'; acc['note'] = ''
        self._save(); self._refresh()

    # ── Load / Save ────────────────────────────────────────────────────────────
    def _load(self):
        if not os.path.exists(RAKUTEN_REG_FILE): return
        try:
            with open(RAKUTEN_REG_FILE, 'r', encoding='utf-8') as f:
                self._accounts = json.load(f)
            for acc in self._accounts:
                acc.setdefault('status', 'pending')
                acc.setdefault('note', '')
                acc.setdefault('rakuten_id', '')
            self._refresh()
        except Exception:
            pass

    def _save(self):
        with open(RAKUTEN_REG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._accounts, f, ensure_ascii=False, indent=2)

    def _load_pool(self):
        if not os.path.exists(EMAIL_POOL_FILE): return
        try:
            with open(EMAIL_POOL_FILE, 'r', encoding='utf-8') as f:
                self._pool = json.load(f)
            self._pool_refresh()
            self._preview_pwd()
        except Exception:
            pass

    def _save_pool(self):
        with open(EMAIL_POOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(self._pool, f, ensure_ascii=False, indent=2)

    def get_pending(self) -> list[dict]:
        """Tra ve cac account chua dang ky (pending hoac failed)."""
        return [a for a in self._accounts
                if a.get('status') in ('pending', 'failed')]

    def get_max_concurrent(self) -> int:
        return max(1, self._max_concurrent.get())


# ── App chinh ─────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PTO Bot')
        self.geometry('1020x680')
        self.resizable(True, True)
        self._running = False
        self._build()
        self._poll()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=4, pady=(4, 2))
        self.acc_tab        = AccountTab(nb, self)
        self.addr_tab       = AddressTab(nb)
        self.rakuten_tab    = RakutenTab(nb, self)
        self.rakuten_reg_tab = RakutenRegTab(nb, self)
        nb.add(self.acc_tab,         text='  PokemonCenter  ')
        nb.add(self.addr_tab,        text='  Dia chi Nhat Ban  ')
        nb.add(self.rakuten_tab,     text='  Rakuten Orders  ')
        nb.add(self.rakuten_reg_tab, text='  Rakuten Dang ky  ')

        log_frame = tk.LabelFrame(self, text='Log hoat dong')
        log_frame.pack(fill='x', padx=4, pady=(0, 4))
        self.log_text = tk.Text(log_frame, height=10, state='disabled',
                                font=('Consolas', 9), bg='#1e1e1e', fg='#d4d4d4', wrap='none')
        vsb = ttk.Scrollbar(log_frame, orient='vertical',   command=self.log_text.yview)
        hsb = ttk.Scrollbar(log_frame, orient='horizontal', command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side='bottom', fill='x')
        vsb.pack(side='right',  fill='y')
        self.log_text.pack(fill='both', expand=True)

        handler = GUILogHandler(self.log_text)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    # ── Bot ───────────────────────────────────────────────────────────────────
    def start_bot(self):
        pending    = self.acc_tab.get_pending()
        registered = self.acc_tab.get_registered()

        if not pending and not registered:
            messagebox.showinfo('', 'Khong co tai khoan nao can chay.'); return

        lines = []
        if pending:
            lines.append(f'• {len(pending)} tai khoan se DANG KY')
        if registered:
            lines.append(f'• {len(registered)} tai khoan da dang ky se tu dong DANG NHAP')

        no_url = [a['email'] for a in pending if not a.get('reg_url')]
        if no_url:
            lines.append(
                f'\nLuu y: {len(no_url)} tai khoan chua co URL dang ky se bi bo qua:\n' +
                '\n'.join(no_url[:5]) + ('\n...' if len(no_url) > 5 else '')
            )

        if not messagebox.askyesno('Xac nhan', '\n'.join(lines) + '\n\nTiep tuc?'):
            return

        self._running = True
        self.acc_tab.run_btn.config(state='disabled')
        self.acc_tab.stop_btn.config(state='normal')
        self.acc_tab.status_lbl.config(text='Dang chay...', fg='#f39c12')
        threading.Thread(
            target=self._worker, args=(pending, registered), daemon=True
        ).start()

    def _worker(self, pending, registered):
        import time
        from browser import create_browser_context
        from playwright_stealth import Stealth
        from data_gen import generate_japanese_profile
        from tasks_pokecen import (PIPELINE_URL_ONLY, PIPELINE_LOGIN,
                                   PIPELINE_LOGIN_SMART, task_login_pokecen,
                                   task_save_session)

        # ── Giai doan 1: Dang ky cac tai khoan chua co ─────────────────────
        reg_total   = len(pending)
        reg_success = 0
        reg_skipped = 0

        if pending:
            logging.info(f'[BOT] ===== GIAI DOAN 1: DANG KY ({reg_total} tai khoan) =====')

        for i, entry in enumerate(pending, 1):
            if not self._running:
                logging.info('Bot da dung.')
                break

            url = entry.get('reg_url', '').strip()
            if not url:
                logging.warning(f'[{i}/{reg_total}] Bo qua (chua co URL): {entry["email"]}')
                self.acc_tab.set_status(entry['email'], 'That bai', 'Chua co URL dang ky')
                reg_skipped += 1
                continue

            profile = generate_japanese_profile()
            pwd = entry.get('pto_password', '').strip() or PASSWORD
            account = {
                **profile,
                'email':          entry['email'],
                'email_password': entry.get('email_password', ''),
                'phone':          entry.get('phone', ''),
                'reg_url':        url,
                'password':       pwd,
                'otp_req_q':      otp_req_q,
                'otp_res_q':      otp_res_q,
            }

            logging.info(f'{"="*55}')
            logging.info(f'[DK {i}/{reg_total}] {account["email"]}')
            logging.info(f'  URL: {url[:70]}...' if len(url) > 70 else f'  URL: {url}')
            self.acc_tab.set_status(account['email'], 'Dang chay')

            pw, browser, ctx = create_browser_context(proxy=None)
            page = ctx.new_page()
            Stealth().apply_stealth_sync(page)
            ok = False
            err_note = ''
            try:
                for task_fn in PIPELINE_URL_ONLY:
                    if 'fill_regform' in task_fn.__name__:
                        self.acc_tab.set_status(account['email'], 'Dien form')
                    logging.info(f'  >> {task_fn.__name__}')
                    task_fn(page, ctx, account)
                ok = True
            except Exception as e:
                err_note = str(e)[:80]
                logging.error(f'  !! {e}')
                try:
                    page.screenshot(path=f'err_{entry["email"].split("@")[0]}.png')
                except Exception:
                    pass
            finally:
                try: browser.close()
                except Exception: pass
                try: pw.stop()
                except Exception: pass

            if ok:
                entry['pto_password']    = account['password']
                entry['birthday_year']   = account.get('birthday_year', '')
                entry['birthday_month']  = account.get('birthday_month', '')
                entry['birthday_day']    = account.get('birthday_day', '')
                save_account({'email': account['email'], 'password': account['password']})
                self.acc_tab.set_status(account['email'], 'Thanh cong', 'Dang ky thanh cong!')
                # Them vao danh sach se dang nhap ngay sau
                registered.append(entry)
                reg_success += 1
                logging.info(f'  [OK] {account["email"]}')
            else:
                self.acc_tab.set_status(account['email'], 'That bai', err_note)

            self.acc_tab.save_file()

            if i < reg_total and self._running:
                logging.info('Nghi 10s truoc tai khoan tiep theo...')
                time.sleep(10)

        if pending:
            logging.info(
                f'[DK] Xong! Thanh cong: {reg_success} | '
                f'Bo qua: {reg_skipped} | That bai: {reg_total-reg_success-reg_skipped}'
            )

        # ── Giai doan 2: Tu dong dang nhap cac tai khoan da co mat khau ────
        login_accounts = registered
        login_total   = len(login_accounts)
        login_success = 0

        if not login_accounts:
            self.after(0, self._done)
            return

        logging.info(f'[BOT] ===== GIAI DOAN 2: DANG NHAP ({login_total} tai khoan) =====')

        for i, entry in enumerate(login_accounts, 1):
            if not self._running:
                logging.info('Bot da dung.')
                break

            logging.info(f'{"="*55}')
            logging.info(f'[DN {i}/{login_total}] {entry["email"]}')
            self.acc_tab.set_status(entry['email'], 'Dang nhap')

            login_pwd = entry.get('pto_password', '').strip() or PASSWORD
            account = {
                'email':          entry['email'],
                'password':       login_pwd,
                'email_password': entry.get('email_password', ''),
                'birthday_year':  entry.get('birthday_year', ''),
                'birthday_month': entry.get('birthday_month', ''),
                'birthday_day':   entry.get('birthday_day', ''),
                'otp_req_q':      otp_req_q,
                'otp_res_q':      otp_res_q,
            }

            MAX_RETRY = 5
            ok        = False
            err_note  = ''
            pw = browser = page = ctx = None

            for attempt in range(1, MAX_RETRY + 1):
                if not self._running:
                    break
                logging.info(f'  [Thu {attempt}/{MAX_RETRY}] {entry["email"]}')

                if browser:
                    try: browser.close()
                    except Exception: pass
                    try: pw.stop()
                    except Exception: pass
                    pw = browser = page = ctx = None

                try:
                    pw, browser, ctx = create_browser_context(proxy=None)
                    page = ctx.new_page()
                    Stealth().apply_stealth_sync(page)

                    # Thu session truoc
                    try:
                        for task_fn in PIPELINE_LOGIN_SMART:
                            logging.info(f'    >> {task_fn.__name__}')
                            task_fn(page, ctx, account)
                        ok = True
                    except Exception as se:
                        logging.info(f'    [Session] {se} -> form login...')
                        task_login_pokecen(page, ctx, account)
                        task_save_session(page, ctx, account)
                        ok = True

                    break

                except Exception as e:
                    err_note = str(e)[:160]
                    logging.error(f'  !! [Thu {attempt}] {e}')
                    try:
                        if page:
                            page.screenshot(path=f'login_err_{entry["email"].split("@")[0]}_t{attempt}.png')
                    except Exception:
                        pass

                    if attempt < MAX_RETRY and self._running:
                        wait_sec = attempt * 5
                        logging.info(f'  Nghi {wait_sec}s roi thu lai...')
                        time.sleep(wait_sec)

            if not ok and browser:
                try: browser.close()
                except Exception: pass
                try: pw.stop()
                except Exception: pass
                browser = pw = None

            if ok:
                # Neu vua reset mat khau, luu mat khau moi
                if account.get('password_reset_done'):
                    entry['pto_password'] = account['password']
                    self.acc_tab.save_file()
                    logging.info(f'  [PwReset] Da luu mat khau moi cho {entry["email"]}')

                self.acc_tab.set_status(entry['email'], 'Thanh cong', 'Dang nhap thanh cong!')
                login_success += 1
                logging.info(f'  [OK] Dang nhap: {entry["email"]}')

                # Dong browser (giai doan 2 tu dong, khong giu mo)
                if browser:
                    try: browser.close()
                    except Exception: pass
                if pw:
                    try: pw.stop()
                    except Exception: pass
            else:
                self.acc_tab.set_status(entry['email'], 'That bai', f'Loi sau {MAX_RETRY} lan: {err_note}')

            if i < login_total and self._running:
                logging.info('Nghi 5s truoc tai khoan tiep theo...')
                time.sleep(5)

        logging.info(f'[DN] Xong! Thanh cong: {login_success}/{login_total}')
        self.after(0, self._done)

    def _done(self):
        self._running = False
        self.acc_tab.run_btn.config(state='normal')
        self.acc_tab.stop_btn.config(state='disabled')
        self.acc_tab.status_lbl.config(text='Hoan thanh', fg='#27ae60')

    def stop_bot(self):
        self._running = False
        self.acc_tab.status_lbl.config(text='Dang dung...', fg='#e74c3c')

    # ── Login Bot ─────────────────────────────────────────────────────────────
    def start_login_bot(self):
        registered = self.acc_tab.get_registered()
        if not registered:
            messagebox.showinfo(
                '',
                'Khong co tai khoan nao co trang thai "Thanh cong".\n'
                'Hay chay CHAY BOT de dang ky truoc.'
            )
            return
        if not messagebox.askyesno(
            'Xac nhan',
            f'Se tu dong dang nhap {len(registered)} tai khoan da dang ky thanh cong.\nTiep tuc?'
        ):
            return

        self._login_running = True
        self.acc_tab.login_btn.config(state='disabled')
        self.acc_tab.login_stop_btn.config(state='normal')
        self.acc_tab.status_lbl.config(text='Dang nhap...', fg='#2980b9')
        threading.Thread(target=self._login_worker, args=(registered,), daemon=True).start()

    def inspect_login(self):
        """Mo browser, dump form login ra file de lay selector chinh xac."""
        if not messagebox.askyesno(
            'Inspect Login',
            'Bot se mo trang login, dump cac input/button ra file:\n'
            '  • login_form_dump.txt\n'
            '  • login_screenshot.png\n\n'
            'Sau do doc file de xem selector chinh xac.\nTiep tuc?'
        ):
            return
        threading.Thread(target=self._inspect_login_worker, daemon=True).start()

    def _inspect_login_worker(self):
        from browser import create_browser_context
        from playwright_stealth import Stealth
        from tasks_pokecen import PIPELINE_INSPECT_LOGIN
        logging.info('[Inspect] Mo trang login...')
        pw, browser, ctx = create_browser_context(proxy=None)
        page = ctx.new_page()
        Stealth().apply_stealth_sync(page)
        try:
            account = {'email': '', 'password': '', 'otp_req_q': otp_req_q, 'otp_res_q': otp_res_q}
            for task_fn in PIPELINE_INSPECT_LOGIN:
                task_fn(page, ctx, account)
            logging.info('[Inspect] Xong! Mo file login_form_dump.txt de xem ket qua.')
            self.after(0, lambda: messagebox.showinfo(
                'Inspect xong',
                'Da luu:\n  • login_form_dump.txt\n  • login_screenshot.png\n\n'
                'Mo file login_form_dump.txt (trong thu muc PTO) de xem selector.'
            ))
        except Exception as e:
            logging.error(f'[Inspect] Loi: {e}')
        finally:
            try: browser.close()
            except Exception: pass
            try: pw.stop()
            except Exception: pass

    def stop_login_bot(self):
        self._login_running = False
        self.acc_tab.status_lbl.config(text='Dang dung DN...', fg='#e74c3c')

    def _login_worker(self, accounts):
        import time
        from browser import create_browser_context
        from playwright_stealth import Stealth
        from tasks_pokecen import (PIPELINE_LOGIN_SMART, task_login_pokecen,
                                   task_save_session)

        total         = len(accounts)
        success       = 0
        open_browsers = []   # giu browser mo cho den khi user bam DUNG DN

        for i, entry in enumerate(accounts, 1):
            if not self._login_running:
                logging.info('[Login] Da dung.')
                break

            logging.info(f'{"="*55}')
            logging.info(f'[Login {i}/{total}] {entry["email"]}')
            self.acc_tab.set_status(entry['email'], 'Dang nhap')

            account = {
                'email':          entry['email'],
                'password':       entry.get('pto_password', '').strip() or PASSWORD,
                'email_password': entry.get('email_password', ''),
                'birthday_year':  entry.get('birthday_year', ''),
                'birthday_month': entry.get('birthday_month', ''),
                'birthday_day':   entry.get('birthday_day', ''),
                'otp_req_q':      otp_req_q,
                'otp_res_q':      otp_res_q,
            }

            pw = browser = page = ctx = None
            ok       = False
            err_note = ''
            try:
                pw, browser, ctx = create_browser_context(proxy=None)
                page = ctx.new_page()
                Stealth().apply_stealth_sync(page)

                # Thu session cookies truoc (nhanh, khong can form)
                try:
                    for task_fn in PIPELINE_LOGIN_SMART:
                        logging.info(f'  >> {task_fn.__name__}')
                        task_fn(page, ctx, account)
                    ok = True
                    logging.info(f'  [Session OK] {entry["email"]}')
                except Exception as session_err:
                    # Session het han / chua co -> dang nhap bang form 1 lan
                    logging.info(f'  [Session] {session_err} -> form login...')
                    task_login_pokecen(page, ctx, account)
                    task_save_session(page, ctx, account)
                    ok = True
                    logging.info(f'  [Form OK] {entry["email"]}')

            except Exception as e:
                err_note = str(e)[:160]
                logging.error(f'  !! {e}')
                try:
                    if page:
                        page.screenshot(path=f'login_err_{entry["email"].split("@")[0]}.png')
                except Exception:
                    pass
                if browser:
                    try: browser.close()
                    except Exception: pass
                if pw:
                    try: pw.stop()
                    except Exception: pass
                browser = pw = None

            if ok:
                # Luu mat khau moi neu vua reset
                if account.get('password_reset_done'):
                    entry['pto_password'] = account['password']
                    self.acc_tab.save_file()
                    logging.info(f'  [PwReset] Da luu mat khau moi cho {entry["email"]}')

                open_browsers.append((pw, browser, entry['email']))
                self.acc_tab.set_status(entry['email'], 'Thanh cong', 'Dang o trang chu')
                success += 1
            else:
                self.acc_tab.set_status(entry['email'], 'That bai', err_note[:80])

            if i < total and self._login_running:
                time.sleep(2)

        # Giu tat ca browser mo cho den khi user bam DUNG DN
        if open_browsers:
            logging.info(
                f'[Login] {len(open_browsers)} browser dang mo trang chu.'
                f' Bam [DUNG DN] de dong.'
            )
            self.after(0, lambda n=len(open_browsers): self.acc_tab.status_lbl.config(
                text=f'{n} browser dang mo - bam DUNG DN', fg='#27ae60'
            ))
            while self._login_running:
                time.sleep(1)
            logging.info('[Login] Dong tat ca browser...')
            for pw_i, browser_i, email_i in open_browsers:
                try:
                    browser_i.close()
                    logging.info(f'  Dong: {email_i}')
                except Exception:
                    pass
                try: pw_i.stop()
                except Exception: pass

        logging.info(f'[Login] Xong! Thanh cong: {success}/{total}')
        self.after(0, self._login_done)

    def _login_done(self):
        self._login_running = False
        self.acc_tab.login_btn.config(state='normal')
        self.acc_tab.login_stop_btn.config(state='disabled')
        self.acc_tab.status_lbl.config(text='Hoan thanh DN', fg='#27ae60')

    # ── Rakuten Bot ───────────────────────────────────────────────────────────
    def start_rakuten_bot(self):
        pending = self.rakuten_tab.get_pending()
        if not pending:
            messagebox.showinfo('', 'Khong co tai khoan Rakuten nao can chay.'); return
        cfg = self.rakuten_tab.get_product_config()
        if not cfg['product_url'] and not cfg['keyword']:
            messagebox.showwarning('', 'Hay nhap URL san pham hoac Keyword truoc khi chay!'); return
        try:
            sniper_cfg = self.rakuten_tab.get_sniper_config()
        except ValueError as e:
            messagebox.showerror('Loi gio mo ban', str(e)); return

        n      = len(pending)
        mode   = sniper_cfg['mode']
        maxcon = self.rakuten_tab.get_max_concurrent()

        # Xac nhan
        if mode == 'snipe':
            dt = sniper_cfg['target_datetime']
            msg = (f'{n} tai khoan se chay SONG SONG (toi da {maxcon} browser cung luc).\n\n'
                   f'Tat ca se:\n'
                   f'  1. Dang nhap + vao trang san pham\n'
                   f'  2. Cung nhau san hang luc: {dt.strftime("%Y-%m-%d %H:%M:%S")}\n\n'
                   f'Tiep tuc?')
        elif mode == 'monitor':
            msg = (f'{n} tai khoan se chay SONG SONG (toi da {maxcon} browser cung luc).\n'
                   f'Reload moi {sniper_cfg["monitor_interval"]}s, dat hang ngay khi phat hien nut mua.\n\nTiep tuc?')
        else:
            msg = (f'{n} tai khoan se chay SONG SONG (toi da {maxcon} browser cung luc).\n\nTiep tuc?')
        if not messagebox.askyesno('Xac nhan', msg):
            return

        self._rakuten_stop_event = threading.Event()
        self._rakuten_running    = True
        self.rakuten_tab.run_btn.config(state='disabled')
        self.rakuten_tab.stop_btn.config(state='normal')
        lbl = {'normal': 'Dang chay...', 'monitor': 'Dang theo doi...', 'snipe': 'Sniper san sang...'}.get(mode, 'Dang chay...')
        self.rakuten_tab.status_lbl.config(text=lbl, fg='#f39c12')
        self.rakuten_tab.update_progress(0, n, 0)
        threading.Thread(
            target=self._rakuten_worker,
            args=(pending, cfg, sniper_cfg, maxcon),
            daemon=True).start()

    def stop_rakuten_bot(self):
        self._rakuten_running = False
        if hasattr(self, '_rakuten_stop_event'):
            self._rakuten_stop_event.set()
        self.rakuten_tab.status_lbl.config(text='Dang dung...', fg='#e74c3c')

    def _rakuten_worker(self, accounts, cfg, sniper_cfg, max_concurrent):
        """
        Quan ly pool browser song song bang ThreadPoolExecutor.
        Moi tai khoan chay trong thread rieng, browser rieng, hoan toan doc lap.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from browser import create_browser_context
        from playwright_stealth import Stealth
        from tasks_rakuten import PIPELINE_RAKUTEN, PIPELINE_RAKUTEN_SNIPE

        mode     = sniper_cfg.get('mode', 'normal')
        pipeline = PIPELINE_RAKUTEN_SNIPE if mode in ('monitor', 'snipe') else PIPELINE_RAKUTEN
        total    = len(accounts)

        if mode == 'snipe':
            dt = sniper_cfg.get('target_datetime')
            logging.info(f'[Sniper] {total} tai khoan | Gio mo ban: {dt.strftime("%Y-%m-%d %H:%M:%S")} | Song song: {max_concurrent}')
        elif mode == 'monitor':
            logging.info(f'[Sniper] {total} tai khoan | Theo doi | Song song: {max_concurrent}')
        else:
            logging.info(f'[Rakuten] {total} tai khoan | Binh thuong | Song song: {max_concurrent}')

        done_count   = 0
        success_count = 0
        lock = threading.Lock()

        def _run_one(entry):
            """Xu ly mot tai khoan trong thread rieng."""
            nonlocal done_count, success_count

            rid = entry['rakuten_id']
            if not getattr(self, '_rakuten_running', False):
                return

            def _status_cb(msg):
                logging.info(f'  [{rid.split("@")[0]}] {msg}')
                self.rakuten_tab.after(0, self.rakuten_tab.update_snipe_status, msg)

            account = {
                'rakuten_id':          rid,
                'rakuten_password':    entry.get('rakuten_password', ''),
                'product_url':         cfg.get('product_url', ''),
                'keyword':             cfg.get('keyword', ''),
                'quantity':            cfg.get('quantity', 1),
                'auto_select_variant': cfg.get('auto_select_variant', True),
                'otp_req_q':           otp_req_q,
                'otp_res_q':           otp_res_q,
                'target_datetime':     sniper_cfg.get('target_datetime'),
                'monitor_interval':    sniper_cfg.get('monitor_interval', 5),
                'stop_event':          getattr(self, '_rakuten_stop_event', None),
                'status_cb':           _status_cb,
            }

            logging.info(f'[{rid.split("@")[0]}] Bat dau')
            self.rakuten_tab.set_status(rid, 'Dang chay')

            pw, browser, ctx = create_browser_context(proxy=None)
            page = ctx.new_page()
            Stealth().apply_stealth_sync(page)
            ok = False; err_note = ''
            try:
                status_map = {
                    'login':             'Dang nhap',
                    'find_product':      'Tim san pham',
                    'monitor_and_snipe': 'Dang san...',
                    'add_to_cart':       'Them gio hang',
                    'checkout':          'Thanh toan',
                    'place_order':       'Dat hang',
                }
                for task_fn in pipeline:
                    if not getattr(self, '_rakuten_running', False):
                        raise Exception('Dung boi nguoi dung')
                    for k, v in status_map.items():
                        if k in task_fn.__name__:
                            self.rakuten_tab.set_status(rid, v); break
                    logging.info(f'  [{rid.split("@")[0]}] >> {task_fn.__name__}')
                    task_fn(page, ctx, account)
                ok = True
            except Exception as e:
                err_note = str(e)[:80]
                logging.error(f'  [{rid.split("@")[0]}] !! {e}')
                try: page.screenshot(path=f'rakuten_err_{rid.split("@")[0]}.png')
                except Exception: pass
            finally:
                try: browser.close()
                except Exception: pass
                try: pw.stop()
                except Exception: pass

            with lock:
                done_count += 1
                if ok:
                    success_count += 1
                    triggered_at = account.get('snipe_triggered_at', '')
                    order_id     = account.get('order_id', '')
                    note = f'Don: {order_id}' if order_id else (f'OK luc {triggered_at}' if triggered_at else 'Dat hang OK!')
                    self.rakuten_tab.set_status(rid, 'Thanh cong', note)
                    logging.info(f'[{rid.split("@")[0]}] OK | {note}')
                else:
                    self.rakuten_tab.set_status(rid, 'That bai', err_note)
                d, s = done_count, success_count
            self.rakuten_tab.after(0, self.rakuten_tab.update_progress, d, total, s)
            self.rakuten_tab.save_file()

        # Chay song song
        with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(_run_one, entry): entry for entry in accounts}
            for fut in as_completed(futures):
                try: fut.result()
                except Exception as e:
                    logging.error(f'[Pool] Loi thread: {e}')

        logging.info(f'[Rakuten] Tat ca xong! Thanh cong: {success_count}/{total}')
        self.after(0, self._rakuten_done)

    def _rakuten_done(self):
        self._rakuten_running = False
        self.rakuten_tab.run_btn.config(state='normal')
        self.rakuten_tab.stop_btn.config(state='disabled')
        self.rakuten_tab.status_lbl.config(text='Hoan thanh', fg='#27ae60')
        self.rakuten_tab.update_snipe_status('')

    # ── Rakuten Dang ky Bot ───────────────────────────────────────────────────
    def start_rakuten_reg_bot(self):
        pending = self.rakuten_reg_tab.get_pending()
        if not pending:
            messagebox.showinfo('', 'Khong co account nao dang cho dang ky.\n'
                                    'Bam "+ Tao account" de tao them.'); return

        maxcon = self.rakuten_reg_tab.get_max_concurrent()
        if not messagebox.askyesno(
            'Xac nhan',
            f'Se dang ky {len(pending)} account Rakuten\n'
            f'(song song toi da {maxcon} browser).\n\nTiep tuc?'
        ): return

        self._reg_stop_event = threading.Event()
        self._reg_running    = True
        self.rakuten_reg_tab.run_btn.config(state='disabled')
        self.rakuten_reg_tab.verify_btn.config(state='disabled')
        self.rakuten_reg_tab.stop_btn.config(state='normal')
        self.rakuten_reg_tab.status_lbl.config(text='Dang dang ky...', fg='#8e44ad')
        threading.Thread(
            target=self._rakuten_reg_worker,
            args=(pending, maxcon, 'register'),
            daemon=True,
        ).start()

    def start_rakuten_verify_bot(self):
        """Verify login cho cac account da dang ky (status='done')."""
        import json
        from pathlib import Path
        data = json.loads(Path('rakuten_reg_accounts.json').read_text(encoding='utf-8')) \
               if Path('rakuten_reg_accounts.json').exists() else []
        # "verified" = da xac nhan OK -> khong test lai
        done_accs = [a for a in data if a.get('status') in ('done', 'login_fail')]
        if not done_accs:
            messagebox.showinfo('', 'Khong co account "done"/"login_fail" nao de verify.\n'
                                    '("verified" = da xac nhan OK, khong can test lai)\n'
                                    'Hay dang ky truoc.'); return

        maxcon = self.rakuten_reg_tab.get_max_concurrent()
        if not messagebox.askyesno(
            'Xac nhan',
            f'Se kiem tra dang nhap {len(done_accs)} account da dang ky.\n'
            f'(song song toi da {maxcon} browser).\n\nTiep tuc?'
        ): return

        self._reg_stop_event = threading.Event()
        self._reg_running    = True
        self.rakuten_reg_tab.run_btn.config(state='disabled')
        self.rakuten_reg_tab.verify_btn.config(state='disabled')
        self.rakuten_reg_tab.stop_btn.config(state='normal')
        self.rakuten_reg_tab.status_lbl.config(text='Dang verify login...', fg='#27ae60')
        threading.Thread(
            target=self._rakuten_reg_worker,
            args=(done_accs, maxcon, 'verify'),
            daemon=True,
        ).start()

    def stop_rakuten_reg_bot(self):
        self._reg_running = False
        if hasattr(self, '_reg_stop_event'):
            self._reg_stop_event.set()
        self.rakuten_reg_tab.status_lbl.config(text='Dang dung...', fg='#e74c3c')

    def _rakuten_reg_worker(self, accounts: list[dict], max_concurrent: int, mode: str):
        """
        Worker chung cho ca 'register' va 'verify'.
        mode = 'register' | 'verify'
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from playwright.sync_api import sync_playwright
        from tasks_rakuten_reg import register_one, verify_login_one

        total         = len(accounts)
        done_count    = 0
        success_count = 0
        lock          = threading.Lock()

        logging.info(f'[{mode.upper()}] Bat dau {total} account (song song: {max_concurrent})')

        def _run_one(acc: dict):
            nonlocal done_count, success_count
            n = acc['n']

            if not getattr(self, '_reg_running', False):
                return

            def _cb(msg):
                logging.info(msg)
            def _stopped():
                return not getattr(self, '_reg_running', False)

            # Hien thi trang thai dang chay
            if mode == 'register':
                self.rakuten_reg_tab.set_status(n, 'running', 'Dang dang ky...')
            else:
                self.rakuten_reg_tab.set_status(n, 'done', 'Dang verify login...')

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                try:
                    if mode == 'register':
                        success, note = register_one(acc, browser,
                                                     status_cb=_cb, stop_check=_stopped)
                    else:
                        success, note = verify_login_one(acc, browser,
                                                         status_cb=_cb, stop_check=_stopped)
                finally:
                    try: browser.close()
                    except Exception: pass

            with lock:
                done_count += 1
                if success:
                    success_count += 1
                if mode == 'register':
                    new_status = 'done' if success else 'failed'
                else:
                    # Verify: login OK -> "verified" (khong test lai lan sau)
                    #         login fail -> "login_fail"
                    new_status = 'verified' if success else 'login_fail'
                self.rakuten_reg_tab.set_status(n, new_status, note)
                status_label = 'THANH CONG' if success else 'THAT BAI'
                logging.info(f'[{mode.upper()} #{n:03d}] {status_label}: {note}')
                d, s = done_count, success_count

            action_lbl = 'Dang ky' if mode == 'register' else 'Verify'
            self.rakuten_reg_tab.after(
                0, self.rakuten_reg_tab.progress_lbl.config,
                {'text': f'{action_lbl} [{d}/{total}]  OK: {s}  Fail: {d-s}',
                 'fg': '#27ae60' if mode == 'verify' else '#8e44ad'}
            )

        with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
            futures = {pool.submit(_run_one, acc): acc for acc in accounts}
            for fut in as_completed(futures):
                try:
                    fut.result()
                except Exception as e:
                    logging.error(f'[{mode.upper()}] Loi thread: {e}')

        logging.info(f'[{mode.upper()}] XONG: {success_count}/{total} thanh cong')
        self.after(0, self._rakuten_reg_done)

    def _rakuten_reg_done(self):
        self._reg_running = False
        self.rakuten_reg_tab.run_btn.config(state='normal')
        self.rakuten_reg_tab.verify_btn.config(state='normal')
        self.rakuten_reg_tab.stop_btn.config(state='disabled')
        self.rakuten_reg_tab.status_lbl.config(text='Hoan thanh', fg='#27ae60')
        self.rakuten_reg_tab._refresh()

    # ── Poll ──────────────────────────────────────────────────────────────────
    def _poll(self):
        try:
            req = otp_req_q.get_nowait()
            self.after(0, self._show_otp,
                       req.get('email', ''), req.get('prompt', 'Nhap OTP:'))
        except queue.Empty:
            pass
        self.after(300, self._poll)

    def _show_otp(self, email, prompt):
        dlg = OTPDialog(self, email, prompt)
        otp_res_q.put(dlg.result or '')


if __name__ == '__main__':
    App().mainloop()
