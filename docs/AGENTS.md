# The Build: ~80 Autonomous Agents, One Evening

Chhello Dwar was not written the usual way. It was **orchestrated** — a fleet of roughly 80
specialized AI agents, coordinated through the **Hermes** agent platform, with **Gemini** as
the reasoning engine and Manas as the solo human architect making every call.

## Why agents
The problem statement dropped at 16:50. Demos were judged from 20:45. A solo builder has
~3 hours of keyboard time. The only way to cover recon, corpus, engine, UI, evaluation,
deployment and demo-craft in that window is to **parallelize cognition**: many agents,
each with one narrow mandate, each returning evidence instead of opinions.

## The fleet, by phase

| Phase | Agents (≈ count) | Mandate |
|---|---|---|
| Domain recon | 5 | Elder-fraud research: police-documented scam scripts (digital arrest, fake KYC, fake courier), red-flag taxonomy, Gujarati phrasing of warnings |
| Event + judge recon | 5 | Read the event rules like a contract: audio-model mandate, mid-call warning requirement, "don't cry wolf" control call, offline-backup clause |
| Architecture | 8 | One agent per candidate architecture; one counter-analyst whose only job was to attack the chosen design; a risk auditor that checked every PS requirement line by line |
| Naming + story | 6 | Name candidates, tagline crafting, demo-narrative agents (the "last door" metaphor) |
| Corpus generation | 6 | Scam script writers (from the recon fleet's police-documented patterns), TTS turn-caching, WAV assembly, provenance labeling (`_SYNTH`) |
| Engine build | 8 | Chunk pipeline, structured-output schemas, cumulative scorer design, schema-drift normalization, resilience layers |
| UI/UX | 10 | Theme extraction agents (14 event screenshots → design tokens), font agents (self-hosted Gujarati + Devanagari subsets), flicker-hunt agents, trilingual copy agents |
| Live-agent layer | 6 | Real-time mic chunking, conversational reply design, speech-generation wiring |
| Evaluation | 8 | E2E harness agents (4-call suite), genuine-call control agents, latency measurement, "24–44s before the money demand" verification |
| Red team | 8 | "How does this demo die?" agents: venue internet dead, mic permission denied, quota exhausted, autoplay blocked — each with a pre-built fallback |
| Ops + deploy | 10 | HTTPS/secure-context fixes, PWA manifest + service worker, Cloud Run/Dockerfile, keep-alive strategy |

**≈80 agents.** Totals are approximate because agents spawned sub-agents.

## The pattern that made it work
1. **Evidence over opinions.** Every recon agent had to quote the primary source — the PS
   text, the event rules, the police-documented scripts. No vibes.
2. **One agent, one mandate, one artifact.** A red-team agent returns a failure mode list,
   not a redesign.
3. **The human decides at the seams.** Agent fleets proposed; Manas chose the problem,
   the name, the tone, and the demo arc.
4. **Measure, then claim.** The outcomes table in the README comes from the E2E harness,
   not from anyone's confidence.

## What the humans did
One problem statement, one name, one story, one 3-minute demo arc — and every accept/reject
decision at the seams between agent fleets.
