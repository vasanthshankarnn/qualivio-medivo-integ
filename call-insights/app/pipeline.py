"""Call pipeline: register -> transcribe (or use a supplied transcript) -> AI extraction -> label resolution -> store."""
import json
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

import psycopg2.extras

from app.config import CI_BLOB_PREFIX, DATA_DIR
from app.db import fetch_all, fetch_one, get_conn
from app.logger import logger
from app.services import audio
from app.services.extraction import CallExtraction, SignalHit, extract
from app.services.resolver import resolve, resolve_staff
from app.services.transcript_parser import parse_transcript

AUDIO_DIR = DATA_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_STEREO_LAYOUT = {"0": "hub staff", "1": "other party"}


def _set_status(call_id, status, error=None):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE ci_calls SET status = %s, error = %s, updated_at = NOW() WHERE call_id = %s",
                    (status, error, call_id))


def _store_segments(cur, call_id, segments, source):
    cur.execute("DELETE FROM ci_call_segments WHERE call_id = %s", (call_id,))
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO ci_call_segments (call_id, seq, start_s, end_s, channel, speaker_label, speaker_role, text) VALUES %s",
        [(call_id, i, s["start_s"], s["end_s"], s.get("channel"), s["speaker_label"], s.get("speaker_role"), s["text"])
         for i, s in enumerate(segments)],
    )
    cur.execute("UPDATE ci_calls SET transcript_source = %s, updated_at = NOW() WHERE call_id = %s", (source, call_id))


def register_call(audio_path: str, metadata: dict, transcript_text: str | None = None) -> uuid.UUID:
    """Create the call record, keep a local copy of the audio and, if given, store the supplied transcript."""
    src = Path(audio_path)
    info = audio.probe(str(src))
    call_id = uuid.uuid4()
    local = AUDIO_DIR / f"{call_id}{src.suffix.lower()}"
    shutil.copyfile(src, local)
    layout = metadata.get("channel_layout") or (DEFAULT_STEREO_LAYOUT if info["channels"] >= 2 else None)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ci_calls (call_id, external_call_id, call_datetime, direction, staff_id, case_id,
                                     channel_layout, audio_filename, audio_duration_s, audio_channels)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (call_id, metadata.get("external_call_id"), metadata.get("call_datetime"), metadata.get("direction"),
             metadata.get("staff_id"), metadata.get("case_id"), json.dumps(layout) if layout else None,
             src.name, round(info["duration_s"], 2), info["channels"]),
        )
        if transcript_text:
            segments = parse_transcript(transcript_text)
            if not segments:
                raise ValueError("Transcript has no '[mm:ss] Speaker: text' lines")
            _store_segments(cur, call_id, segments, "provided")
    logger.info("Registered call %s (%s)", metadata.get("external_call_id") or call_id, src.name)
    return call_id


def _transcribe(call: dict) -> list[dict]:
    from app.services.azure_batch import AzureBatchTranscriber
    from app.services.blob_storage import BlobStorage

    local = next(AUDIO_DIR.glob(f"{call['call_id']}.*"))
    stereo = (call["audio_channels"] or 1) >= 2
    mp3 = AUDIO_DIR / f"{call['call_id']}_transcribe.mp3"
    audio.to_transcription_mp3(str(local), str(mp3), keep_stereo=stereo)
    blob = BlobStorage()
    key = blob.upload_file(f"{CI_BLOB_PREFIX}/{call['call_id']}/audio.mp3", str(mp3))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE ci_calls SET audio_blob_key = %s WHERE call_id = %s", (key, call["call_id"]))
    phrases = AzureBatchTranscriber().transcribe(blob.sas_url(key), f"ci-{call['call_id']}", stereo=stereo)
    layout = call["channel_layout"] or {}
    for p in phrases:
        if stereo:
            role = layout.get(str(p["channel"]), f"channel {p['channel']}")
            p["speaker_label"], p["speaker_role"] = f"Channel {p['channel']} ({role})", role
        else:  # mono: Azure still reports channel 0; who spoke comes from diarization (and the AI), not a channel
            p["channel"] = None
            p["speaker_label"], p["speaker_role"] = f"Speaker {p.get('speaker') or '?'}", None
    mp3.unlink(missing_ok=True)
    return phrases


def _seconds(ts):
    try:
        m, s = str(ts).split(":")[-2:]
        return int(m) * 60 + int(s)
    except (ValueError, TypeError):
        return None


def _date_or_none(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def relabel_call(call_id) -> dict:
    """Re-run label resolution on the stored AI output (no new AI call), e.g. after master-data or matching changes."""
    call = fetch_one("SELECT * FROM ci_calls WHERE call_id = %s", (call_id,))
    ext = fetch_one("SELECT raw FROM ci_call_extractions WHERE call_id = %s", (call_id,))
    if not call or not ext:
        return {"call_id": str(call_id), "status": "skipped"}
    labels, entity_rows = resolve(CallExtraction.model_validate(ext["raw"]), {"case_id": call["case_id"]})
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM ci_call_entities WHERE call_id = %s", (call_id,))
        psycopg2.extras.execute_values(
            cur, "INSERT INTO ci_call_entities (call_id, entity_type, heard_text, resolved_id, match_method, confidence) VALUES %s",
            [(call_id, r["entity_type"], r["heard_text"], r["resolved_id"], r["match_method"], r["confidence"]) for r in entity_rows])
        cur.execute("""UPDATE ci_calls SET patient_id = %s, practice_id = %s, prescriber_id = %s, payer_id = %s, program_id = %s,
                           updated_at = NOW() WHERE call_id = %s""",
                    (labels["patient_id"], labels["practice_id"], labels["prescriber_id"], labels["payer_id"],
                     labels["program_id"], call_id))
    return {"call_id": str(call_id), "status": "relabelled", **labels}


def process_call(call_id) -> dict:
    call = fetch_one("SELECT * FROM ci_calls WHERE call_id = %s", (call_id,))
    if not call:
        raise ValueError(f"Call {call_id} not found")
    try:
        segments = fetch_all("SELECT * FROM ci_call_segments WHERE call_id = %s ORDER BY seq", (call_id,))
        if not segments:  # no supplied transcript: transcribe the audio
            _set_status(call_id, "transcribing")
            phrases = _transcribe(call)
            with get_conn() as conn, conn.cursor() as cur:
                _store_segments(cur, call_id, phrases, "azure")
            segments = fetch_all("SELECT * FROM ci_call_segments WHERE call_id = %s ORDER BY seq", (call_id,))

        _set_status(call_id, "extracting")
        staff = fetch_one("SELECT * FROM ci_staff WHERE staff_id = %s", (call["staff_id"],)) if call["staff_id"] else None
        when = call["call_datetime"]
        context = {
            "call date": when.strftime("%A %Y-%m-%d %H:%M") if isinstance(when, datetime) else when,
            "direction": call["direction"],
            "hub agent on the call": f"{staff['staff_name']} ({staff['role']}, {staff['organisation']})" if staff else None,
            "case id": call["case_id"],
            "audio channels": ", ".join(f"channel {k} = {v}" for k, v in (call["channel_layout"] or {}).items())
            if call["transcript_source"] == "azure" else None,
        }
        signals = fetch_all("SELECT * FROM ci_signals ORDER BY signal_id")
        result, meta = extract(segments, context, signals)
        labels, entity_rows = resolve(result, {"case_id": call["case_id"]})
        # Agent: phone-system metadata first; otherwise the hub-side speaker's name heard on the call.
        staff_id = call["staff_id"] or resolve_staff(result)
        known = {s["signal_id"] for s in signals}

        with get_conn() as conn, conn.cursor() as cur:
            for table in ("ci_call_entities", "ci_call_signals", "ci_call_promises", "ci_call_documents",
                          "ci_call_safety", "ci_call_extractions"):
                cur.execute(f"DELETE FROM {table} WHERE call_id = %s", (call_id,))
            cur.execute(
                """INSERT INTO ci_call_extractions (call_id, model, summary, other_party_type, journey_stage,
                       identity_verified, identity_quote, sentiment, sentiment_reason, raw, prompt_tokens, output_tokens,
                       contact_reason, resolved_on_call, resolution_note)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (call_id, meta["model"], result.summary, result.other_party_type, result.journey_stage,
                 result.identity_verified, result.identity_quote, result.other_party_sentiment, result.sentiment_reason,
                 json.dumps(result.model_dump()), meta["prompt_tokens"], meta["output_tokens"],
                 result.contact_reason, result.resolved_on_call, result.resolution_note),
            )
            psycopg2.extras.execute_values(
                cur, "INSERT INTO ci_call_entities (call_id, entity_type, heard_text, resolved_id, match_method, confidence) VALUES %s",
                [(call_id, r["entity_type"], r["heard_text"], r["resolved_id"], r["match_method"], r["confidence"]) for r in entity_rows])
            hits = [h for h in result.signals if h.signal_id in known]
            # S37 mirrors identity_verified deterministically, so the flag and the signal never disagree.
            hits = [h for h in hits if h.signal_id != "S37"]
            if result.identity_verified and "S37" in known:
                hits.append(SignalHit(signal_id="S37", quote=result.identity_quote or "", timestamp=None,
                                      speaker_role="hub_staff", confidence=1.0))
            # S08 (promise with a date) mirrors the extracted promises that carry a time reference.
            dated = [p for p in result.promises if p.due_text or p.due_date]
            if dated and "S08" in known and not any(h.signal_id == "S08" for h in hits):
                hits.append(SignalHit(signal_id="S08", quote=dated[0].quote, timestamp=dated[0].timestamp,
                                      speaker_role=dated[0].made_by_role, confidence=1.0))
            # S33 / S34 mirror the structured safety findings, so the queue and the signals always agree.
            hits = [h for h in hits if h.signal_id not in ("S33", "S34")]
            for m in result.safety_mentions:
                if m.kind == "adverse_event" and "S33" in known:
                    hits.append(SignalHit(signal_id="S33", quote=m.quote, timestamp=m.timestamp, speaker_role="patient", confidence=1.0))
            for q in result.medical_questions:
                if "S34" in known:
                    hits.append(SignalHit(signal_id="S34", quote=q.question, timestamp=q.timestamp, speaker_role=q.asked_by, confidence=1.0))
            safety = [(m.kind, None, m.mention, m.quote, _seconds(m.timestamp), None, m.acknowledged) for m in result.safety_mentions
                      if m.kind in ("adverse_event", "quality_complaint")]
            safety += [("medical_question", q.topic, q.question, q.question, _seconds(q.timestamp), q.asked_by,
                        q.referred and not q.hub_answered_medically) for q in result.medical_questions]
            safety += [("dosing_mistake", None, h.quote, h.quote, _seconds(h.timestamp), h.speaker_role, None)
                       for h in hits if h.signal_id == "S32"]
            if safety:
                ext_id = call["external_call_id"] or str(call_id)
                psycopg2.extras.execute_values(
                    cur, """INSERT INTO ci_call_safety (call_id, kind, topic, mention, quote, timestamp_s, asked_by, handled_ok, safety_key)
                            VALUES %s""",
                    [(call_id, *row, f"{ext_id}|{row[0]}|{int(row[4] or 0)}|{i}") for i, row in enumerate(safety)])
            if hits:
                psycopg2.extras.execute_values(
                    cur, "INSERT INTO ci_call_signals (call_id, signal_id, quote, timestamp_s, speaker_role, confidence) VALUES %s",
                    [(call_id, h.signal_id, h.quote, _seconds(h.timestamp), h.speaker_role, h.confidence) for h in hits])
            if result.promises:
                psycopg2.extras.execute_values(
                    cur, "INSERT INTO ci_call_promises (call_id, made_by_role, action, due_text, due_date, quote, timestamp_s) VALUES %s",
                    [(call_id, p.made_by_role, p.action, p.due_text, _date_or_none(p.due_date), p.quote, _seconds(p.timestamp))
                     for p in result.promises])
            doc_types = {"payer_required": "payer_required", "requested_from_office": "requested_from_office",
                         "missing_items": "missing_item", "confirmed_sent": "confirmed_sent"}
            docs = [(call_id, doc_types[kind], item) for kind, items in result.documents.model_dump().items()
                    for item in items if item and item.strip()]
            if docs:
                psycopg2.extras.execute_values(cur, "INSERT INTO ci_call_documents (call_id, list_type, item) VALUES %s", docs)
            cur.execute(
                """UPDATE ci_calls SET patient_id = %s, practice_id = %s, prescriber_id = %s, payer_id = %s, program_id = %s,
                       staff_id = %s, other_party_type = %s, journey_stage = %s, status = 'completed', error = NULL,
                       processed_at = NOW(), updated_at = NOW()
                   WHERE call_id = %s""",
                (labels["patient_id"], labels["practice_id"], labels["prescriber_id"], labels["payer_id"],
                 labels["program_id"], staff_id, result.other_party_type, result.journey_stage, call_id),
            )
        dropped = [h.signal_id for h in result.signals if h.signal_id not in known]
        if dropped:
            logger.warning("Call %s: ignored unknown signal ids %s", call_id, dropped)
        logger.info("Processed call %s: %d signals, %d promises", call["external_call_id"] or call_id, len(hits), len(result.promises))
        return {"call_id": str(call_id), "status": "completed", "signals": len(hits)}
    except Exception as e:
        logger.exception("Call %s failed", call_id)
        _set_status(call_id, "failed", str(e)[:2000])
        return {"call_id": str(call_id), "status": "failed", "error": str(e)}
