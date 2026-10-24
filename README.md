# 🚪 છેલ્લો દ્વાર · CHELLO DWAR (The Last Door)
**Garbathon 2026 — Problem Statement 03 · Voice AI: Scam Call Shield** · GDG Ahmedabad Pre-DevFest · built by Manas Choksi (solo)

> Every scam call is a knock on your mother's door. **Chhello Dwar is the last door that scammer ever reaches.**

## The problem (PS 03)
"Digital arrest", fake KYC and fake courier calls cost Indians thousands of crores a year. Elders and first-time smartphone users are hit hardest — because the victim is alone on the call. Expected output: play a scripted scam call, the assistant flags it as a scam **while the call is still going**, warns the user, and explains why in simple Gujarati or Hindi.

## What it does
An end-to-end **Gemini** voice agent that listens to a phone call in 6-second chunks. Each chunk goes to **Gemini audio understanding** — transcript + red-flag reasoning in ONE structured call — feeding a deterministic cumulative scorer. When red flags cross the threshold, Chhello Dwar **interrupts the call mid-stream**: the call audio ducks, and a spoken **Gujarati warning** breaks over it, naming the exact lies it heard — *"પોલીસ ક્યારેય વિડિયો કોલ પર ધરપકડ નથી કરતી. કોલ તરત બંધ કરો. ફરિયાદ માટે 1930 પર કોલ કરો."*

Three pre-recorded scam calls + **one genuine call as the control**: the genuine call stays silent — **it protects without crying wolf.** Plus a **LIVE mode**: tap 🎤, speak to the shield yourself — your speech is analyzed in real time, the transcript and red flags appear live, and the agent **talks back in Gujarati** — warning you if you sound scammy, reassuring you when you don't.

## Measured outcomes (chunk-level E2E, run at the event)
| call | verdict | warning fired at | scam score |
|---|---|---|---|
| Digital arrest (Hindi) | SCAM | **6s into a 56s call** | 30 |
| Fake KYC + OTP (Hindi) | SCAM | **6s into a 41s call** | 18 |
| Fake courier (Hindi) | SCAM | **6s into a 40s call** | 26 |
| Genuine bank follow-up (Gujarati) | GENUINE — silent | never | **0** |

All 3 scam calls were interrupted **24–44 seconds before the money demand**. The genuine call — deliberately containing *OTP*, *Aadhaar* and a deadline in benign forms — raised **zero flags across all 7 chunks**.

## Red flags it names (per the PS)
urgency · threats · OTP/money requests · police/bank impersonation · secrecy instructions · Aadhaar/PAN demands · digital-arrest claims · fake case claims — every warning cites the exact words it heard.

## Stack — 100% Google
- **Gemini** — audio understanding + red-flag reasoning in one structured call per chunk; **Gemini speech generation** for the live Gujarati warning + conversational replies
- **Firebase Firestore** — real-time audit log: every call verdict written to `rakhdi_sessions` from the client
- **Google Cloud Run** — one-command deploy of the whole shield (Dockerfile included)
- Single-file trilingual PWA (ગુજરાતી · हिन्दी · English), installable on any phone via Add to Home screen

## How it was built: a fleet of ~80 autonomous agents
The entire shield — recon, architecture, corpus, engine, UI, evals — was produced in one evening by orchestrating **~80 specialized AI agents** (recon fleets, design fleets, build agents, red-team agents, eval agents) through the **Hermes** agent platform, with Gemini as the reasoning engine. Full breakdown in [docs/AGENTS.md](docs/AGENTS.md).

## Structure
```
├── app/                  # the shield
│   ├── app.py            # FastAPI shell
│   ├── ps3.py            # detection engine: chunk endpoint, scorer, warning assembly
│   ├── llm.py            # Gemini client: audio analysis + speech generation + usage counters
│   ├── static/           # trilingual PWA (fonts + icons self-hosted)
│   ├── data/calls/       # the 4-call corpus (synthetic, _SYNTH provenance)
│   ├── data/warnings/    # pre-generated Gujarati warning wavs (offline layer)
│   ├── make_calls.py     # corpus generator (Gemini speech generation, turn-cached)
│   └── e2e_ps3.py        # the 4-call evaluation harness
├── docs/AGENTS.md        # the agent-fleet build log
├── Dockerfile            # Google Cloud Run / any container host
└── render.yaml           # one-command deploy blueprint
```

## Run locally
```bash
cd app
pip install -r requirements.txt
export GEMINI_API_KEY=...        # your Gemini API key
uvicorn app:app --port 8080      # → http://localhost:8080
```

## Deploy
- **Cloud Run:** `gcloud run deploy chhello-dwar --source app --allow-unauthenticated --set-env-vars GEMINI_API_KEY=...`
- **Render:** blueprint in `render.yaml` — auto-detected.

## PROVENANCE (full disclosure)
- The call recordings are **synthetic re-enactments** (filenames carry `_SYNTH`), scripted from police-documented scam patterns and voiced with Gemini speech generation — real scam recordings would mean real victims, an ethical non-starter. `make_calls.py` reproduces the corpus.
- Chunk analyses are cached per (call, chunk) for rehearsal replays; the live demo and LIVE mic mode make fresh Gemini calls every time — the LIVE mode's unique session IDs make rehearsed answers impossible.
