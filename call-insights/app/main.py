import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.cache import clear as clear_cache, on_clear
from app.dashboard import router as dashboard_router
from app.tabs import router as tabs_router
from app.db import fetch_all, fetch_one, init_schema
from app.pipeline import process_call, register_call
from app.rules import init_rules_schema, recompute

app = FastAPI(title="Call Insights", version="0.1.0",
              description="Transcribe hub calls, extract conversational signals, label calls for correlation.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CI_CORS_ORIGINS", "http://localhost:5180").split(",") if o.strip()],
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(dashboard_router)
app.include_router(tabs_router)


@app.on_event("startup")
def _startup():
    init_schema()
    init_rules_schema()
    threading.Thread(target=_warm_cache, daemon=True).start()
    on_clear(_warm_cache)  # after any change, rebuild the screens in the background


_warm_lock = threading.Lock()
_warm_again = threading.Event()


def _warm_cache():
    """Pre-load the screen data so the next page opened is already fast. One warm-up at a time: a change that
    arrives while one is running just makes it run once more afterwards."""
    if not _warm_lock.acquire(blocking=False):
        _warm_again.set()
        return
    try:
        while True:
            _warm_again.clear()
            _warm_once()
            if not _warm_again.is_set():
                break
    finally:
        _warm_lock.release()


def _warm_once():
    from app import dashboard, tabs
    try:
        dashboard.master()
        dashboard.action_catalog()
        f = dashboard.filters()  # the screens' default selection (this week)
        for fn in (dashboard.summary, tabs.stuck, tabs.access_issues, tabs.at_risk, tabs.call_summary, dashboard.hub_quality,
                   dashboard.executive, dashboard.patient_calls, dashboard.alerts, dashboard.brief, dashboard.follow_through,
                   dashboard.safety):
            fn(f=f)
        for p in dashboard.patients():
            if p["recorded"]:  # simulated patients' journeys are built on first open
                dashboard.journey(p["patient_id"])
    except Exception:  # warming is best effort
        pass


def _process_and_recompute(call_id):
    """Process one call, then refresh the cross-call insights so the screens reflect it."""
    if process_call(call_id)["status"] == "completed":
        recompute()
    clear_cache()


@app.get("/v1/health")
def health():
    return {"status": "ok"}


@app.post("/v1/calls", status_code=201)
async def upload_call(
    background: BackgroundTasks,
    audio: UploadFile = File(..., description="Call recording (mp3 / wav / m4a). Stereo: one party per channel."),
    transcript: Optional[UploadFile] = File(None, description="Optional transcript; if given, transcription is skipped."),
    external_call_id: Optional[str] = Form(None),
    call_datetime: Optional[str] = Form(None, description="ISO date-time of the call"),
    direction: Optional[str] = Form(None, description="Inbound | Outbound"),
    staff_id: Optional[str] = Form(None, description="Hub agent ID from the phone system"),
    case_id: Optional[str] = Form(None, description="Hub case ID from the phone system, if attached"),
    channel_layout: Optional[str] = Form(None, description='JSON, e.g. {"0": "hub staff", "1": "provider office"}'),
    process: bool = Form(True),
):
    suffix = Path(audio.filename or "call.mp3").suffix or ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    text = (await transcript.read()).decode("utf-8", errors="replace") if transcript else None
    try:
        layout = json.loads(channel_layout) if channel_layout else None
        call_id = register_call(tmp_path, {
            "external_call_id": external_call_id, "call_datetime": call_datetime, "direction": direction,
            "staff_id": staff_id, "case_id": case_id, "channel_layout": layout,
        }, transcript_text=text)
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if process:
        background.add_task(_process_and_recompute, call_id)
    return {"call_id": str(call_id), "status": "pending", "transcript_supplied": text is not None}


@app.post("/v1/calls/{call_id}/process")
def reprocess(call_id: UUID, background: BackgroundTasks):
    if not fetch_one("SELECT 1 FROM ci_calls WHERE call_id = %s", (call_id,)):
        raise HTTPException(status_code=404, detail="Call not found")
    background.add_task(_process_and_recompute, call_id)
    return {"call_id": str(call_id), "status": "queued"}


@app.get("/v1/calls")
def list_calls():
    return fetch_all(
        """SELECT c.call_id, c.external_call_id, c.call_datetime, c.direction, c.status, c.transcript_source,
                  c.case_id, c.patient_id, c.practice_id, c.payer_id, c.program_id, c.other_party_type, c.journey_stage,
                  (SELECT count(*) FROM ci_call_signals s WHERE s.call_id = c.call_id) AS signal_count
           FROM ci_calls c ORDER BY c.call_datetime NULLS LAST, c.created_at""")


@app.get("/v1/calls/{call_id}")
def get_call(call_id: UUID):
    call = fetch_one("SELECT * FROM ci_calls WHERE call_id = %s", (call_id,))
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    q = "SELECT * FROM {} WHERE call_id = %s ORDER BY {}"
    return {
        "call": call,
        "extraction": fetch_one("SELECT * FROM ci_call_extractions WHERE call_id = %s", (call_id,)),
        "segments": fetch_all(q.format("ci_call_segments", "seq"), (call_id,)),
        "entities": fetch_all(q.format("ci_call_entities", "id"), (call_id,)),
        "signals": fetch_all(
            """SELECT cs.*, s.signal_name, s.insight_type FROM ci_call_signals cs
               JOIN ci_signals s ON s.signal_id = cs.signal_id WHERE cs.call_id = %s ORDER BY cs.timestamp_s""", (call_id,)),
        "promises": fetch_all(q.format("ci_call_promises", "timestamp_s"), (call_id,)),
        "documents": fetch_all(q.format("ci_call_documents", "id"), (call_id,)),
    }


@app.get("/v1/signals")
def list_signals():
    return fetch_all("SELECT * FROM ci_signals ORDER BY signal_id")
