"""
captcha_solver.py
=================
Giai CAPTCHA anh chua ky tu van ban tren cac trang web.

Chien luoc:
  1. Lay anh CAPTCHA tu trang (screenshot phan tu img)
  2. Tien xu ly anh (tang do tuong phan, thu nhi phan hoa)
  3. OCR bang EasyOCR (primary) hoac pytesseract (fallback)
  4. Neu OCR that bai / confidence thap -> hien dialog nhap tay

Dung:
    from captcha_solver import solve_captcha_on_page
    text = solve_captcha_on_page(page, manual_cb=None)
"""
import io
import logging
import re
import base64
from typing import Callable, Optional

log = logging.getLogger(__name__)

# ── Image preprocessing ───────────────────────────────────────────────────────
def _preprocess_image(img_bytes: bytes) -> bytes:
    """
    Tien xu ly anh CAPTCHA:
    - Xoa noise dots bang median filter va morphological operations
    - Tang do tuong phan
    - Thu nhi phan hoa Otsu
    - Upscale x3 de OCR chinh xac hon
    """
    try:
        from PIL import Image, ImageFilter, ImageEnhance
        import numpy as np

        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')

        # Upscale truoc (de xu ly tot hon)
        w, h = img.size
        img = img.resize((w * 3, h * 3), Image.LANCZOS)

        # Chuyen sang grayscale
        gray = img.convert('L')
        arr  = np.array(gray)

        # Threshold nhi phan - pixels < 128 la text (toi mau), nguoc lai la nen
        # CAPTCHA Rakuten: text mau do/toi tren nen sang
        threshold = 160
        binary = (arr < threshold).astype('uint8') * 255

        # Loai bo noise dots bang erosion (thu nho phan tu nho)
        from PIL import ImageMorph
        binary_img = Image.fromarray(binary.astype('uint8'))

        # Ap dung median filter de lam muot
        binary_img = binary_img.filter(ImageFilter.MedianFilter(size=3))

        # Lai upscale lan nua
        bw, bh = binary_img.size
        binary_img = binary_img.resize((bw, bh), Image.LANCZOS)

        # Tang contrast
        enhancer = ImageEnhance.Contrast(binary_img)
        binary_img = enhancer.enhance(3.0)

        out = io.BytesIO()
        binary_img.save(out, format='PNG')
        return out.getvalue()
    except Exception as e:
        log.debug(f"[CAPTCHA] Preprocess error: {e}")
        try:
            # Fallback don gian
            from PIL import Image, ImageEnhance
            img = Image.open(io.BytesIO(img_bytes)).convert('L')
            w, h = img.size
            img = img.resize((w * 3, h * 3), Image.LANCZOS)
            img = ImageEnhance.Contrast(img).enhance(2.5)
            out = io.BytesIO()
            img.save(out, format='PNG')
            return out.getvalue()
        except Exception:
            return img_bytes


# ── OCR engines ───────────────────────────────────────────────────────────────
_easyocr_reader = None  # cache reader de khong load lai model moi lan

def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(['en'], verbose=False)
    return _easyocr_reader


def _ocr_easyocr(img_bytes: bytes) -> tuple[str, float]:
    """Tra ve (text, confidence) bang EasyOCR."""
    try:
        reader  = _get_easyocr_reader()
        results = reader.readtext(img_bytes, detail=1, paragraph=False,
                                  allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
        if not results:
            return '', 0.0
        text = ''.join(r[1] for r in results)
        conf = min(r[2] for r in results)
        text = re.sub(r'\s+', '', text)
        return text, conf
    except Exception as e:
        log.warning(f"[CAPTCHA] EasyOCR error: {e}")
        return '', 0.0


def _ocr_tesseract(img_bytes: bytes) -> tuple[str, float]:
    """Tra ve (text, confidence) bang pytesseract (fallback)."""
    try:
        import pytesseract
        from PIL import Image
        img  = Image.open(io.BytesIO(img_bytes))
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT,
                                         config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
        texts = [t for t, c in zip(data['text'], data['conf']) if t.strip() and int(c) > 0]
        confs = [int(c) / 100 for t, c in zip(data['text'], data['conf']) if t.strip() and int(c) > 0]
        text  = ''.join(texts)
        conf  = min(confs) if confs else 0.0
        return text, conf
    except Exception as e:
        log.debug(f"[CAPTCHA] Tesseract error: {e}")
        return '', 0.0


# ── Get CAPTCHA image bytes from page ─────────────────────────────────────────
def _get_captcha_bytes(page, captcha_selector: str = None) -> Optional[bytes]:
    """
    Lay bytes cua anh CAPTCHA tu trang web.
    Tim img co src data:image hoac src dau tu captcha-like URL.
    """
    try:
        # Thu selector chi dinh truoc
        selectors = []
        if captcha_selector:
            selectors.append(captcha_selector)
        selectors += [
            'img[src*="captcha"]',
            'img[alt*="captcha"]',
            'img[alt*="CAPTCHA"]',
            'img[src*="challenge"]',
            '.captcha img', '#captcha img',
            'img[src^="data:image"]',   # base64 inline
        ]

        for sel in selectors:
            try:
                els = page.query_selector_all(sel)
                if not els:
                    continue
                for el in els:
                    if not el.is_visible():
                        continue
                    # Lay src
                    src = el.get_attribute('src') or ''
                    if src.startswith('data:image'):
                        # Inline base64
                        b64 = src.split(',', 1)[1]
                        return base64.b64decode(b64)
                    elif src:
                        # Screenshot phan tu
                        bb = el.bounding_box()
                        if bb and bb['width'] > 20 and bb['height'] > 10:
                            return el.screenshot()
            except Exception:
                pass

        # Fallback: screenshot tat ca img tren trang, lay cai co kich thuoc captcha-like
        imgs = page.query_selector_all('img')
        for img in imgs:
            try:
                bb = img.bounding_box()
                if not bb:
                    continue
                w, h = bb['width'], bb['height']
                # CAPTCHA thuong la anh ngang, khoang 100-400px rong, 30-100px cao
                if 80 <= w <= 500 and 25 <= h <= 120:
                    return img.screenshot()
            except Exception:
                pass
    except Exception as e:
        log.debug(f"[CAPTCHA] get_bytes error: {e}")
    return None


# ── Manual input ────────────────────────────────────────────────────────────────
def _manual_input_dialog(img_bytes: Optional[bytes],
                          ocr_guess: str = '') -> str:
    """
    Yeu cau user nhap CAPTCHA thu cong.

    Chien luoc 2 lop:
      1. Luu anh ra file tam, mo bang Windows Photo Viewer de user nhin ro
      2. Hoi qua console input() - LUON HOAT DONG, khong bi che boi browser

    Tkinter dialog chi la uu tien thu 3 (de backup khi co GUI).
    """
    import os, tempfile, subprocess, sys, threading

    # ── Buoc 1: Mo anh CAPTCHA bang ung dung anh mac dinh ─────────────────────
    img_path = None
    if img_bytes:
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix='_captcha.png', delete=False,
                dir=tempfile.gettempdir()
            )
            tmp.write(img_bytes)
            tmp.close()
            img_path = tmp.name
            # Mo anh bang chuong trinh mac dinh (Windows: mspaint / Photos)
            os.startfile(img_path)
            log.info(f"[CAPTCHA] Mo anh: {img_path}")
        except Exception as e:
            log.debug(f"[CAPTCHA] Khong mo anh duoc: {e}")

    # ── Buoc 2: Hoi qua console (luon hoat dong) ──────────────────────────────
    print("\n" + "=" * 55)
    print("  *** CAPTCHA - YEU CAU NHAP THU CONG ***")
    print("=" * 55)
    if img_path:
        print(f"  Anh CAPTCHA: {img_path}")
        print("  (Da mo bang ung dung anh, hay nhin anh va nhap)")
    if ocr_guess:
        print(f"  OCR goi y  : {ocr_guess}")
    print("=" * 55)

    val = ''
    while not val:
        try:
            val = input("  Nhap ma CAPTCHA (phan biet HOA/thuong) roi Enter: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Neu chay trong moi truong khong co stdin (GUI thread)
            # -> thu Tkinter dialog song song
            break

    # ── Buoc 3: Neu stdin khong co (GUI thread), thu Tkinter ──────────────────
    if not val:
        val = _tkinter_dialog(img_bytes, ocr_guess)

    # Don dep file tam
    if img_path:
        try:
            os.unlink(img_path)
        except Exception:
            pass

    if val:
        log.info(f"[CAPTCHA] User nhap: '{val}'")
    else:
        log.warning("[CAPTCHA] Khong lay duoc input CAPTCHA")
    return val


def _tkinter_dialog(img_bytes: Optional[bytes], ocr_guess: str = '') -> str:
    """Dialog Tkinter du phong khi stdin khong kha dung (GUI thread)."""
    import threading
    result_holder = ['']
    done_event    = threading.Event()

    def _build():
        try:
            import tkinter as tk
            from PIL import Image, ImageTk

            root = tk.Tk()
            root.title('CAPTCHA - Nhap ma xac nhan')
            root.attributes('-topmost', True)
            root.resizable(False, False)
            root.configure(bg='#2c3e50')

            tk.Label(root, text='⚠  BOT CAN BAN NHAP CAPTCHA  ⚠',
                     font=('Arial', 11, 'bold'),
                     bg='#e74c3c', fg='white', pady=6).pack(fill='x')

            if img_bytes:
                try:
                    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                    scale = max(3, 380 // max(img.width, 1))
                    img   = img.resize((img.width * scale, img.height * scale),
                                       Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    frm   = tk.Frame(root, bg='white', bd=3, relief='ridge')
                    frm.pack(padx=15, pady=(12, 4))
                    lbl   = tk.Label(frm, image=photo, bg='white')
                    lbl.image = photo
                    lbl.pack()
                except Exception:
                    pass

            tk.Label(root, text='Nhap ky tu trong anh (phan biet HOA/thuong):',
                     font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1',
                     pady=4).pack()

            var   = tk.StringVar(value=ocr_guess)
            entry = tk.Entry(root, textvariable=var,
                             font=('Consolas', 22, 'bold'), width=10,
                             justify='center', fg='#2c3e50', bg='#ecf0f1')
            entry.pack(padx=20, pady=(4, 2), ipady=8)
            entry.select_range(0, 'end')
            entry.focus_force()

            def _ok(*_):
                v = var.get().strip()
                if not v:
                    entry.config(bg='#f1948a')
                    root.after(400, lambda: entry.config(bg='#ecf0f1'))
                    return
                result_holder[0] = v
                root.destroy()
                done_event.set()

            tk.Button(root, text='  XAC NHAN  ', command=_ok,
                      bg='#27ae60', fg='white',
                      font=('Arial', 13, 'bold'), padx=12, pady=6,
                      relief='flat', cursor='hand2').pack(pady=(8, 15))

            entry.bind('<Return>', _ok)
            root.protocol('WM_DELETE_WINDOW', _ok)

            root.update_idletasks()
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            w,  h  = root.winfo_reqwidth(),    root.winfo_reqheight()
            root.geometry(f'{w}x{h}+{(sw-w)//2}+{max(50,(sh-h)//3)}')
            root.lift()
            root.attributes('-topmost', True)
            root.mainloop()
        except Exception as e:
            log.error(f"[CAPTCHA] Tkinter dialog loi: {e}")
        finally:
            done_event.set()

    t = threading.Thread(target=_build, daemon=False)
    t.start()
    done_event.wait(timeout=300)  # Toi da 5 phut
    return result_holder[0]


# ── Main public API ────────────────────────────────────────────────────────────
def detect_captcha(page) -> bool:
    """
    Kiem tra trang hien tai co CAPTCHA THAT su khong.
    Chi tra True khi co BANG CHUNG RO RANG (tranh false positive tu banner quang cao).
    """
    try:
        # 1. URL chua captcha (dang tin cay nhat)
        if any(kw in page.url.lower() for kw in ['captcha', '/challenge']):
            return True

        # 2. Co input field yeu cau nhap CAPTCHA
        has_captcha_input = page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input'));
            return inputs.some(el => {
                const lbl = el.getAttribute('aria-label') || el.placeholder || '';
                const parent = el.closest('form,div,section');
                const nearby = parent ? parent.innerText : '';
                return lbl.includes('上記の文字') || lbl.toLowerCase().includes('captcha')
                    || nearby.includes('上記の文字を入力')
                    || nearby.toLowerCase().includes('captcha');
            });
        }""")
        if has_captcha_input:
            return True

        # 3. Co img co src/alt chua 'captcha' (chinh xac, khong dua vao kich thuoc)
        has_captcha_img = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('img')).some(img => {
                const src = img.src || '';
                const alt = img.alt || '';
                return src.toLowerCase().includes('captcha')
                    || alt.toLowerCase().includes('captcha');
            });
        }""")
        if has_captcha_img:
            return True

        # 4. Text page co cu phap ro rang (chi "上記の文字を入力" moi la CAPTCHA)
        has_captcha_text = page.evaluate("""() => {
            const text = document.body ? document.body.innerText : '';
            return text.includes('上記の文字を入力');
        }""")
        if has_captcha_text:
            return True

    except Exception:
        pass
    return False


def solve_captcha_on_page(page,
                           input_selector: str = None,
                           captcha_img_selector: str = None,
                           manual_cb: Callable[[bytes], str] = None,
                           ocr_threshold: float = 0.5,
                           max_retries: int = 3,
                           force_manual: bool = False) -> Optional[str]:
    """
    Giai CAPTCHA tren trang hien tai va dien vao input.

    Args:
        page:                  Playwright page
        input_selector:        CSS selector cua o nhap CAPTCHA (neu None: tu dong tim)
        captcha_img_selector:  CSS selector anh CAPTCHA
        manual_cb:             Callback(img_bytes) -> str de nhap tay (None = hien dialog)
        ocr_threshold:         Nguong confidence cua OCR (0-1), duoi nguong -> nhap tay
        max_retries:           So lan thu lai khi OCR sai

    Returns:
        text duoc dien vao, hoac None neu that bai
    """
    # Kiem tra xem Vision AI co san khong
    try:
        from vision_captcha import solve_captcha_vision, has_vision_config
        _vision_ok = has_vision_config()
    except ImportError:
        _vision_ok = False

    for attempt in range(max_retries):
        log.info(f"[CAPTCHA] Giai lan {attempt+1}/{max_retries}...")

        # 1. Lay anh CAPTCHA
        img_bytes = _get_captcha_bytes(page, captcha_img_selector)
        if not img_bytes:
            log.warning("[CAPTCHA] Khong tim thay anh CAPTCHA")
            return None

        text = None

        # 2. Thu Vision AI truoc (chinh xac nhat)
        if _vision_ok and not force_manual:
            log.info("[CAPTCHA] Thu Vision AI...")
            text = solve_captcha_vision(img_bytes)
            if text:
                import re as _re
                text = _re.sub(r'[^A-Za-z0-9]', '', text)
                log.info(f"[CAPTCHA] Vision AI: '{text}'")

        # 3. Fallback: EasyOCR (mien phi, it chinh xac hon)
        if not text and not force_manual:
            processed     = _preprocess_image(img_bytes)
            text_raw,  cr = _ocr_easyocr(img_bytes)
            text_proc, cp = _ocr_easyocr(processed)
            log.info(f"[CAPTCHA] EasyOCR raw='{text_raw}'({cr:.2f}) proc='{text_proc}'({cp:.2f})")
            best_text, best_conf = (text_proc, cp) if cp >= cr else (text_raw, cr)
            best_text = re.sub(r'[^A-Za-z0-9]', '', best_text)[:8]
            if best_text and best_conf >= ocr_threshold:
                text = best_text
                log.info(f"[CAPTCHA] EasyOCR dung: '{text}' (conf={best_conf:.2f})")
            else:
                log.info(f"[CAPTCHA] EasyOCR conf thap ({best_conf:.2f}), chuyen sang nhap tay")

        # 4. Nhap tay qua console (fallback cuoi)
        if not text or force_manual:
            reason = "force_manual" if force_manual else "Vision AI + OCR that bai"
            log.info(f"[CAPTCHA] Nhap tay ({reason})")
            if manual_cb:
                text = manual_cb(img_bytes)
            else:
                text = _manual_input_dialog(img_bytes, ocr_guess=text or '')

        if not text:
            log.warning("[CAPTCHA] Khong co text sau khi xu ly")
            continue

        # 5. Dien vao input va submit
        log.info(f"[CAPTCHA] Dung text: '{text}'")
        filled = _fill_captcha_input(page, text, input_selector)
        if filled:
            return text
        log.warning(f"[CAPTCHA] Khong dien duoc input, thu lai...")

    log.error("[CAPTCHA] Giai that bai sau toi da retry")
    return None


def _fill_captcha_input(page, text: str, selector: str = None) -> bool:
    """Dien text vao truong CAPTCHA."""
    try:
        if selector:
            el = page.query_selector(selector)
            if el:
                el.fill(text)
                return True

        # Tim theo aria-label / placeholder goi la captcha
        for aria in ["上記の文字を入力してください", "captcha", "認証文字"]:
            filled = bool(page.evaluate(f"""(v) => {{
                const el = Array.from(document.querySelectorAll('input')).find(
                    e => (e.getAttribute('aria-label') || e.placeholder || '').includes('{aria}')
                );
                if (!el) return false;
                const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                s.call(el, v);
                el.dispatchEvent(new Event('input',  {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                return true;
            }}""", text))
            if filled:
                return True

        # Fallback: input text thu 2 (thu 1 thuong la email, thu 2 la captcha)
        filled = bool(page.evaluate(f"""(v) => {{
            const inputs = Array.from(document.querySelectorAll('input[type=text],input:not([type])'));
            const el = inputs.length > 1 ? inputs[1] : inputs[0];
            if (!el) return false;
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            s.call(el, v);
            el.dispatchEvent(new Event('input',  {{bubbles:true}}));
            el.dispatchEvent(new Event('change', {{bubbles:true}}));
            return true;
        }}""", text))
        return filled
    except Exception as e:
        log.debug(f"[CAPTCHA] fill error: {e}")
        return False
