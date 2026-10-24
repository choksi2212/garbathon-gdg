"""
Sanjog LLM layer — provider abstraction with demo-survival fallbacks.

Priority chain for every capability:
  1. Gemini (generativelanguage REST, key from ../.env)  — the Google-stack play
  3. Canned mock responses — survives total API/network loss on stage

Zero SDK dependencies: httpx + stdlib only. Swap providers via env or /api/mode.
"""
import base64
import json
import os
import random
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------- env
def _load_env() -> dict:
    env = {}
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if k in ("GEMINI_API_KEY",):
            env[k] = v
    return env

ENV = _load_env()
GEMINI_KEY = ENV.get("GEMINI_API_KEY", "")
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

G_TEXT = "gemini-3.6-flash"          # extraction / reasoning / matching (new-key era model)
G_TTS = "gemini-2.5-flash-preview-tts"


# provider chain: "show" = gemini-first (Google-stack optics, limited quota — showtime only)
PREF = {"value": "show"}
LAST = {"provider": "none", "error": None, "ts": 0}
USAGE = {"gemini": 0}


def health() -> dict:
    return {"gemini_key": bool(GEMINI_KEY), "usage": USAGE,
            "last_provider": LAST["provider"], "last_error": LAST["error"], "pref": PREF}


def _record(provider, err=None):
    LAST["provider"] = provider
    LAST["error"] = err
    LAST["ts"] = time.time()


# ---------------------------------------------------------------- gemini
def _gemini_post(model: str, payload: dict, timeout: float = 45.0) -> dict:
    url = f"{GEMINI_BASE}/{model}:generateContent?key={GEMINI_KEY}"
    r = httpx.post(url, json=payload, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:300]}")
    USAGE["gemini"] += 1
    return r.json()


def _gemini_text(resp: dict) -> str:
    try:
        parts = resp["candidates"][0]["content"]["parts"]
        for p in parts:
            if "text" in p:
                return p["text"]
    except Exception:
        pass
    raise RuntimeError(f"Gemini returned no text: {json.dumps(resp)[:300]}")


def _gemini_json(payload: dict) -> dict:
    resp = _gemini_post(G_TEXT, payload)
    raw = _gemini_text(resp).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def gemini_tts_wav(text: str, voice: str = "Kore") -> str | None:
    """Hero voice: Gemini speech generation -> wav url (24kHz 16-bit mono)."""
    os.makedirs(os.path.join(HERE, "static", "announcements"), exist_ok=True)
    try:
        import time as _t
        payload = {
            "contents": [{"parts": [{"text": "Say warmly: " + text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
            },
        }
        data = None
        for _ in range(2):  # preview-TTS occasionally returns an empty candidate; retry once
            resp = _gemini_post(G_TTS, payload, timeout=45)
            try:
                data = resp["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                break
            except Exception:
                _t.sleep(1.0)
        if not data:
            raise RuntimeError("tts-empty-candidate")
        pcm = base64.b64decode(data)
        import wave
        fname = f"gtts_{int(time.time() * 1000)}.wav"
        fpath = os.path.join(HERE, "static", "announcements", fname)
        with wave.open(fpath, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        USAGE["gemini"] += 1
        _record("gemini-tts")
        return f"/static/announcements/{fname}"
    except Exception as e:
        _record("gemini-tts-failed", str(e)[:200])
        return None

def tts_wav(text: str, lang: str = "gu") -> str | None:
    """Speak text -> wav url (Gemini speech generation)."""
    return gemini_tts_wav(text, "Kore" if lang != "en" else "Charon")
