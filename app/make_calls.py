"""RAKHDI — generate the 4 demo call WAVs + 3 fallback warning WAVs via Gemini TTS.
Two voice passes per call (scammer=Charon / elder=Kore / genuine RM=Leda / customer=Puck),
500ms gaps, concatenated with the wave module, downsampled 24k->16k for telephony realism.
Per the risk auditor: filenames carry _SYNTH, and DATASET.md documents provenance.
"""
import base64
import json
import os
import random
import sys
import time
import wave

import audioop

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm

OUT = os.path.join(HERE, "data", "calls")
os.makedirs(OUT, exist_ok=True)

VOICES = {"S": "Charon", "V": "Kore", "RM": "Leda", "C": "Puck"}

CALLS = {
    "scam1_digital_arrest_SYNTH": [
        ("S", "नमस्ते, मैं मुंबई साइबर सेल से इंस्पेक्टर आर. के. शर्मा बोल रहा हूँ। आपके आधार नंबर पर money laundering का केस दर्ज हुआ है।"),
        ("V", "क्या? मैं कुछ समझ नहीं पा रही... मेरे साथ ऐसा कैसे हो सकता है?"),
        ("S", "आपके खाते से आठ लाख रुपये एक संदिग्ध आतंकी के खाते में गए हैं। आप पर सीधी जांच चल रही है। तुरंत वीडियो कॉल पर आइए, आपका digital arrest हो रहा है।"),
        ("V", "वीडियो कॉल पर गिरफ्तारी? पुलिस ऐसा कभी नहीं करती... मुझे बेटी से पूछने दीजिए।"),
        ("S", "रुकिए! किसी को बताया तो तुरंत वारंट निकलेगा। बेटी को कुछ मत बताना। जांच फीस पचास हजार रुपये सरकारी सेक्योरिटी खाते में भेजिए, तीस मिनट का समय है।"),
        ("V", "पचास हजार? मेरे पास इतने पैसे कहां हैं..."),
        ("S", "आधार और पैन कार्ड कैमरे पर दिखाइए और जितना हो सके तुरंत ट्रांसफर कीजिए, वरना आपको अभी जेल जाना पड़ेगा।"),
        ("V", "भगवान के लिए... देखती हूँ..."),
    ],
    "scam2_fake_kyc_otp_SYNTH": [
        ("S", "नमस्कार, मैं एसबीआई हेड ऑफिस से श्वेता मेहरा बोल रही हूँ। आपका KYC आज रात बारह बजे तक अपडेट नहीं हुआ तो आपका खाता हमेशा के लिए ब्लॉक हो जाएगा।"),
        ("V", "अरे! KYC कैसे अपडेट करूँ? मुझे कुछ पता नहीं चला था।"),
        ("S", "इसीलिए फोन कर रही हूँ। आपके नंबर पर अभी एक OTP आया होगा, उसे मुझे बता दीजिए, सिर्फ दस मिनट का समय है।"),
        ("V", "OTP? बैंक तो कभी OTP नहीं मांगती..."),
        ("S", "मैडम, समय बहुत कम है। OTP और आधार नंबर दोनों चाहिए, वरना खाते के सारे पैसे फ्रीज हो जाएंगे। जल्दी बोलिए!"),
        ("V", "ठीक है... SMS देख रही हूँ..."),
        ("S", "OTP बताइए और फोन नहीं काटना, लाइन पर रहिए।"),
    ],
    "scam3_fake_courier_SYNTH": [
        ("S", "मैडम, फेडएक्स कस्टम डिपार्टमेंट से बोल रहा हूँ। आपके नाम का पार्सल पकड़ा गया है, जिसमें तीन करोड़ रुपये की ड्रग्स और तीन पासपोर्ट मिले हैं।"),
        ("V", "मेरा पार्सल? मैंने कुछ नहीं भेजा..."),
        ("S", "मुंबई पुलिस का money laundering का केस चल रहा है, जांच वीडियो कॉल पर होगी, अभी आइए।"),
        ("V", "मम्मी को बताती हूँ..."),
        ("S", "किसी को नहीं बताना! केस बंद कराने के लिए पचपन हजार रुपये एक सेक्योर सरकारी खाते में जमा करने होंगे, आज शाम तक। वरना गिरफ्तारी वारंट निकल जाएगा।"),
        ("V", "इतने पैसे कहां से..."),
        ("S", "जल्दी कीजिए, समय बहुत कम है। वरना आपका नाम एयरपोर्ट पर जुर्माने वाली लिस्ट में आ जाएगा।"),
    ],
    "genuine_bank_followup_SYNTH": [
        ("RM", "નમસ્તે બહેન, હું HDFC બેંકની શ્વેતા બોલું છું. તમારી ફિક્સ્ડ ડિપોઝિટ પરીપક્વ થઈ છે, લગભગ બે લાખ રૂપિયા."),
        ("C", "ઓહ, સારું. હવે શું કરવું?"),
        ("RM", "શુક્રવાર સુધીમાં બ્રાન્ચમાં આવીને કાગળો કરાવી લેશો તો વ્યાજ સારું મળશે. અને યાદ રાખો — આપણે ક્યારેય OTP માંગીએ નહીં, કોઈને કદી OTP આપવાનું નહીં."),
        ("C", "સમજાઈ ગયું. હું પોતે બ્રાન્ચ આવી જઈશ."),
        ("RM", "ફક્ત આધાર કાર્ડ બ્રાન્ચમાં લઈ જજો અને ડોક્ટરનો અપોઇન્ટમેન્ટ છે એટલે વેળા પહેલાં નીકળજો, મોડું ન થઈ જતું."),
        ("C", "બરાબર, આભાર."),
    ],
}

WARNINGS = {
    "warn_video_arrest": ("સાવધાન! આ ફોનકોલ સ્કેમ છે. પોલીસ ક્યારેય વિડિયો કોલ પર ધરપકડ નથી કરતી. "
                          "કોલ તરત બંધ કરો. ફરિયાદ માટે 1930 પર કોલ કરો."),
    "warn_otp": ("સાવધાન! આ ફોનકોલ સ્કેમ છે. OTP કોઈને આપવાનો નથી — બેંક ક્યારેય OTP નથી માંગતી. "
                 "કોલ તરત બંધ કરો. ફરિયાદ માટે 1930 પર કોલ કરો."),
    "warn_money": ("સાવધાન! આ ફોનકોલ સ્કેમ છે. ફોન પર પૈસા ટ્રાન્સફર ન કરો. "
                   "કોલ તરત બંધ કરો. ફરિયાદ માટે 1930 પર કોલ કરો."),
}

def tts_pcm(text: str, voice: str, role: str = "S") -> bytes:
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    try:
        resp = llm._gemini_post(llm.G_TTS, payload, timeout=45)
        data = resp["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        llm.USAGE["gemini"] += 1
        return base64.b64decode(data)
    except Exception as e:
        raise RuntimeError(f"tts failed: {e}")


def wrap_pcm(pcm: bytes) -> bytes:
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(pcm)
    return buf.getvalue()


def silence(ms: int = 500) -> bytes:
    return b"\x00" * (int(24000 * 2 * ms / 1000))


def degrade(pcm: bytes, rate: int = 24000) -> tuple:
    """Downsample to 16kHz telephony realism (audioop is stdlib on py3.11)."""
    out, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    # sprinkle barely-audible line noise (~ -42dB)
    noisy = bytearray(out)
    rnd = random.Random(42)
    for i in range(0, len(noisy), 4):
        n = rnd.randint(-8, 8)
        noisy[i] = max(0, min(255, noisy[i] + n))
    return bytes(noisy), 16000


# ---------------- calls ----------------
CACHE = os.path.join(OUT, "turn_cache")
os.makedirs(CACHE, exist_ok=True)

manifest = {}
for call_id, turns in CALLS.items():
    print(f"=== {call_id} ({len(turns)} turns) ===")
    parts = []
    for i, (role, line) in enumerate(turns):
        voice = VOICES[role]
        cpath = os.path.join(CACHE, f"{call_id}_{i}_{role}.pcm")
        if os.path.exists(cpath):
            pcm = open(cpath, "rb").read()
            print(f"  turn {i + 1} [{role}/{voice}] cached")
        else:
            pcm = tts_pcm(line, voice, role)
            open(cpath, "wb").write(pcm)
            print(f"  turn {i + 1} [{role}/{voice}] {len(pcm)} bytes")
            time.sleep(1.2)  # keep free-tier RPM happy
        parts.append((role, wrap_pcm(pcm)))
    raw = b"".join(p for _, p in parts)
    # interleave silences
    blob = silence(400)
    joined = blob
    for _, p in parts:
        joined += p + silence(650)
    pcm24 = joined[4:]  # trim leading silence
    deg, rate = degrade(pcm24)
    path = os.path.join(OUT, f"{call_id}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(deg)
    dur = len(deg) / 2 / rate
    manifest[call_id] = {"file": path, "seconds": round(dur, 1), "turns": len(turns)}
    print(f"  -> {path} ({dur:.1f}s)\n")

# ---------------- fallback warnings ----------------
os.makedirs(os.path.join(HERE, "data", "warnings"), exist_ok=True)
for wname, text in WARNINGS.items():
    wpath = os.path.join(CACHE, f"warning_{wname}.pcm")
    if os.path.exists(wpath):
        pcm = open(wpath, "rb").read()
    else:
        pcm = tts_pcm(text, "Kore", "V")
        open(wpath, "wb").write(pcm)
    deg, rate = degrade(wrap_pcm(pcm))
    path = os.path.join(HERE, "data", "warnings", f"{wname}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(deg)
    print(f"warning {wname}: {len(deg) / 2 / rate:.1f}s")

import json
with open(os.path.join(OUT, "calls.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print("\nMANIFEST:", json.dumps(manifest, indent=1))
print("usage:", llm.USAGE)
