"""Chhello Dwar — The Last Door: Scam Call Shield (Garbathon 2026, GDG Ahmedabad).
FastAPI shell: serves the shield UI + mounts the detection engine router."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import llm
import ps3

HERE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Chhello Dwar — Scam Call Shield", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    h = llm.health()
    h["ok"] = True
    return h


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
app.include_router(ps3.router, prefix="/api/ps3")
