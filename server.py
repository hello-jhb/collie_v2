"""
server.py — FastAPI wrapper around the Collie engine (the move off Streamlit).

ONE container serves the engine API AND (later) the built front-end, so it deploys
as a single Cloud Run service — the cheapest path. The engine modules are unchanged;
this is a thin API layer over build_investment_read / assemble_fact_sheet / whatif.

  POST /api/analyze  model file (+ optional actuals)  -> {session_id, mode, read_md, fact_sheet}
  POST /api/chat     {session_id, message}            -> {reply}
  POST /api/whatif   {session_id, amount, funded_by?} -> recomputed returns

Run locally:  uvicorn server:app --reload
Container:    see Dockerfile (uvicorn on $PORT)
"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

app = FastAPI(title="Collie", version="0.1.0")

# In-memory session store (demo-grade). One session = one analyzed deal + its
# grounding (the fact sheet) so chat/what-if can reuse it without re-running.
_SESSIONS: dict[str, dict[str, Any]] = {}


async def _save(workdir: Path, up: UploadFile) -> Path:
    p = workdir / Path(up.filename).name
    p.write_bytes(await up.read())
    return p


@app.post("/api/analyze")
async def analyze(model: UploadFile = File(...),
                  actuals: list[UploadFile] = File(default=[])):
    """Upload a model workbook (+ optional actuals statements) → the Investment Read,
    the validated fact sheet, and the metrics the UI grid renders."""
    workdir = Path(tempfile.mkdtemp(prefix="collie_"))
    model_path = await _save(workdir, model)
    actuals_paths = [await _save(workdir, a) for a in actuals if a and a.filename]

    from deal_truth import build_deal_truth
    from deal_analysis import build_analysis
    from interpretation import assemble_fact_sheet, build_investment_read

    dt = build_deal_truth(model_path)
    if not dt.get("engine_found", True):
        raise HTTPException(422, dt.get("reason", "no validated cash-flow engine in this workbook"))
    analysis = build_analysis(model_path, dt=dt)

    perf = None
    if actuals_paths:
        from perf_vs_plan_engine import build_perf_vs_plan
        perf = build_perf_vs_plan(model_path, actuals_paths)
        perf = perf if perf.get("ok") else None

    read = build_investment_read(model_path, dt=dt, analysis=analysis, perf=perf)
    fs = read.get("fact_sheet") or assemble_fact_sheet(model_path, dt=dt, analysis=analysis, perf=perf)

    sid = uuid.uuid4().hex
    _SESSIONS[sid] = {"model_path": str(model_path), "fact_sheet": fs}
    return {"session_id": sid, "mode": fs.get("mode"),
            "read_md": read.get("md"), "fact_sheet": fs}


@app.post("/api/chat")
async def chat(session_id: str = Form(...), message: str = Form(...)):
    """Grounded Q&A: GPT answers ONLY from the validated fact sheet, bound by its
    guardrails. (Return-impact math routes to /api/whatif, not a GPT estimate.)"""
    sess = _SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    from scenarios._llm import complete, llm_available
    from interpretation import render_fact_sheet
    if not llm_available():
        return {"reply": "Chat needs an API key. The validated fact sheet is still available."}
    system = (
        "You are an asset manager answering questions about ONE deal, given a VALIDATED "
        "FACT SHEET — every number in it is correct; use ONLY it. Obey the guardrails it "
        "contains and never contradict them; never invent or recompute a number. For a "
        "return-impact / what-if calculation, say it should be run as a what-if rather "
        "than estimating. Be concise.\n\n" + render_fact_sheet(sess["fact_sheet"]))
    return {"reply": complete(system, message, temperature=0.2)}


@app.post("/api/whatif")
async def whatif(session_id: str = Form(...), amount: float = Form(...),
                 funded_by: str = Form("equity")):
    """Deterministic return-impact: perturb the validated cash-flow stream and
    recompute XIRR/EM (no GPT)."""
    sess = _SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, "unknown session")
    from whatif import what_if_capex
    return what_if_capex(sess["model_path"], amount, funded_by=funded_by)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(
        "<h1>Collie API</h1><p>POST a model workbook to <code>/api/analyze</code>. "
        "The front-end build will be served from here.</p>")
