"""Chhello Dwar — offline test suite (no API calls; uses the cached corpus).
Run: pytest tests/ -q"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

import ps3  # noqa: E402


def _client():
    import app as appmod
    return TestClient(appmod.app)


# ---------------- health + UI ----------------

def test_health_ok():
    c = _client()
    h = c.get("/api/health").json()
    assert h["ok"] is True and "gemini_key" in h


def test_ui_serves():
    c = _client()
    r = c.get("/")
    assert r.status_code == 200
    assert "છેલ્લો" in r.text


def test_ui_accessibility_baseline():
    t = _client().get("/").text
    assert '<html lang="gu">' in t
    assert 'role="main"' in t
    assert 'name="description"' in t


# ---------------- corpus + provenance ----------------

def test_corpus_four_calls():
    calls = ps3.list_calls()
    assert len(calls) == 4
    ids = " ".join(c["id"] for c in calls)
    assert "SYNTH" in ids          # synthetic provenance labels present
    assert "genuine" in ids        # the control call exists


# ---------------- detection engine (cached corpus, zero API) ----------------

def test_scam_chunk_detects_otp_request():
    out = ps3.analyze_chunk("scam2_fake_kyc_otp_SYNTH", 4, b"", "audio/wav")
    assert out["from_cache"] is True
    cats = [f["category"] for f in out["red_flags"]]
    assert "otp_request" in cats


def test_genuine_chunk_stays_clean():
    out = ps3.analyze_chunk("genuine_bank_followup_SYNTH", 3, b"", "audio/wav")
    assert out["from_cache"] is True
    assert out["red_flags"] == []          # 'we never ask for OTP' = benign


def test_genuine_never_flags_across_all_chunks():
    for i in range(7):
        if not os.path.exists(ps3._cache_path("genuine_bank_followup_SYNTH", i)):
            continue
        out = ps3.analyze_chunk("genuine_bank_followup_SYNTH", i, b"", "audio/wav")
        assert out["red_flags"] == [], f"chunk {i} raised flags on a genuine call"


def test_every_scam_call_has_a_flagged_chunk():
    for call in ["scam1_digital_arrest_SYNTH", "scam2_fake_kyc_otp_SYNTH", "scam3_fake_courier_SYNTH"]:
        flagged = 0
        for i in range(12):
            if not os.path.exists(ps3._cache_path(call, i)):
                continue
            out = ps3.analyze_chunk(call, i, b"", "audio/wav")
            if out["red_flags"]:
                flagged += 1
        assert flagged >= 1, f"{call}: no red flags raised anywhere"


# ---------------- warning assembly (pure function) ----------------

def test_build_warning_names_the_lies_and_the_helpline():
    txt = ps3.build_warning({"otp_request": 1, "urgency": 1})
    assert "1930" in txt                    # the cyber-helpline
    assert "OTP" in txt or "ઓટીપી" in txt


def test_build_warning_prioritises_digital_arrest():
    txt = ps3.build_warning({"video_arrest": 1, "urgency": 1})
    assert "વિડિયો" in txt or "ધરપકડ" in txt


def test_build_warning_caps_lines():
    cats = {c: 1 for c in ["video_arrest", "otp_request", "money_transfer",
                           "police_impersonation", "secrecy_instruction", "urgency"]}
    txt = ps3.build_warning(cats)
    assert len(txt) < 400
