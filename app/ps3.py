"""RAKHDI — PS3 scam-call detector.
Chunked Gemini 2.5 Flash audio-in analysis + deterministic cumulative scorer + mid-call Gujarati warnings.
Quota-efficient by design: every chunk analysis is cached by (call_id, chunk_index) —
rehearsals replay free; only the live demo makes fresh calls (cache is the 429 safety net).
"""
import base64
import json
import os
import threading
import time

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

import llm

router = APIRouter(prefix="/api/ps3")

HERE = os.path.dirname(os.path.abspath(__file__))
CALLS_DIR = os.path.join(HERE, "data", "calls")
WARN_DIR = os.path.join(HERE, "data", "warnings")
CACHE_DIR = os.path.join(HERE, "data", "analysis_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SESSIONS = {}
LOCK = threading.Lock()

CALL_META = [
    {"id": "scam1_digital_arrest_SYNTH", "label": "Call 1", "hint": "an unknown official..."},
    {"id": "scam2_fake_kyc_otp_SYNTH", "label": "Call 2", "hint": "the bank that calls YOU..."},
    {"id": "scam3_fake_courier_SYNTH", "label": "Call 3", "hint": "a parcel you never sent..."},
    {"id": "genuine_bank_followup_SYNTH", "label": "Call 4", "hint": "your actual bank..."},
]

PROMPT = ("You are RAKHDI, a scam-call detection agent protecting an elderly person in India. "
          "You receive a short chunk of a phone call as RAW AUDIO. "
          "Transcribe it VERBATIM in the language spoken (keep Hindi/Gujarati/English code-mixing exactly as heard). "
          "Then list the red flags heard in THIS chunk only. Categories: "
          "otp_request (asked to READ OUT an OTP), money_transfer (send money / fees / gift cards), "
          "video_arrest (digital arrest over video call), police_impersonation (claims to be police/CBI/customs/cyber-cell/bank officer), "
          "secrecy_instruction (don't tell family / don't disconnect), aadhaar_pan_request (disclose documents over the phone), "
          "fake_case_claim (parcel with drugs / money-laundering case on your name), threat_legal (warrant / arrest threat), "
          "urgency (artificial deadline), fear_induction. "
          "BENIGN — do NOT flag: a bank SAYING 'we never ask for OTP' (that is a safety notice, quote it as benign); "
          "asking to bring documents IN PERSON to a branch; appointment reminders; mild deadlines like 'visit before Friday'. "
          "Also list benign_signals you hear. chunk_score 0-10 = how scammy THIS chunk sounds. "
          "reason_gu = one short simple Gujarati sentence explaining the biggest thing heard (for the warning card). reply_gu = a short warm conversational Gujarati sentence SPOKEN BACK to the caller: if they said something scammy, warn them firmly; if the call sounds genuine, reassure them; if they asked a question, answer it briefly. Like a caring family member listening on the line. Keep it under 15 words.")

SCHEMA = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string"},
        "red_flags": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "category": {"type": "string"},
                "quote": {"type": "string"},
                "severity": {"type": "integer"},
            },
            "required": ["category", "quote", "severity"],
        }},
        "benign_signals": {"type": "array", "items": {"type": "string"}},
        "chunk_score": {"type": "number"},
        "reason_gu": {"type": "string"},
        "reply_gu": {"type": "string"},
    },
    "required": ["transcript", "red_flags", "benign_signals", "chunk_score", "reason_gu", "reply_gu"],
}

WEIGHTS = {
    "otp_request": 4, "money_transfer": 4, "video_arrest": 4,
    "police_impersonation": 4, "secrecy_instruction": 4, "remote_access": 4,
    "threat_legal": 3, "aadhaar_pan_request": 3, "fake_case_claim": 3,
    "urgency": 2, "fear_induction": 2, "bank_impersonation": 2,
}

WARN_LINES = {
    "video_arrest": "પોલીસ ક્યારેય વિડિયો કોલ પર ધરપકડ નથી કરતી.",
    "otp_request": "OTP કોઈને આપવાનો નથી — બેંક ક્યારેય OTP નથી માંગતી.",
    "money_transfer": "ફોન પર પૈસા ટ્રાન્સફર ન કરો.",
    "secrecy_instruction": "પરિવારથી છુપાવવાનું કહેનાર ખોટું છે, પરિવારના કોઈને ચોક્કસ કહો.",
    "aadhaar_pan_request": "આધાર-પેન કાગળ ફોન પર ન આપો.",
    "police_impersonation": "ફોન પર પોલીસ બની બોલનાર ખોટો છે.",
    "threat_legal": "ફોન પર ધમકી એ સ્કેમ છે.",
    "fake_case_claim": "તમારા નામનો ખોટો કેસ — આ જૂઠ છે.",
    "urgency": "જલ્દી કરાવવાનું દબાણ એ સ્કેમની પહેલી નિશાની છે.",
    "fear_induction": "ડરાવવાનો પ્રયાસ થઈ રહ્યો છે — શાંત રહો.",
    "bank_impersonation": "બેંકના નામે ફોન કરનારની ઓળખ ખરી કરો.",
    "remote_access": "કોઈપણ એપ ઇન્સ્ટોલ કરવા ન દો.",
    "remote_access_or_urn": "કોઈપણ એપ ઇન્સ્ટોલ કરવા ન દો.",
}
WARN_PREGEN = {
    "video_arrest": "warn_video_arrest.wav",
    "otp_request": "warn_otp.wav",
    "money_transfer": "warn_money.wav",
}


def _cache_path(call_id, idx):
    return os.path.join(CACHE_DIR, f"{call_id}_{idx}.json")


def _cache_and_return(out, call_id, idx):
    out.setdefault("red_flags", [])
    out.setdefault("benign_signals", [])
    out.setdefault("chunk_score", 0)
    out.setdefault("transcript", "")
    out.setdefault("reason_gu", "")
    out.setdefault("reply_gu", "")
    slim = {k: out.get(k) for k in ("transcript", "red_flags", "benign_signals", "chunk_score", "reason_gu", "reply_gu", "from")}
    json.dump(slim, open(_cache_path(call_id, idx), "w", encoding="utf-8"), ensure_ascii=False)
    out["from_cache"] = False


def analyze_chunk(call_id: str, idx: int, audio: bytes, mime: str) -> dict:
    """Gemini audio-in -> structured red flags. Cached forever (quota efficiency)."""
    cp = _cache_path(call_id, idx)
    if os.path.exists(cp):
        out = json.load(open(cp, encoding="utf-8"))
        out["from_cache"] = True
        return out
    payload = {
        "contents": [{"role": "user", "parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": mime or "audio/wav", "data": base64.b64encode(audio).decode()}},
        ]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": SCHEMA,
            "temperature": 0.1,
            "thinking_config": {"thinking_budget": 0},
        },
    }
    try:
        resp = llm._gemini_post(llm.G_TEXT, payload, timeout=45)
        raw = llm._gemini_text(resp)
        out = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        out["from"] = "gemini"
    except Exception as e:
        # resilience: one silent retry on the same structured call
        try:
            resp = llm._gemini_json(payload)
            out = llm._gemini_text(resp) or {}
        except Exception:
            out = {}

    out["from_cache"] = False
    return out


def build_warning(flags_seen: dict) -> tuple:
    """Assemble the Gujarati warning text from detected categories (max 4 lines)."""
    parts = ["સાવધાન! આ ફોનકોલ સ્કેમ છે. કંઈક કરવા પહેલાં મારી વાત સાંભળો."]
    prio = ["video_arrest", "otp_request", "money_transfer", "police_impersonation",
            "secrecy_instruction", "aadhaar_pan_request", "threat_legal", "fake_case_claim", "urgency"]
    n = 0
    for cat in prio:
        if cat in flags_seen and cat in WARN_LINES and n < 4:
            parts.append(WARN_LINES[cat])
            n += 1
    parts.append("આ કોલ તરત બંધ કરો. ફરિયાદ માટે 1930 પર કોલ કરો.")
    return " ".join(parts)


def speak_warning(text: str, primary_cat: str) -> str:
    """Layered voice: Gemini speech generation -> pre-generated wav. Returns URL."""
    # tier 3 first check availability (cheap, local)
    pre = WARN_PREGEN.get(primary_cat)
    # tier 1: Gemini TTS
    url = llm.tts_wav(text, "gu")
    if url:
        return url

    # tier 3: pre-generated
    if pre and os.path.exists(os.path.join(WARN_DIR, pre)):
        return f"/data/warnings/{pre}"
    return ""


@router.get("/calls")
def list_calls():
    out = []
    for c in CALL_META:
        p = os.path.join(CALLS_DIR, c["id"] + ".wav")
        out.append({**c, "url": f"/data/calls/{c['id']}.wav",
                    "seconds": round(os.path.getsize(p) / 32000, 1) if os.path.exists(p) else 0})
    return out


@router.post("/chunk")
async def ps3_chunk(
    call_id: str = Form(...),
    chunk_index: int = Form(...),
    audio: UploadFile = File(...),
):
    data = await audio.read()
    mime = audio.content_type or "audio/wav"
    res = analyze_chunk(call_id, chunk_index, data, mime)
    if not res.get("transcript") and res.get("ok") is False:
        return JSONResponse(res, status_code=500)

    flags = res.get("red_flags") or []
    # normalize: the model sometimes returns plain strings instead of objects
    norm_flags = []
    for f in flags:
        if isinstance(f, dict):
            norm_flags.append({"category": f.get("category", ""), "quote": f.get("quote", ""), "severity": f.get("severity", 2)})
        elif isinstance(f, str):
            norm_flags.append({"category": f, "quote": "", "severity": 3})
    res["red_flags"] = norm_flags
    flags = norm_flags
    # deterministic cumulative scorer
    with LOCK:
        s = SESSIONS.setdefault(call_id, {"total": 0, "cats": set(), "chunks": set(),
                                         "benign": set(), "warned": False, "escalated": False,
                                         "flags": {}, "events": []})
        chunk_cats = set()
        for f in flags:
            cat = (f.get("category") or "").lower().strip()
            sev = min(max(int(f.get("severity", 2)), 1), 4)
            w = WEIGHTS.get(cat, 2)
            if cat not in s["cats"]:
                s["total"] += w
                s["cats"].add(cat)
            s["flags"][cat] = f.get("quote", "")
            chunk_cats.add(cat)
        if chunk_cats:
            s["chunks"].add(chunk_index)
        for b in res.get("benign_signals") or []:
            s["benign"].add(str(b)[:60])
        # GENUINE override: benign evidence and zero hard flags cap the score
        hard = s["cats"] & {"otp_request", "money_transfer", "video_arrest", "police_impersonation",
                            "secrecy_instruction", "remote_access"}
        if len(s["benign"]) >= 2 and not hard:
            s["total"] = min(s["total"], 5)
        verdict = "listening"
        warning = None
        if not s["warned"] and s["total"] >= 7 and len(s["cats"]) >= 2 and len(s["chunks"]) >= 2:
            s["warned"] = True
            wtext = build_warning(s["flags"])
            primary = next((c for c in ["video_arrest", "otp_request", "money_transfer", "police_impersonation"]
                           if c in s["flags"]), "urgency")
            waudio = speak_warning(wtext, primary)
            warning = {"text": wtext, "audio": waudio, "at_chunk": chunk_index}
            verdict = "SCAM"
        elif s["warned"]:
            verdict = "SCAM"
        elif hard:
            verdict = "suspicious"
        snap = {k: (sorted(v) if isinstance(v, set) else v) for k, v in s.items() if k != "events"}
    return {
        "ok": True,
        "call_id": call_id,
        "chunk_index": chunk_index,
        "transcript": res.get("transcript", ""),
        "red_flags": flags,
        "benign_signals": res.get("benign_signals", []),
        "reason_gu": res.get("reason_gu", ""),
        "reply_gu": res.get("reply_gu", ""),
        "engine": res.get("from", "?"),
        "cached": res.get("from_cache", False),
        "cumulative": snap,
        "verdict": verdict,
        "warning": warning,
    }


@router.post("/reset/{call_id}")
def ps3_reset(call_id: str):
    with LOCK:
        SESSIONS.pop(call_id, None)
    return {"ok": True}


from pydantic import BaseModel as _BaseModel


class SayBody(_BaseModel):
    text: str


@router.post("/say")
def ps3_say(body: SayBody):
    """Speak a conversational reply: hero voice, invisible fallback chain."""
    url = llm.gemini_tts_wav(body.text, "Kore")
    if url:
        return {"ok": True, "audio": url}
    url = llm.tts_wav(body.text, "gu")  # layered fallback — never surfaced
    if url:
        return {"ok": True, "audio": url}
    return {"ok": False, "audio": None}


@router.post("/reset")
def ps3_reset_all():
    with LOCK:
        SESSIONS.clear()
    return {"ok": True}
