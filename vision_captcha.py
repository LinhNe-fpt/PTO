"""
vision_captcha.py
=================
Giai CAPTCHA bang AI Vision (Gemini / GPT-4o).

Cau hinh:
  - Tao file captcha_config.json (hoac dat vao email_pool.json)
  - Hoac set bien moi truong GEMINI_API_KEY / OPENAI_API_KEY

captcha_config.json:
{
    "provider": "gemini",          // "gemini" hoac "openai"
    "gemini_api_key": "AIza...",
    "openai_api_key": "sk-...",
    "openai_model": "gpt-4o-mini"  // tuy chon, mac dinh gpt-4o-mini
}
"""
import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

CONFIG_FILE = Path(__file__).parent / "captcha_config.json"

_PROMPT = (
    "This is a CAPTCHA image. "
    "Please read ALL the characters shown (letters and digits) exactly as they appear. "
    "The text may be slightly distorted or have noise — do your best. "
    "Reply with ONLY the characters, nothing else. "
    "Preserve exact capitalization (uppercase/lowercase). "
    "Do NOT include spaces unless the CAPTCHA clearly shows spaces."
)


def _load_config() -> dict:
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return cfg


def _img_to_b64(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode()


# ── Gemini ────────────────────────────────────────────────────────────────────
def _solve_gemini(img_bytes: bytes, api_key: str) -> Optional[str]:
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        import PIL.Image
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Tang kich thuoc de AI nhin ro hon
        if img.width < 200:
            scale = max(2, 200 // img.width)
            img = img.resize((img.width * scale, img.height * scale), PIL.Image.LANCZOS)

        # Thu lan luot cac model (uu tien lite vi nhanh va co free tier)
        MODELS = [
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-2.5-flash-lite",
        ]
        response = None
        for _model in MODELS:
            try:
                response = client.models.generate_content(
                    model=_model,
                    contents=[_PROMPT, img],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=20,
                    ),
                )
                log.info(f"[Vision/Gemini] Dung model: {_model}")
                break
            except Exception as _e:
                log.debug(f"[Vision/Gemini] {_model}: {_e}")
        if response is None:
            raise RuntimeError("Tat ca Gemini model deu that bai")
        text = (response.text or "").strip()
        import re
        text = re.sub(r"[^A-Za-z0-9]", "", text)
        log.info(f"[Vision/Gemini] CAPTCHA = '{text}'")
        return text if text else None

    except Exception as e:
        log.warning(f"[Vision/Gemini] Loi: {e}")
        return None


# ── OpenAI GPT-4o ─────────────────────────────────────────────────────────────
def _solve_openai(img_bytes: bytes, api_key: str, model: str = "gpt-4o-mini") -> Optional[str]:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        b64 = _img_to_b64(img_bytes)
        resp = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text",       "text": _PROMPT},
                    {"type": "image_url",  "image_url": {
                        "url": f"data:image/png;base64,{b64}",
                        "detail": "high"
                    }},
                ],
            }],
            max_tokens=20,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
        import re
        text = re.sub(r"[^A-Za-z0-9]", "", text)
        log.info(f"[Vision/OpenAI] CAPTCHA = '{text}'")
        return text if text else None

    except Exception as e:
        log.warning(f"[Vision/OpenAI] Loi: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────
def solve_captcha_vision(img_bytes: bytes) -> Optional[str]:
    """
    Giai CAPTCHA bang AI Vision.
    Tra ve chuoi ky tu CAPTCHA, hoac None neu that bai.
    """
    cfg = _load_config()

    # Lay API key: uu tien config file, fallback bien moi truong
    provider       = cfg.get("provider", "gemini").lower()
    gemini_key     = cfg.get("gemini_api_key", "") or os.getenv("GEMINI_API_KEY", "")
    openai_key     = cfg.get("openai_api_key", "") or os.getenv("OPENAI_API_KEY", "")
    openai_model   = cfg.get("openai_model", "gpt-4o-mini")

    if provider == "openai" and openai_key:
        return _solve_openai(img_bytes, openai_key, openai_model)
    elif gemini_key:
        result = _solve_gemini(img_bytes, gemini_key)
        if result:
            return result
        # Fallback sang OpenAI neu Gemini that bai
        if openai_key:
            log.info("[Vision] Gemini that bai, thu OpenAI...")
            return _solve_openai(img_bytes, openai_key, openai_model)
    elif openai_key:
        return _solve_openai(img_bytes, openai_key, openai_model)
    else:
        log.warning("[Vision] Chua cau hinh API key. Tao file captcha_config.json")
        return None


def has_vision_config() -> bool:
    """Kiem tra xem da cau hinh Vision AI chua."""
    cfg = _load_config()
    return bool(
        cfg.get("gemini_api_key") or cfg.get("openai_api_key") or
        os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
