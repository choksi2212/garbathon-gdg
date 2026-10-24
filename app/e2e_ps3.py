"""RAKHDI engine E2E: slice each call wav into 6s chunks -> POST /api/ps3/chunk
sequentially (mimicking playback cadence, but faster). Proves: scam calls trigger
the mid-call warning; the genuine call stays silent. Fills the analysis cache
(rehearsals + offline backup become free)."""
import io
import json
import time
import urllib.request
import wave

BASE = "https://localhost:8443"
import ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CH = 6.0


def post(url, data=None, is_json=False, form=None):
    if form:
        boundary = "----rakhdi"
        body = b""
        for k, v in form.items():
            if isinstance(v, bytes):
                body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{k}.bin\"\r\n"
                         f"Content-Type: application/octet-stream\r\n\r\n").encode() + v + b"\r\n"
            else:
                body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, data=json.dumps(data).encode() if data else b"",
                                     headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60, context=ctx).read())


def wav_chunk_bytes(path, i):
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        w.setpos(int(i * CH * rate))
        frames = w.readframes(int(CH * rate))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate)
        out.writeframes(frames)
    return buf.getvalue(), rate


def run_call(call_id, path, expected):
    post(f"{BASE}/api/ps3/reset/{call_id}", {})
    with wave.open(path, "rb") as w:
        dur = w.getnframes() / w.getframerate()
    n = int(dur / CH) + 1
    print(f"\n=== {call_id} ({dur:.0f}s, {n} chunks) — expect: {expected} ===")
    warned_at = None
    cumulative_total = 0
    r = {}
    for i in range(n):
        data, rate = wav_chunk_bytes(path, i)
        t0 = time.time()
        for attempt in range(4):
            try:
                r = post(f"{BASE}/api/ps3/chunk", form={"call_id": call_id, "chunk_index": str(i),
                                                       "audio": data})
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:200]
                wait = 20 * (attempt + 1)
                print(f"  chunk {i}: 429/err (attempt {attempt + 1}) — waiting {wait}s: {body[:120]}")
                time.sleep(wait)
        dt = time.time() - t0
        cum = r.get("cumulative") or {}
        cumulative_total = cum.get("total", 0)
        flags = r.get("red_flags") or []
        cached = "CACHE" if r.get("cached") else "LIVE "
        print(f"  chunk {i}: {cached} {dt:4.1f}s | flags={[f['category'] for f in flags]} | total={cumulative_total}"
              f" | verdict={r.get('verdict')}")
        if r.get("warning") and warned_at is None:
            warned_at = i
            wt = r["warning"]["text"][:80]
            print(f"  ⚠ WARNING at chunk {i} ({i * 6}-{i * 6 + 6}s into call): {wt}...")
            print(f"  ⚠ warning audio: {r['warning'].get('audio')}")
    return warned_at, cumulative_total, r


calls = [
    ("scam1_digital_arrest_SYNTH", "data/calls/scam1_digital_arrest_SYNTH.wav", "SCAM + warning mid-call"),
    ("scam2_fake_kyc_otp_SYNTH", "data/calls/scam2_fake_kyc_otp_SYNTH.wav", "SCAM + warning mid-call"),
    ("scam3_fake_courier_SYNTH", "data/calls/scam3_fake_courier_SYNTH.wav", "SCAM + warning mid-call"),
    ("genuine_bank_followup_SYNTH", "data/calls/genuine_bank_followup_SYNTH.wav", "GENUINE — no warning"),
]

import os
HERE = os.path.dirname(os.path.abspath(__file__))
results = {}
for cid, path, exp in calls:
    warn_chunk, total, last = run_call(cid, os.path.join(HERE, path), exp)
    ok = ("SCAM" in (last.get("verdict") or "")) if "SCAM" in exp else (last.get("verdict") != "SCAM")
    results[cid] = {"warned_at_chunk": warn_chunk, "warned_at_seconds": (warn_chunk * 6 if warn_chunk is not None else None),
                    "final_total": total, "verdict": last.get("verdict"), "pass": ok and ((warn_chunk is not None) == ("SCAM" in exp))}
    print(f"  => {cid}: {'✅ PASS' if results[cid]['pass'] else '❌ FAIL'} (verdict={last.get('verdict')}, warned_at_chunk={warn_chunk})")

print("\n=== E2E SUMMARY ===")
print(json.dumps(results, indent=1))
scam_warn_secs = [r["warned_at_seconds"] for c, r in results.items() if "scam" in c and r["warned_at_seconds"]]
if scam_warn_secs:
    print(f"warnings fired at {scam_warn_secs} seconds into the calls (call durations ~40-56s)")
