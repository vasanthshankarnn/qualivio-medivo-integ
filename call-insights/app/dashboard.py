"""Endpoints for the insight workspace screens (deck slides 16-20), plus the few writes the screens make
(insight status / owner / feedback and safety review). Every screen takes the same filters as the deck's filter bar."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from urllib.parse import quote as urlquote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import engines, mock
from app.analytics import (DROP_OFF, FRICTION_TYPES, MEANING, NOT_A_REASON, PARTIES, PARTY_OF_CALL, PAYER_REQUIREMENT,
                           SCORE_AREAS, STAGE_ORDER, STAGE_TITLE, Data, Filters, demo_scores, display_payer, pct, vs_pct,
                           vs_rate)
from app.cache import cached, clear as clear_cache
from app.engines import WAIT_DAYS, capped
from app.db import fetch_all, fetch_one, get_conn
from app.pipeline import AUDIO_DIR
from app.rules import AS_OF, recompute
from app.services.extraction import CONTACT_REASONS, MEDICAL_TOPICS

router = APIRouter(prefix="/v1")

RULE_LABEL = {"R1": "Asked vs told", "R2": "Practice friction", "R3": "Drop-off risk", "R4": "Call close",
              "R6": "Promise not kept", "SAFETY": "Safety review", "IDCHECK": "Identity check"}
SEVERITY = {"R3": 0, "SAFETY": 0, "R6": 1, "R1": 2, "R4": 3, "R2": 4, "IDCHECK": 9}
KIND_LABEL = {"adverse_event": "Possible adverse event", "quality_complaint": "Quality complaint",
              "medical_question": "Medical Information question", "dosing_mistake": "Dosing mistake"}
SUGGESTED_ROUTE = {"adverse_event": "pharmacovigilance", "dosing_mistake": "pharmacovigilance",
                   "medical_question": "medical_information", "quality_complaint": "quality_complaint"}
STATUSES = ("new", "open", "in_progress", "watching", "fixed", "expected")


DEFAULT_DAYS = 7


def filters(program: str | None = None, stage: str | None = None, payer: str | None = None, days: str | None = None,
            sp: str | None = None) -> Filters:
    """The filter bar. The period defaults to this week (last 7 days); days=all selects every analysed call."""
    n = 0 if days == "all" else int(days) if days and days.isdigit() else DEFAULT_DAYS
    return Filters(program or None, stage or None, payer or None, n, sp or None)


@cached
def get_data(f: Filters) -> Data:
    return Data(f)


def _base(d: Data) -> dict:
    return {"as_of": AS_OF.isoformat(), "period_start": d.start.isoformat(), "weeks": round(d.weeks, 1),
            "conversations": len(d.calls),
            "baseline_note": "Normal = the 13 weeks before the period"}


def _heard(labels) -> str:
    """Top things heard, as one phrase: 'Office staff unavailable · repeat contact / callback'."""
    top = [l for l, _ in Counter(labels).most_common(2)]
    return " · ".join([top[0]] + [t[0].lower() + t[1:] for t in top[1:]]) if top else ""


def _rate_text(v: dict) -> dict:
    """Uniform 'vs normal' cell: ratio text, direction and a plain-language detail."""
    ratio = v["ratio"]
    return {"text": f"{ratio:g}×" if ratio is not None else "–", "direction": v["direction"], "score": ratio or 0,
            "detail": f"{v['count']} mentions · {v['per_week']:g} a week vs normal {v['normal']:g}"}


# ====================================================================== shared lookups
@router.post("/insights/recompute")
def recompute_insights():
    result = recompute()
    clear_cache()
    return result


@router.get("/insights")
@cached
def insights(rule_id: str | None = None, subject_type: str | None = None):
    sql = "SELECT i.*, a.priority, a.insight_type FROM ci_insights i LEFT JOIN ci_action_catalog a USING (rule_id) WHERE 1=1"
    params = []
    if rule_id:
        sql += " AND i.rule_id = %s"
        params.append(rule_id)
    if subject_type:
        sql += " AND i.subject_type = %s"
        params.append(subject_type)
    return fetch_all(sql + " ORDER BY i.rule_id, i.subject_id", params)


@router.get("/actions")
@cached
def action_catalog():
    return fetch_all("SELECT * FROM ci_action_catalog ORDER BY rule_id")


@router.get("/rule-weights")
@cached
def rule_weights():
    return fetch_all("""SELECT w.*, s.signal_name FROM ci_rule_weights w LEFT JOIN ci_signals s USING (signal_id)
                        ORDER BY w.rule_id, w.signal_id""")


@router.get("/master")
@cached
def master():
    out = {
        "practices": fetch_all("SELECT * FROM ci_practices ORDER BY practice_name"),
        "payers": [p for p in fetch_all("SELECT * FROM ci_payers ORDER BY payer_name") if display_payer(p["payer_name"])],
        "programs": fetch_all("SELECT * FROM ci_programs ORDER BY program_name"),
        "staff": fetch_all("SELECT * FROM ci_staff ORDER BY staff_name"),
        "pharmacies": [],
        "stages": STAGE_ORDER,
        "as_of": AS_OF.isoformat(),
    }
    if mock.ENABLED:
        ids = {"programs": "program_id", "payers": "payer_id", "pharmacies": "sp_id", "practices": "practice_id",
               "staff": "staff_id"}
        for k, rows in mock.master_additions().items():
            have = {r[ids[k]] for r in out[k]}
            out[k] = out[k] + [r for r in rows if r[ids[k]] not in have]
        for k, name in (("practices", "practice_name"), ("payers", "payer_name"), ("programs", "program_name"),
                        ("pharmacies", "sp_name")):
            out[k] = sorted(out[k], key=lambda r: r[name])
    return out


# ====================================================================== Screen 1 · Overview
@router.get("/dashboard/overview")
@cached
@capped
def overview(f: Filters = Depends(filters)):
    d = get_data(f)
    calls, items, b = d.calls, d.friction(), d.baseline
    fcr, fcr_calls = d.fcr(calls)
    rep, rep_calls = d.repeat_pct(calls)
    gap = [i for i in d.open_insights if i["patient"] and i["rule_id"] != "IDCHECK"]
    gap_patients = {i["patient"]["patient_id"] for i in gap}
    drop = [(c, s) for c in calls for s in d.sig[c["call_id"]] if s["signal_id"] in DROP_OFF]
    ae = [s for s in _safety_rows(d) if s["kind"] in ("adverse_event", "dosing_mistake")]

    with_reason = [c for c in calls if c["contact_reason"]]
    reasons = []
    for r in CONTACT_REASONS:
        cs = [c for c in with_reason if c["contact_reason"] == r]
        share, normal = pct(len(cs), len(with_reason)), b["contact_reason_share"].get(r)
        reasons.append({"reason": r, "count": len(cs), "share": share or 0, "normal": normal,
                        "above": bool(share is not None and normal is not None and share - normal >= 5 and len(cs) >= 2),
                        "evidence": [d.ev(c, c["resolution_note"], r) for c in cs]})
    reasons.sort(key=lambda x: (x["reason"] == "Other", -x["share"]))

    current = d.current_stage()
    stages = []
    for st in STAGE_ORDER:
        cs = [c for c in calls if c["journey_stage"] == st]
        st_items = [i for i in items if i["stage"] == st]
        top = Counter(i["type"] for i in st_items).most_common(1) or Counter(
            s["signal_name"] for c in cs for s in d.sig[c["call_id"]] if s["signal_id"] not in NOT_A_REASON).most_common(1)
        stages.append({"stage": st, "calls": len(cs), "open_gaps": len({p for p in gap_patients if current.get(p) == st}),
                       "repeat": d.repeat_pct(cs)[0], "fcr": d.fcr(cs)[0], "top_reason": top[0][0] if top else None,
                       "evidence": st_items or [d.ev(c, c["resolution_note"], c["contact_reason"]) for c in cs]})

    rows = engines.access_issues(d)
    return {
        **_base(d),
        "kpis": {
            "interactions": {"value": len(calls), "patients": len({c["patient_id"] for c in calls if c["patient_id"]}),
                             "channels": 1, "evidence": [d.ev(c, c["summary"], c["contact_reason"]) for c in calls]},
            "fcr": {"value": fcr, "vs": vs_pct(fcr, b["fcr"].get("all")), "of": len(fcr_calls),
                    "evidence": [d.ev(c, c["resolution_note"], "Resolved on the call" if c["resolved_on_call"] else "Left outstanding")
                                 for c in fcr_calls]},
            "repeat": {"value": rep, "vs": vs_pct(rep, b["repeat_7d"].get("all")), "of": len(rep_calls),
                       "evidence": [d.ev(c, c["resolution_note"], "Followed by another contact within 7 days")
                                    for c in rep_calls if d.repeat_7d(c)]},
            "open_gap": {"value": len(gap_patients), "evidence": [e for i in gap for e in d.insight_evidence(i)]},
            "drop_off": {"value": len(drop), "patients": len({c["patient_id"] for c, _ in drop}),
                         "vs": _rate_text(vs_rate(len(drop), d.weeks, b["drop_off_weekly"].get("all"))),
                         "evidence": [d.ev(c, s["quote"], s["signal_name"]) for c, s in drop]},
            "safety": {"value": len(ae), "to_review": sum(1 for s in ae if s["status"] == "awaiting"),
                       "evidence": [s["evidence"] for s in ae]},
        },
        "reasons": reasons,
        "stages": stages,
        "what_changed": _what_changed(d, reasons, rows, fcr, gap),
        "opportunity": _opportunity(items),
        "watchlist": _watchlist(d, gap),
    }


# ====================================================================== Executive dashboard (Qualivio's component)
@router.get("/dashboard/executive")
@cached
@capped
def executive(f: Filters = Depends(filters)):
    """Call volume and duration by direction, and what the calls were about (Qualivio 'Executive dashboard')."""
    d = get_data(f)
    calls = d.calls
    total = len(calls)
    secs = [float(c["audio_duration_s"] or 0) for c in calls]
    answered = [float(c["audio_duration_s"]) for c in calls if c["live"] and c["audio_duration_s"]]  # as on the summary

    def side(direction):
        cs = [c for c in calls if (c["direction"] or "").lower() == direction]
        types = Counter(c["contact_reason"] or "Other" for c in cs)
        return {
            "count": len(cs), "share": pct(len(cs), total) or 0,
            "weekly": [{"label": w, "count": n} for w, n in zip(engines.week_labels(13), engines.series(
                [c["day"] for c in d.scope if (c["direction"] or "").lower() == direction], 13))],
            "types": [{"type": t, "count": n, "share": pct(n, len(cs)),
                       "evidence": [d.ev(c, c["resolution_note"], t) for c in cs if (c["contact_reason"] or "Other") == t]}
                      for t, n in types.most_common()],
            "evidence": [d.ev(c, c["summary"], c["contact_reason"]) for c in cs],
        }

    return {
        **_base(d),
        "inbound": side("inbound"),
        "outbound": side("outbound"),
        "total": total,
        "agents": len({c["staff_id"] for c in calls if c["staff_id"]}),
        "total_seconds": round(sum(secs)),
        "avg_seconds": round(sum(answered) / len(answered)) if answered else 0,
        "evidence": [d.ev(c, c["summary"], c["contact_reason"]) for c in calls],
    }


# ====================================================================== Patient dashboard + conversation (Qualivio's screens)
@router.get("/dashboard/patient-calls")
@cached
def patient_calls(f: Filters = Depends(filters), patient: str | None = None):
    """Qualivio's agent dashboard, organised by patient: every call, its duration and scores.
    The five scores are MOCK values (see analytics.demo_scores)."""
    d = get_data(f)
    # recorded calls only: each one opens to its transcript and audio
    real = [c for c in d.calls if not c["mock"]]
    calls = [c for c in real if not patient or c["patient_id"] == patient]
    rows = []
    for c in sorted(calls, key=lambda c: c["call_datetime"], reverse=True):
        rows.append({"call_id": str(c["call_id"]), "external_call_id": c["external_call_id"], "date": c["call_datetime"].isoformat(),
                     "patient_id": c["patient_id"], "patient_name": c["patient_name"] or "Not identified", "case_id": c["case_id"],
                     "party": PARTY_OF_CALL.get(c["other_party_type"], "Other"), "staff_name": c["staff_name"],
                     "duration_s": float(c["audio_duration_s"] or 0), "signals": len(d.sig[c["call_id"]]),
                     "scores": demo_scores(c["call_id"])})
    secs = [r["duration_s"] for r in rows]
    avg = {a: round(sum(r["scores"][a] for r in rows) / len(rows), 1) if rows else None for a in SCORE_AREAS}
    people = sorted({(c["patient_id"], c["patient_name"], c["case_id"]) for c in real if c["patient_id"]}, key=lambda p: p[1] or "")
    return {**_base(d), "calls": rows, "count": len(rows), "total_seconds": round(sum(secs)),
            "avg_seconds": round(sum(secs) / len(secs)) if secs else 0, "scores": avg,
            "patients": [{"patient_id": i, "patient_name": n, "case_id": k} for i, n, k in people], "scores_are_mock": True}


@router.get("/calls/{call_id}/conversation")
@cached
def conversation(call_id: UUID):
    """Conversation analysis page: patient, date, signal count, mock scores and the transcript timeline."""
    d = get_data(Filters())
    c = d.by_id.get(UUID(str(call_id)))
    if not c:
        raise HTTPException(status_code=404, detail="Call not found (or not processed yet)")
    segs = sorted(fetch_all("SELECT * FROM ci_call_segments WHERE call_id = %s ORDER BY seq", (c["call_id"],)),
                  key=lambda s: float(s["start_s"] or 0))
    return {"call_id": str(c["call_id"]), "external_call_id": c["external_call_id"], "date": c["call_datetime"].isoformat(),
            "patient_id": c["patient_id"], "patient_name": c["patient_name"] or "Not identified", "case_id": c["case_id"],
            "staff_name": c["staff_name"], "party": PARTY_OF_CALL.get(c["other_party_type"], "Other"),
            "duration_s": float(c["audio_duration_s"] or 0), "signals": d.sig[c["call_id"]],
            "speakers": c["raw"].get("speakers", []), "segments": segs, "scores": demo_scores(c["call_id"]), "scores_are_mock": True}


# ====================================================================== Screen 1 · Executive summary
STAGE_PLAIN = {"Prior authorization & appeal": "prior authorization", "Specialty pharmacy & first fill": "specialty pharmacy",
               "Benefits verification": "benefits check", "Copay & assistance": "copay help", "Adherence & refill": "refills"}


def plural_n(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


@router.get("/dashboard/summary")
@cached
@capped
def summary(f: Filters = Depends(filters)):
    """One page for leaders. Each box is also its own tab (Neil, 16 Oct): stuck stages, emerging access issues,
    patients at risk, call summary – the same engines, so the numbers match."""
    d = get_data(f)
    ov = overview(f=f)
    b, calls = d.baseline, d.calls
    st = engines.stuck(d)
    stages = [{**{k: x[k] for k in ("stage", "short", "slug", "calls", "patients", "waiting", "friction", "longest_days",
                                    "status", "ongoing")}, "evidence": x["evidence_waiting"] + x["evidence"]} for x in st["stages"]]
    slow = next((x for x in st["stages"] if x["stage"] == st["slowest"]), None)
    rows = engines.access_issues(d)
    hot = [r for r in rows if r["status"] in ("New", "Rising")]
    top_issues = [{"label": r["title"], "vs": f"{r['vs']} normal" if r["vs"].endswith("×") else r["vs"], "key": r["key"],
                   "status": r["status"], "evidence": r["evidence"]} for r in hot[:3]]
    rp = engines.risk_page(d)
    flagged = [x for x in rp["patients"] if x["level"] != "Low"]
    risk_calls = {e["call_id"] for x in engines.at_risk(d) if x["level"] != "Low" for e in x["evidence"]}
    answered = [c for c in calls if c["live"] and c["resolved_on_call"] is not None]
    reasons = [{"reason": c["label"], "key": c["key"], "patients": c["flagged"], "evidence": c["evidence"]}
               for c in rp["categories"] if c["flagged"]][:4]

    # Hub at a glance.
    prev = None
    if f.days:
        lo, hi = d.start - timedelta(days=f.days), d.start - timedelta(days=1)
        prev = sum(1 for c in d.scope if lo <= c["day"] <= hi)
    live = [c for c in calls if c["live"] and c["audio_duration_s"]]
    by_reason = defaultdict(list)
    for c in live:
        by_reason[c["contact_reason"] or "Other"].append(float(c["audio_duration_s"]))
    longest = max(by_reason.items(), key=lambda kv: sum(kv[1]) / len(kv[1]), default=(None, []))[0]
    safety_rows = [x for x in _safety_rows(d) if x["kind"] in ("adverse_event", "dosing_mistake")]
    reviewed = [x for x in safety_rows if x["status"] != "awaiting"]
    k = ov["kpis"]
    return {
        **_base(d),
        "stuck": {"stages": stages, "wait_days": WAIT_DAYS,
                  "slowest": slow and {"stage": slow["stage"], "slug": slow["slug"], "waiting": slow["waiting"],
                                       "longest_days": slow["longest_days"],
                                       "top_reason": slow["reasons"][0]["name"] if slow["reasons"] else None,
                                       "evidence": slow["evidence_waiting"]}},
        "issues": {"count": len(hot), "new": sum(1 for r in hot if r["status"] == "New"), "top": top_issues,
                   "calls": len({e["call_id"] for r in hot for e in r["evidence"]})},
        "risk": {"patients": len(flagged), "new_this_week": rp["kpis"]["new_this_week"], "reasons": reasons,
                 "calls": len(risk_calls),
                 "evidence": [e for x in flagged for e in x["evidence"]]},
        "glance": {
            "conversations": {"value": len(calls), "previous": prev, "change_pct": pct(len(calls) - prev, prev) if prev else None,
                              "evidence": k["interactions"]["evidence"]},
            "fcr": {"value": k["fcr"]["value"], "target": b["fcr_target"].get("all"), "evidence": k["fcr"]["evidence"],
                    "of": len(answered), "resolved": sum(1 for c in answered if c["resolved_on_call"])},
            "repeat": {"value": k["repeat"]["value"], "vs": k["repeat"]["vs"], "evidence": k["repeat"]["evidence"]},
            "avg_call": {"minutes": round(sum(sum(v) for v in by_reason.values()) / max(1, len(live)) / 60, 1) if live else None,
                         "longest": longest},
            "side_effects": {"value": len(safety_rows), "awaiting": len(safety_rows) - len(reviewed),
                             "max_hours": max((x["hours_to_review"] or 0 for x in reviewed), default=None),
                             "evidence": [x["evidence"] for x in safety_rows]},
        },
        "reasons": [r for r in ov["reasons"] if r["count"]],  # every reason: they add up to the calls
        "what_changed": ov["what_changed"][:4],
    }


OWNER_BY_PARTY = {"Physician office": "Field Access", "Payer": "Market Access", "Patient": "Patient Services",
                  "Specialty pharmacy": "Trade / pharmacy lead"}


# ====================================================================== v2 Screen 5 · Hub quality & safety
@router.get("/dashboard/hub-quality")
@cached
@capped
def hub_quality(f: Filters = Depends(filters)):
    """Eight operational focus areas, each with one number, the reason behind it and the fix (deck screen 5)."""
    d = get_data(f)
    ft, sm, saf = follow_through(f=f), summary(f=f), safety(f=f)
    k, b = ft["kpis"], d.baseline
    by_reason = {r["reason"]: r for r in ft["by_reason"]}
    worst_fcr = min((r for r in ft["by_reason"] if r["fcr"] is not None), key=lambda r: r["fcr"], default=None)
    worst_rep = max((r for r in ft["by_reason"] if r["repeat"]), key=lambda r: r["repeat"], default=None)
    live = [c for c in d.calls if c["live"]]
    transfers = [(c, blk) for c in live for blk in c["raw"].get("hold_or_transfer", []) if blk.get("kind") == "transfer"]
    handoffs = [(c, h) for c in live for h in c["raw"].get("handoffs", [])]
    id_needed = [c for c in live if c["other_party_type"] in ("provider_office", "patient", "caregiver", "payer")]
    id_ok = [c for c in id_needed if c["identity_verified"]]
    hub_items = [i for i in d.friction() if i["with"] == "Hub process"]
    topics = Counter(i["label"] for i in hub_items)
    train = [(t, n) for t, n in topics.most_common() if n >= 2]
    fcr_t = b["fcr_target"].get("all")
    longest = sm["glance"]["avg_call"]["longest"]
    longest_min = round(sum(float(c["audio_duration_s"] or 0) for c in live if c["contact_reason"] == longest) /
                        max(1, sum(1 for c in live if c["contact_reason"] == longest)) / 60, 1) if longest else None

    def card(key, title, value, unit, ok, why, fix, evidence):
        return {"key": key, "title": title, "value": value, "unit": unit, "status": "On track" if ok else "Watch",
                "tone": "green" if ok else "amber", "why": why, "fix": fix, "evidence": evidence}

    cards = [
        card("fcr", "First-call resolution", f"{k['fcr']['value']}%" if k["fcr"]["value"] is not None else "—",
             f"target {fcr_t:g}%" if fcr_t else "", (k["fcr"]["value"] or 0) >= (fcr_t or 0),
             (f"Lowest for {worst_fcr['reason'].lower()} calls ({worst_fcr['fcr']}%): {str(worst_fcr['root_cause'] or 'item left open').lower()}"
              if worst_fcr else "No calls in this period"),
             "Close every call with the next step, an owner and a date", by_reason[worst_fcr["reason"]]["evidence"] if worst_fcr else []),
        card("handle", "Handle time", f"{sm['glance']['avg_call']['minutes']:g} min" if sm["glance"]["avg_call"]["minutes"] else "—", "avg call",
             True, f"Longest: {longest.lower()} calls ({longest_min} min)" if longest else "—",
             "Shorter verification script for the longest call type", by_reason.get(longest, {}).get("evidence", [])),
        card("repeat", "Repeat contacts", f"{k['repeat']['value']}%" if k["repeat"]["value"] is not None else "—", "within 7 days",
             not (k["repeat"]["vs"] and k["repeat"]["vs"]["direction"] == "up"),
             (f"Most repeats on {worst_rep['reason'].lower()} ({worst_rep['repeat']}% called again within 7 days)" if worst_rep
              else "No contact repeated within 7 days"),
             "Give a dated status update so people don't need to call back", by_reason[worst_rep["reason"]]["evidence"] if worst_rep else []),
        card("escalations", "Escalations", len(transfers) + len(handoffs), "transfers & handoffs",
             all(h.get("confirmed") for _, h in handoffs),
             (f"{sum(1 for _, h in handoffs if not h.get('confirmed'))} handoffs not confirmed"
              if any(not h.get("confirmed") for _, h in handoffs)
              else "All handoffs confirmed" if handoffs else "Transfers mid-call" if transfers else "None heard"),
             "Confirm every handoff with the receiving team on the call",
             [d.ev(c, h.get("quote"), f"Handoff to {h.get('to')}") for c, h in handoffs] + [d.ev(c, None, "Transfer") for c, _ in transfers]),
        card("compliance", "Compliance", f"{pct(len(id_ok), len(id_needed))}%" if id_needed else "—", "identity checks done",
             len(id_ok) == len(id_needed),
             f"{len(id_needed) - len(id_ok)} of {len(id_needed)} calls skipped the ID check",
             "Team refresher: identity check before case details",
             [d.ev(c, None, "Identity not confirmed") for c in id_needed if not c["identity_verified"]]),
        card("consistency", "Consistent answers", len(ft["same_question"]), "cases with mixed answers", not ft["same_question"],
             "Office told fewer documents than the payer requires" if ft["same_question"] else "Offices were told what payers require",
             "One answer per payer rule in the hub payer guide", [e for s in ft["same_question"] for e in s["evidence"]]),
        card("training", "Training needs (team level)", len(train), "topics", not train,
             " · ".join(f"{t.lower()} ({n})" for t, n in train[:2]) or "No repeated hub-side gaps",
             "Targeted 30-minute team sessions on these topics", [i for i in hub_items if i["label"] in dict(train)]),
        card("safety", "Safety & medical questions", f"{saf['counts']['adverse_events']} · {saf['counts']['medical']}", "side effects · questions",
             saf["counts"]["awaiting"] == 0,
             ("None heard in this period" if not saf["counts"]["adverse_events"] and not saf["counts"]["medical"]
              else f"{saf['counts']['awaiting']} awaiting review" if saf["counts"]["awaiting"] else "All reviewed"),
             "Coaching on safety capture; every flag reviewed by a person", [q["evidence"] for q in saf["queue"]]),
    ]
    return {**_base(d), "cards": cards}


def _what_changed(d: Data, reasons, rows, fcr, gap):
    b, lines = d.baseline, []
    top = next((r for r in reasons if r["above"]), None)
    if top:
        kind = engines.ENTITY_BY_REASON.get(top["reason"], "program")
        ents = Counter(engines._entity_name(c, kind) for c in d.calls if c["contact_reason"] == top["reason"])
        ents.pop(None, None)
        mostly = f", mostly {ents.most_common(1)[0][0]}" if ents and kind != "program" else ""
        lines.append({"text": f"{top['reason']} calls up: {top['share']}% of calls (normally {top['normal']:g}%){mostly}.",
                      "to": "/call-summary", "tone": "up", "evidence": top["evidence"]})
    for r in [r for r in rows if r["status"] in ("New", "Rising")][:2]:
        what = "new" if r["status"] == "New" else f"{r['vs']} normal"
        lines.append({"text": f"{r['title']}: {what}, {plural_n(r['patients'], 'patient')}.",
                      "to": f"/access-issues/{urlquote(r['key'], safe='')}", "tone": "up", "evidence": r["evidence"]})
    for i in gap:
        if i["rule_id"] == "R3" and i["band"] in ("high", "watch"):
            lines.append({"text": f"{i['patient']['patient_name']}: cost, distance and hesitation before first dose – "
                                  f"{i['band']} drop-off risk.", "to": f"/journey/{i['patient']['patient_id']}",
                          "tone": "up", "evidence": d.insight_evidence(i)})
    normal = b["fcr"].get("all")
    if fcr is not None and normal is not None and fcr <= normal - 5:
        live = [c for c in d.calls if c["live"] and c["resolved_on_call"] is not None]
        out = [c for c in live if not c["resolved_on_call"]]
        lines.append({"text": f"First-call resolution {fcr}% (normally {normal:g}%): {len(out)} of {len(live)} calls left open.",
                      "to": "/hub", "tone": "down",
                      "evidence": [d.ev(c, c["resolution_note"], "Left outstanding") for c in out]})
    r1 = [i for i in d.open_insights if i["rule_id"] == "R1"]
    if r1:
        lines.append({"text": f"{plural_n(len(r1), 'office')} told fewer documents than the payer needs.",
                      "to": "/access-issues", "tone": "up",
                      "evidence": [e for i in r1 for e in d.insight_evidence(i)]})
    return lines[:5]


OPPORTUNITY = {
    ("Missing documents", "Physician office"):
        "{share}% of the friction heard is missing paperwork from physician offices – mostly {entity}. Sending each office "
        "the exact document checklist up front, plus a Field Access visit, would remove most repeat chases.",
    ("Unclear next step", "Hub process"):
        "{share}% of the friction heard is an unclear next step after hub calls. Closing every requirements call with a "
        "document recap and a confirmed date would prevent most resubmissions.",
    ("Waiting, no update", "Physician office"):
        "{share}% of the friction heard is cases waiting on offices – mostly {entity}. A scheduled status check-in would "
        "replace most chase calls.",
    ("Cost worry", "Patient"):
        "{share}% of the friction heard is cost worry before the first dose. Offering copay assistance on the first call "
        "would address it before it turns into drop-off.",
}


def _opportunity(items):
    if not items:
        return None
    (ftype, party), n = Counter((i["type"], i["with"]) for i in items).most_common(1)[0]
    group = [i for i in items if i["type"] == ftype and i["with"] == party]
    entity = Counter(i["entity"] for i in group).most_common(1)[0][0]
    text = OPPORTUNITY.get((ftype, party), "{share}% of the friction heard is " + ftype.lower() + " with " + party.lower()
                           + " ({entity} most often): " + MEANING[ftype].lower() + ".")
    return {"text": text.format(share=pct(n, len(items)), entity=entity), "evidence": group, "to": "/access"}


def _watchlist(d: Data, gap):
    current, people = d.current_stage(), {}
    for i in sorted(gap, key=lambda i: SEVERITY.get(i["rule_id"], 5)):
        p = i["patient"]
        entry = people.setdefault(p["patient_id"], {**p, "stage": current.get(p["patient_id"]), "items": [], "owner": i["owner"]})
        entry["items"].append({"rule_id": i["rule_id"], "label": RULE_LABEL.get(i["rule_id"], i["rule_id"]), "title": i["title"],
                               "band": i["band"], "status": i["status"]})
    return list(people.values())


# ====================================================================== Screen 2 · Access & friction
def _access_rows(d: Data, items):
    """Option 1's 'signals in conversations' table: one row per pattern, compared with normal, with owner and status."""
    b, w, rows = d.baseline, d.weeks, []

    def add(key, kind, heard, entity, vs, meaning, owner, action, evidence, normal_pw, insight=None):
        latest = max((date.fromisoformat(e["date"]) for e in evidence), default=None)
        st = ({k: insight[k] for k in ("insight_key", "status", "owner", "action_note", "action_date", "useful")} if insight
              else d.status_of(key, latest))
        rows.append({"key": key, "kind": kind, "heard": heard, "entity": entity,
                     "signal": f"{heard} – {entity}" if entity else heard, "vs": vs, "meaning": meaning,
                     "owner": st.get("owner") or owner, "suggested_owner": owner, "action": action,
                     **{k: v for k, v in st.items() if k not in ("owner", "insight_key")}, "evidence": evidence,
                     "patients": len({e["patient_id"] for e in evidence if e.get("patient_id")}),
                     "series": d.weekly([date.fromisoformat(e["date"]) for e in evidence]),
                     "normal_per_week": normal_pw, "threshold": round(2 * normal_pw, 2) if normal_pw else None})

    # Physician offices: rule R2, or any office with repeated friction.
    r2 = {i["subject_id"]: i for i in d.insights if i["rule_id"] == "R2"}
    by_office = defaultdict(list)
    for it in items:
        if it["with"] == "Physician office":
            by_office[(it["entity_id"], it["entity"])].append(it)
    for (pid, name), its in by_office.items():
        ins = r2.get(pid)
        normal = b["entity_weekly"].get("practice")
        vs = _rate_text(vs_rate(len(its), w, normal))
        if not ins and (len(its) < 3 or vs["direction"] != "up"):
            continue  # without a fired rule, only patterns above normal are worth a row
        add(ins["insight_key"] if ins else f"PATTERN|practice|{pid}", "practice", _heard(i["label"] for i in its), name,
            vs, MEANING[Counter(i["type"] for i in its).most_common(1)[0][0]],
            "Field Access team", ins["action"] if ins else "Field Access team reviews the office's paperwork with them",
            its, normal, ins)

    # Payers: requirement / denial language heard on calls with that payer.
    by_payer = defaultdict(list)
    for c in d.calls:
        if c["payer_display"]:
            for s in d.sig[c["call_id"]]:
                if s["signal_id"] in PAYER_REQUIREMENT:
                    by_payer[(c["payer_id"], c["payer_display"])].append(d.ev(c, s["quote"], s["signal_name"]))
    for (pid, name), evs in by_payer.items():
        normal = b["entity_weekly"].get("payer")
        vs = _rate_text(vs_rate(len(evs), w, normal))
        if len(evs) >= 2 and vs["direction"] == "up":
            add(f"PATTERN|payer|{pid}", "payer", _heard(e["label"] for e in evs), name, vs,
                "Payer criteria stricter than offices expect – what the payer asks for is not what offices send", "Market Access",
                "Market Access confirms the payer's current criteria; the hub payer guide is updated", evs, normal)

    r1 = [i for i in d.open_insights if i["rule_id"] == "R1"]
    if r1:
        normal = b["rule_weekly"].get("R1")
        add("R1|all|all", "hub", "Office told fewer documents than the payer requires", None,
            _rate_text(vs_rate(len(r1), w, normal)), "Hub templates or call guide out of date against payer rules",
            r1[0]["owner_team"], r1[0]["action"], [e for i in r1 for e in d.insight_evidence(i)], normal)

    r4 = [i for i in d.open_insights if i["rule_id"] == "R4"]
    if r4:
        pa_calls = [c for c in d.calls if c["other_party_type"] == "provider_office"
                    and (c["journey_stage"] or "").startswith("Prior authorization")]
        share, normal = pct(len(r4), len(pa_calls)), b["close_generic_share"].get("all")
        vs = {"text": f"{share}% vs {normal:g}%", "direction": "up" if share and normal and share > normal else "flat",
              "score": round(share / normal, 1) if share and normal else 0,
              "detail": f"{len(r4)} of {len(pa_calls)} PA requirement calls ended without a document list or date"}
        add("R4|all|all", "hub", "PA calls closed without a document list or date", None, vs,
            "Next step unclear for the office – leads to pended PAs and resubmissions", r4[0]["owner_team"], r4[0]["action"],
            [e for i in r4 for e in d.insight_evidence(i)], None)

    for i in d.open_insights:
        if i["rule_id"] == "R3":
            evs = [d.ev(c, s["quote"], s["signal_name"]) for c in d.calls if c["patient_id"] == i["subject_id"]
                   for s in d.sig[c["call_id"]] if s["signal_id"] in DROP_OFF]
            normal = b["entity_weekly"].get("patient")
            add(i["insight_key"], "patient", "Cost, distance and hesitation before first dose", i["patient"]["patient_name"],
                _rate_text(vs_rate(len(evs), w, normal)), "Affordability or logistics barrier – risk the patient never starts",
                i["owner_team"], i["action"], evs or d.insight_evidence(i), normal, i)

    missed = [p for p in d.promises if p["status"] == "missed" and p["call_id"] in d.ids]
    if missed:
        kept = sum(1 for p in d.promises if p["status"] == "kept" and p["call_id"] in d.ids)
        kept_pct, normal = pct(kept, kept + len(missed)), b["promises_kept"].get("all")
        vs = {"text": f"{len(missed)} missed", "direction": "up", "score": 1.5,
              "detail": f"{kept_pct}% of verifiable promises kept vs normal {normal:g}%"}
        add("R6|all|all", "hub", "Promised follow-ups not made", None, vs,
            "Patients and offices wait for a callback that never comes", "Hub operations",
            "Complete the promised follow-up and tell the patient or office",
            [d.ev(d.by_id[p["call_id"]], p["quote"], "Promised follow-up missed") for p in missed], None)
    order = {s: n for n, s in enumerate(STATUSES)}
    rows.sort(key=lambda r: (order.get(r["status"], 9), -r["vs"]["score"]))
    return rows


@router.get("/dashboard/access")
@cached
@capped
def access(f: Filters = Depends(filters)):
    d = get_data(f)
    items = d.friction()
    rows = _access_rows(d, items)

    heat = []
    for st in STAGE_ORDER:
        cells = [{"type": t, "evidence": [i for i in items if i["stage"] == st and i["type"] == t]} for t in FRICTION_TYPES]
        for c in cells:
            c["count"] = len(c["evidence"])
        heat.append({"stage": st, "cells": cells, "total": sum(c["count"] for c in cells)})

    parties = []
    for p in PARTIES:
        its = [i for i in items if i["with"] == p]
        if its:
            ex = next((i for i in reversed(its) if i["quote"]), its[-1])
            parties.append({"party": p, "count": len(its), "share": pct(len(its), len(items)),
                            "entities": Counter(i["entity"] for i in its).most_common(3),
                            "types": Counter(i["type"] for i in its).most_common(3),
                            "example": {"quote": ex["quote"], "entity": ex["entity"], "external_call_id": ex["external_call_id"],
                                        "call_id": ex["call_id"]}, "evidence": its})
    parties.sort(key=lambda x: -x["count"])

    by_payer = defaultdict(lambda: {"calls": 0, "signals": Counter()})
    for c in d.calls:
        if c["payer_display"]:
            p = by_payer[(c["payer_id"], c["payer_display"])]
            p["calls"] += 1
            for s in d.sig[c["call_id"]]:
                if s["insight_type"] == "Payer requirements":
                    p["signals"][s["signal_name"]] += 1
    return {
        **_base(d),
        "rows": rows,
        "heat": heat,
        "types": FRICTION_TYPES,
        "heat_max": max([c["count"] for r in heat for c in r["cells"]] + [1]),
        "parties": parties,
        "pa_slow": _pa_slow(d, items),
        "emerging": _emerging(rows),
        "tracked": _tracked(d, rows),
        "payers": [{"payer_id": k[0], "payer_name": k[1], "calls": v["calls"], "signals": v["signals"].most_common(5)}
                   for k, v in by_payer.items()],
        "friction_total": len(items),
    }


def _tracked(d: Data, rows):
    """'Actions taken - did the fix work?': mention rate before vs after the action date."""
    out = []
    for r in rows:
        if r["status"] not in ("in_progress", "watching", "fixed"):
            continue
        ad = date.fromisoformat(r["action_date"]) if r["action_date"] else AS_OF
        days = [date.fromisoformat(e["date"]) for e in r["evidence"]]
        bw, aw = max(1.0, (ad - d.start).days / 7), (AS_OF - ad).days / 7
        before = round(sum(1 for x in days if x < ad) / bw, 1)
        after = round(sum(1 for x in days if x >= ad) / aw, 1) if aw >= 1 else None
        normal = r["normal_per_week"]
        verdict = ("Fixed – back to normal" if r["status"] == "fixed" else "Watching – too early to tell" if after is None
                   else "Back to normal" if normal is not None and after <= normal else "Improving" if after < before
                   else "No change yet")
        out.append({"key": r["key"], "signal": r["signal"], "status": r["status"], "action": r["action_note"] or r["action"],
                    "action_date": r["action_date"], "before": before, "after": after, "verdict": verdict, "owner": r["owner"]})
    return out


def _pa_slow(d: Data, items):
    """Option 2's 'why prior authorization is slow': share of delayed PA cases showing each reason."""
    pa_cases = {c["case_id"] for c in d.calls if (c["journey_stage"] or "").startswith("Prior authorization") and c["case_id"]}
    case_of = {c["external_call_id"]: c["case_id"] for c in d.all_calls}
    by_case = defaultdict(list)
    for i in items:
        if case_of.get(i["external_call_id"]) in pa_cases:
            by_case[case_of[i["external_call_id"]]].append(i)
    r1 = {i["subject_id"]: i for i in d.open_insights if i["rule_id"] == "R1"}
    payer_sig = defaultdict(list)
    for c in d.calls:
        if c["case_id"] in pa_cases:
            for s in d.sig[c["call_id"]]:
                if s["signal_id"] in ("S15", "S18"):
                    payer_sig[c["case_id"]].append(d.ev(c, s["quote"], s["signal_name"]))
    delayed = set(by_case) | set(payer_sig) | (set(r1) & pa_cases)
    tests = {
        "Office documents late": lambda case: [i for i in by_case[case] if i["with"] == "Physician office"],
        "Payer rule unclear or changed": lambda case: payer_sig[case] + (d.insight_evidence(r1[case]) if case in r1 else []),
        "Next step unclear after hub call": lambda case: [i for i in by_case[case] if i["type"] == "Unclear next step"],
        "Hub follow-up missed": lambda case: [i for i in by_case[case] if i["label"] == "Promised follow-up missed"],
        "Patient unreachable": lambda case: [i for i in by_case[case] if i["with"] == "Patient" and i["type"] == "Waiting, no update"],
    }
    out = []
    for reason, test in tests.items():
        hits = {case: test(case) for case in delayed}
        cases = [c for c, v in hits.items() if v]
        out.append({"reason": reason, "cases": len(cases), "share": pct(len(cases), len(delayed)) or 0,
                    "evidence": [e for c in cases for e in hits[c]]})
    return {"delayed_cases": len(delayed), "pa_cases": len(pa_cases),
            "reasons": sorted((r for r in out if r["cases"]), key=lambda x: -x["share"])}


def _emerging(rows):
    cands = [r for r in rows if r["status"] in ("new", "open") and r["kind"] in ("practice", "payer", "hub")]
    if not cands:
        return None
    r = max(cands, key=lambda r: r["vs"]["score"])
    who = f" across {r['patients']} patient{'s' if r['patients'] != 1 else ''}" if r["patients"] else ""
    return {"title": r["signal"], "text": f"{r['vs']['detail']}{who}. {r['meaning']}.", "owner": r["suggested_owner"],
            "key": r["key"], "vs": r["vs"], "evidence": r["evidence"]}


# ====================================================================== Screen 3 · Patient journey
@router.get("/patients")
@cached
def patients():
    d = get_data(Filters())
    risk = {}  # latest risk row per patient, by call date
    for r in sorted((r for r in d.risk if r["call_id"] in d.by_id), key=lambda r: d.by_id[r["call_id"]]["call_datetime"]):
        risk[r["patient_id"]] = r
    current, out = d.current_stage(), []
    open_by = Counter(i["patient"]["patient_id"] for i in d.open_insights if i["patient"] and i["rule_id"] != "IDCHECK")
    level = {p["patient_id"]: p["level"] for p in engines.at_risk(d)}
    for p in d.patients.values():
        n = len(d.patient_calls.get(p["patient_id"], []))
        if not n:
            continue
        open_items = [None] * open_by.get(p["patient_id"], 0)
        r = risk.get(p["patient_id"])
        out.append({"patient_id": p["patient_id"], "patient_name": p["patient_name"], "case_id": p["case_id"], "drug": p["drug"],
                    "recorded": not p.get("mock"),
                    "practice_name": p["practice_name"], "payer_name": display_payer(p["payer_name"]), "calls": n,
                    "stage": current.get(p["patient_id"]), "open_items": len(open_items),
                    "risk_score": float(r["running"]) if r else 0, "risk_band": r["band"] if r else "low",
                    "risk_level": level.get(p["patient_id"])})
    order = {"High": 0, "Medium": 1, "Low": 2, None: 3}
    return sorted(out, key=lambda p: (-p["risk_score"], order[p["risk_level"]], -p["open_items"], p["patient_name"]))


@router.get("/patients/{patient_id}/journey")
@cached
def journey(patient_id: str):
    d = get_data(Filters())
    patient = d.patients.get(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    calls = [c for c in d.all_calls if c["patient_id"] == patient_id]
    if not calls:
        raise HTTPException(status_code=404, detail="No analysed calls for this patient")
    ids = {c["call_id"] for c in calls}
    risk = {r["call_id"]: r for r in d.risk if r["patient_id"] == patient_id}
    docs = defaultdict(lambda: defaultdict(list))
    for r in d.documents:
        if r["call_id"] in ids:
            docs[r["call_id"]][r["list_type"]].append(r["item"])
    promises = defaultdict(list)
    for p in d.promises:
        if p["call_id"] in ids:
            promises[p["call_id"]].append({k: p[k] for k in ("action", "due_text", "due_date", "made_by_role", "status", "quote")})
    safety = defaultdict(list)
    for s in _safety_rows(d, ids):
        safety[s["call_id"]].append(s)
    friction = defaultdict(list)
    for i in d.friction(calls):
        friction[i["call_id"]].append({k: i[k] for k in ("type", "with", "label", "quote")})
    ins = [i for i in d.insights if i["patient"] and i["patient"]["patient_id"] == patient_id]
    by_call = defaultdict(list)
    for i in ins:
        for e in i["evidence"]:
            by_call[e["external_call_id"]].append(i["insight_key"])

    day0 = calls[0]["call_datetime"].date()
    timeline, bands = [], []
    for c in calls:
        r = risk.get(c["call_id"])
        timeline.append({
            "call_id": str(c["call_id"]), "external_call_id": c["external_call_id"], "day": (c["call_datetime"].date() - day0).days,
            "date": c["call_datetime"].isoformat(), "direction": c["direction"], "party": PARTY_OF_CALL.get(c["other_party_type"], "Other"),
            "other_party_type": c["other_party_type"], "stage": c["journey_stage"], "contact_reason": c["contact_reason"],
            "resolved": c["resolved_on_call"], "resolution_note": c["resolution_note"], "summary": c["summary"],
            "sentiment": c["sentiment"], "identity_verified": c["identity_verified"], "duration_s": float(c["audio_duration_s"] or 0),
            "staff_name": c["staff_name"], "staff_role": c["staff_role"], "practice_name": c["practice_name"],
            "payer_name": c["payer_display"],
            "signals": [{k: s[k] for k in ("signal_id", "signal_name", "insight_type", "quote", "timestamp_s")} for s in d.sig[c["call_id"]]],
            "friction": friction[str(c["call_id"])], "promises": promises[c["call_id"]],
            "payer_required": docs[c["call_id"]]["payer_required"], "requested": docs[c["call_id"]]["requested_from_office"],
            "missing": docs[c["call_id"]]["missing_item"], "handoffs": c["raw"].get("handoffs", []),
            "safety": safety[str(c["call_id"])], "insight_keys": by_call[c["external_call_id"]],
            "risk": {"call_score": float(r["call_score"]), "running": float(r["running"]), "band": r["band"]} if r else None})
        if bands and bands[-1]["stage"] == c["journey_stage"]:
            bands[-1]["to"] = len(timeline) - 1
        else:
            bands.append({"stage": c["journey_stage"], "from": len(timeline) - 1, "to": len(timeline) - 1})

    dob = patient["dob"]
    age = (AS_OF.year - dob.year - ((AS_OF.month, AS_OF.day) < (dob.month, dob.day))) if dob else None
    v2 = _journey_v2(d, patient_id, calls, timeline, ins, day0)
    return {
        "patient": {**{k: patient[k] for k in ("patient_id", "patient_name", "case_id", "drug", "program_name", "practice_name",
                                               "prescriber_name")},
                    "payer_name": display_payer(patient["payer_name"]), "age": age, "stage": calls[-1]["journey_stage"],
                    "first_contact": day0.isoformat(), "today_day": (AS_OF - day0).days},
        **v2,
        "timeline": timeline, "bands": bands,
        "insights": sorted(ins, key=lambda i: SEVERITY.get(i["rule_id"], 5)),
        "story": [{"day": t["day"], "external_call_id": t["external_call_id"], "call_id": t["call_id"],
                   "text": (t["summary"] or "").split(". ")[0].rstrip(".") + "."} for t in timeline if t["summary"]],
        "sources": {"calls": len(calls)},
    }


# ====================================================================== Screen 4 · Follow-through & quality
@router.get("/dashboard/follow-through")
@cached
@capped
def follow_through(f: Filters = Depends(filters)):
    d = get_data(f)
    b, calls, items = d.baseline, d.calls, d.friction()
    fcr, _ = d.fcr(calls)
    rep, _ = d.repeat_pct(calls)
    proms = [p for p in d.promises if p["call_id"] in d.ids]
    kept, missed = sum(1 for p in proms if p["status"] == "kept"), sum(1 for p in proms if p["status"] == "missed")
    handoffs = [(c, h) for c in calls for h in c["raw"].get("handoffs", [])]
    confirmed = pct(sum(1 for _, h in handoffs if h.get("confirmed")), len(handoffs))
    safety = _safety_rows(d)

    idcheck = [i for i in d.open_insights if i["rule_id"] == "IDCHECK"]
    ae_unack = [s for s in safety if s["kind"] == "adverse_event" and s["handled_ok"] is False]
    med_answered = [s for s in safety if s["kind"] == "medical_question" and s["handled_ok"] is False]
    checks = [
        {"label": "Identity not confirmed before case details", "count": len(idcheck),
         "evidence": [e for i in idcheck for e in d.insight_evidence(i)]},
        {"label": "Possible adverse event not acknowledged", "count": len(ae_unack), "evidence": [s["evidence"] for s in ae_unack]},
        {"label": "Medical question answered instead of referred", "count": len(med_answered),
         "evidence": [s["evidence"] for s in med_answered]},
    ]

    segs = defaultdict(list)
    for s in d.segments:
        if s["call_id"] in d.ids:
            segs[s["call_id"]].append(s)
    splits = {c["call_id"]: d.time_split(c, segs[c["call_id"]]) for c in calls if c["live"]}

    def split_for(cs):
        tot = defaultdict(float)
        n = 0
        for c in cs:
            if splits.get(c["call_id"]):
                n += 1
                for k, v in splits[c["call_id"]].items():
                    tot[k] += v
        total = tot.get("total") or 0
        return {**{k: round(100 * tot[k] / total) if total else 0 for k in ("talking", "hold", "silence", "transfer")},
                "minutes": round(total / 60, 1), "calls": n}

    by_reason = []
    for r in CONTACT_REASONS:
        cs = [c for c in calls if c["contact_reason"] == r]
        if not cs:
            continue
        open_calls = [c for c in cs if c["live"] and c["resolved_on_call"] is False]
        open_ids = {str(c["call_id"]) for c in open_calls}
        cause = Counter(i["label"] for i in items if i["call_id"] in open_ids).most_common(1)
        by_reason.append({"reason": r, "calls": len(cs), "fcr": d.fcr(cs)[0], "fcr_normal": b["fcr"].get(r),
                          "repeat": d.repeat_pct(cs)[0], "repeat_normal": b["repeat_7d"].get(r),
                          "root_cause": cause[0][0] if cause else (open_calls[0]["resolution_note"] if open_calls else None),
                          "time": split_for(cs),
                          "evidence": [d.ev(c, c["resolution_note"], "Left outstanding" if c["resolved_on_call"] is False
                                            else "Resolved on the call") for c in cs]})
    by_reason.sort(key=lambda r: (-(r["repeat"] or 0), (r["fcr"] or 0)))

    r4_calls = {i["subject_id"] for i in d.open_insights if i["rule_id"] == "R4"}
    id_calls = {i["subject_id"] for i in idcheck}
    safety_calls = Counter(s["call_id"] for s in safety)
    qa = []
    for c in calls:
        sig = {s["signal_id"] for s in d.sig[c["call_id"]]}
        why = [label for cond, label in ((c["external_call_id"] in id_calls, "identity not confirmed"),
                                         (safety_calls[str(c["call_id"])] > 0, "safety mention"),
                                         (c["external_call_id"] in r4_calls, "vague close"),
                                         (bool(sig & DROP_OFF), "drop-off language"),
                                         (c["live"] and c["resolved_on_call"] is False, "left outstanding"),
                                         (c["sentiment"] in ("negative", "mixed"), f"{c['sentiment']} sentiment")) if cond]
        score = sum({"identity not confirmed": 3, "safety mention": 3, "vague close": 2, "drop-off language": 2}.get(w, 1) for w in why)
        if score:
            qa.append({**d.ev(c), "score": score, "why": why})
    qa.sort(key=lambda x: -x["score"])

    flagged = []
    for p in proms:
        if p["status"] == "missed":
            flagged.append({**d.ev(d.by_id[p["call_id"]], p["quote"]), "kind": "Promise not kept", "text": p["action"]})
    for i in d.open_insights:
        if i["rule_id"] == "R3":
            last = [c for c in d.all_calls if c["patient_id"] == i["subject_id"]][-1]
            if not any(p["call_id"] == last["call_id"] and p["made_by_role"] == "hub_staff" for p in d.promises):
                flagged.append({**d.ev(last), "kind": "Drop-off risk",
                                "text": "Drop-off language heard – no follow-up booked after the last contact"})
    for c in calls:
        later = d.later_calls(c)
        dated = any(p["call_id"] == c["call_id"] and (p["due_text"] or p["due_date"]) for p in d.promises)
        if c["live"] and c["resolved_on_call"] is False and not later and not dated:
            flagged.append({**d.ev(c, c["resolution_note"]), "kind": "Left open", "text": c["resolution_note"] or "Nothing booked"})
    for c, h in handoffs:
        if not h.get("confirmed"):
            flagged.append({**d.ev(c, h.get("quote")), "kind": "Handoff not confirmed", "text": f"Handoff to {h.get('to')}"})

    ms = defaultdict(dict)
    for m in d.milestones:
        ms[m["case_id"]][m["milestone"]] = m["occurred_on"]
    closes = []
    for c in calls:
        s = {x["signal_id"] for x in d.sig[c["call_id"]]}
        if c["other_party_type"] != "provider_office" or not s & {"S19", "S20", "S21", "S22", "S17"} \
                or not (c["journey_stage"] or "").startswith("Prior authorization"):
            continue
        decision = ms.get(c["case_id"], {}).get("pa_decision")
        later = d.later_calls(c)
        closes.append({**d.ev(c), "close": "Recap + date" if {"S19", "S20"} <= s else ("Generic" if s & {"S22", "S17"} else "Partial"),
                       "rework": any({y["signal_id"] for y in d.sig[x["call_id"]]} & {"S15", "S18"} for x in later),
                       "days_to_decision": (decision - c["call_datetime"].date()).days if decision else None})
    groups = defaultdict(list)
    for c in closes:
        if c["days_to_decision"] is not None:
            groups[c["close"]].append(c["days_to_decision"])

    promise_rows = []
    for p in sorted(proms, key=lambda p: (p["status"] != "missed", str(p["due_date"] or ""))):
        kept_by = d.by_id.get(p["kept_by_call_id"]) if p["kept_by_call_id"] else None
        promise_rows.append({**d.ev(d.by_id[p["call_id"]], p["quote"]), "action": p["action"], "due_text": p["due_text"],
                             "due_date": p["due_date"], "made_by_role": p["made_by_role"], "status": p["status"],
                             "kept_by": kept_by["external_call_id"] if kept_by else None})
    return {
        **_base(d),
        "kpis": {
            "fcr": {"value": fcr, "vs": vs_pct(fcr, b["fcr"].get("all"))},
            "repeat": {"value": rep, "vs": vs_pct(rep, b["repeat_7d"].get("all"))},
            "promises": {"value": pct(kept, kept + missed), "kept": kept, "missed": missed,
                         "vs": vs_pct(pct(kept, kept + missed), b["promises_kept"].get("all"))},
            "handoffs": {"value": confirmed, "of": len(handoffs), "vs": vs_pct(confirmed, b["handoffs_confirmed"].get("all"))},
            "checks_missed": {"value": sum(c["count"] for c in checks)},
        },
        "by_reason": by_reason,
        "time_all": split_for([c for c in calls if c["live"]]),
        "checks": checks,
        "same_question": [{"subject_id": i["subject_id"], "patient": i["patient"], "detail": i["detail"], "band": i["band"],
                           "evidence": d.insight_evidence(i)} for i in d.open_insights if i["rule_id"] == "R1"],
        "qa_sample": qa[:5],
        "flagged": engines.cap_evidence({"evidence": flagged}, 40)["evidence"],
        "closes": engines.cap_evidence({"evidence": closes}, 40)["evidence"],
        "close_comparison": {k: {"calls": len(v), "avg_days_to_decision": round(sum(v) / len(v), 1)} for k, v in groups.items()},
        "promises": promise_rows,
        "milestones_note": "PA milestone dates are synthetic until CRM / payer data is connected (Phase 2).",
    }


# ====================================================================== Screen 5 · Safety & Medical Information
def _safety_rows(d: Data, ids=None):
    ids = d.ids if ids is None else ids
    out = []
    for s in d.safety_raw:
        if s["call_id"] not in ids:
            continue
        c = d.by_id[s["call_id"]]
        hours = None
        if s["reviewed_at"] and c["processed_at"]:
            hours = round(max(0.0, (s["reviewed_at"] - c["processed_at"]).total_seconds() / 3600), 1)
        out.append({"safety_key": s["safety_key"], "call_id": str(s["call_id"]), "kind": s["kind"], "kind_label": KIND_LABEL[s["kind"]],
                    "topic": s["topic"], "mention": s["mention"], "quote": s["quote"], "timestamp_s": s["timestamp_s"],
                    "asked_by": s["asked_by"], "handled_ok": s["handled_ok"], "status": s["review_status"] or "awaiting",
                    "suggested_route": SUGGESTED_ROUTE[s["kind"]], "reviewed_at": s["reviewed_at"], "hours_to_review": hours,
                    "product": c["drug"], "patient_name": c["patient_name"], "patient_id": c["patient_id"],
                    "source": "Call", "evidence": d.ev(c, s["quote"], KIND_LABEL[s["kind"]])})
    return out


@router.get("/dashboard/safety")
@cached
@capped
def safety(f: Filters = Depends(filters)):
    d = get_data(f)
    rows = _safety_rows(d)
    med = [r for r in rows if r["kind"] == "medical_question"]
    topics = Counter(r["topic"] or "Other" for r in med)
    reviewed = [r for r in rows if r["status"] != "awaiting"]
    top = topics.most_common(1)[0][0] if topics else None
    return {
        **_base(d),
        "queue": sorted(rows, key=lambda r: (r["status"] != "awaiting", r["kind"] != "adverse_event", r["evidence"]["date"])),
        "counts": {"adverse_events": sum(1 for r in rows if r["kind"] in ("adverse_event", "dosing_mistake")),
                   "quality": sum(1 for r in rows if r["kind"] == "quality_complaint"), "medical": len(med),
                   "awaiting": sum(1 for r in rows if r["status"] == "awaiting"), "reviewed": len(reviewed),
                   "avg_hours": round(sum(r["hours_to_review"] or 0 for r in reviewed) / len(reviewed), 1) if reviewed else None,
                   "target_hours": d.baseline["safety_review_hours"].get("all")},
        "topics": [{"topic": t, "count": topics.get(t, 0), "evidence": [r["evidence"] for r in med if (r["topic"] or "Other") == t]}
                   for t in MEDICAL_TOPICS if topics.get(t) or t in MEDICAL_TOPICS[:5]],
        "top_question": next((r for r in reversed(med) if (r["topic"] or "Other") == top), None),
        "rule": "The platform never reports on its own. Every flag goes to a person and into Ipsen's existing "
                "Pharmacovigilance / Medical Information intake.",
    }


# ====================================================================== Alerts + weekly brief (on every screen)
@router.get("/alerts")
@cached
def alerts(f: Filters = Depends(filters)):
    d = get_data(f)
    out = []
    for r in [r for r in engines.access_issues(d) if r["status"] in ("New", "Rising")][:5]:
        trigger = (f"New · {plural_n(r['patients'], 'patient')}" if r["status"] == "New"
                   else f"{r['vs']} normal · {plural_n(r['patients'], 'patient')}")
        out.append({"type": "Emerging access issue", "tone": "orange", "title": r["title"], "trigger": trigger,
                    "evidence": f"{len(r['evidence'])} excerpts from {plural_n(r['patients'], 'patient')}",
                    "owner": r["owner"], "to": f"/access-issues/{urlquote(r['key'], safe='')}", "status": "new"})
    for x in [x for x in engines.at_risk(d) if x["level"] == "High" and x["new_this_week"] and not x["recorded"]][:3]:
        out.append({"type": "Drop-off risk", "tone": "navy", "title": x["patient_name"],
                    "trigger": " · ".join(x["categories"][:3]), "owner": x["next_step"],
                    "evidence": f"“{x['quote']}”" if x["quote"] else f"{x['mentions']} mentions", "to": f"/journey/{x['patient_id']}",
                    "status": "new"})
    for i in d.open_insights:
        if i["rule_id"] == "R3":
            quotes = [f"“{e['quote']}”" for e in i["evidence"][-2:] if e.get("quote")]
            out.append({"type": "Drop-off risk", "tone": "navy", "title": f"{i['patient']['patient_name']}",
                        "trigger": "Cost, distance and hesitation heard across calls", "owner": i["owner"],
                        "evidence": "; ".join(quotes) or f"{len(i['evidence'])} calls", "to": f"/journey/{i['subject_id']}",
                        "status": i["status"]})
        elif i["rule_id"] == "R6" and i["patient"]:
            out.append({"type": "Promise not kept", "tone": "navy", "title": i["patient"]["patient_name"], "trigger": i["detail"],
                        "owner": i["owner"], "evidence": f"{len(i['evidence'])} calls",
                        "to": f"/journey/{i['patient']['patient_id']}", "status": i["status"]})
    seen = set()
    out = [a for a in out if not ((a["type"], a["title"]) in seen or seen.add((a["type"], a["title"])))]
    for s in _safety_rows(d):
        if s["status"] == "awaiting":
            out.append({"type": s["kind_label"], "tone": "purple", "title": f"Call · {s['patient_name']} · {s['product']}",
                        "trigger": s["mention"], "owner": "Reviewer → " + s["suggested_route"].replace("_", " ").title(),
                        "evidence": f"“{s['quote']}”", "to": "/safety", "status": "awaiting"})
    return {"count": len(out), "alerts": out}


@router.get("/brief")
@cached
def brief(f: Filters = Depends(filters)):
    d = get_data(f)
    ov, acc, saf = overview(f=f), access(f=f), safety(f=f)
    k = ov["kpis"]
    emerging = [r for r in engines.access_issues(d) if r["status"] in ("New", "Rising")][:2]
    rk = engines.risk_page(d)["kpis"]
    top_reason = next((r for r in ov["reasons"] if r["above"]), ov["reasons"][0] if ov["reasons"] else None)
    fcr_vs = k["fcr"]["vs"]
    sections = [
        {"title": "Emerging access issues", "tone": "orange", "to": "/access-issues",
         "text": " ".join(f"{r['title']}: {'new' if r['status'] == 'New' else r['vs'] + ' normal'} – owner {r['owner']}."
                          for r in emerging)
         or "Nothing above normal this period."},
        {"title": "Patients needing attention", "tone": "navy", "to": "/at-risk",
         "text": f"{rk['flagged']} at risk ({rk['high']} high), {rk['new_this_week']} new this week."},
        {"title": "Why people contact the hub", "tone": "navy", "to": "/call-summary",
         "text": (f"{top_reason['reason']} is {top_reason['share']}% of conversations (normal {top_reason['normal']:g}%). "
                  if top_reason else "") +
                 (f"First-contact resolution {k['fcr']['value']}% (normal {fcr_vs['normal']:g}%)." if fcr_vs else "")},
        {"title": "Safety", "tone": "navy", "to": "/safety",
         "text": f"{saf['counts']['adverse_events']} possible adverse events, {saf['counts']['quality']} quality complaints and "
                 f"{saf['counts']['medical']} Medical Information questions; {saf['counts']['awaiting']} awaiting review."},
        {"title": "What patients ask", "tone": "navy", "to": "/safety",
         "text": f"“{saf['top_question']['mention']}” ({saf['top_question']['topic']}) – suggested content for Medical Information."
         if saf["top_question"] else "No medical questions in this period's conversations."},
        {"title": "Did last week's fixes work?", "tone": "green", "to": "/access",
         "text": " ".join(f"{t['signal']}: {t['verdict'].lower()}." for t in acc["tracked"])
         or "No actions tracked yet."},
    ]
    return {**_base(d), "week_of": (AS_OF - timedelta(days=AS_OF.weekday())).isoformat(), "sections": sections}


# ====================================================================== writes from the screens
class ActionUpdate(BaseModel):
    insight_key: str
    status: str | None = None
    owner: str | None = None
    action_note: str | None = None
    action_date: date | None = None
    useful: bool | None = None


@router.post("/insights/action")
def update_action(body: ActionUpdate):
    fields = body.model_dump(exclude_unset=True, exclude={"insight_key"})
    if body.status and body.status not in STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status")
    if body.status in ("in_progress", "watching", "fixed") and "action_date" not in fields:
        existing = fetch_one("SELECT action_date FROM ci_insight_actions WHERE insight_key = %s", (body.insight_key,))
        if not existing or not existing["action_date"]:
            fields["action_date"] = AS_OF  # the demo's "today"
    cols = ["insight_key", *fields]
    updates = ", ".join([*(f"{k} = EXCLUDED.{k}" for k in fields), "updated_at = NOW()"])
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""INSERT INTO ci_insight_actions ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})
                        ON CONFLICT (insight_key) DO UPDATE SET {updates}""", [body.insight_key, *fields.values()])
    clear_cache()
    return fetch_one("SELECT * FROM ci_insight_actions WHERE insight_key = %s", (body.insight_key,))


class SafetyReview(BaseModel):
    safety_key: str
    status: str


@router.post("/safety/review")
def review_safety(body: SafetyReview):
    if body.status not in ("awaiting", "pharmacovigilance", "medical_information", "quality_complaint", "not_safety"):
        raise HTTPException(status_code=400, detail="Unknown status")
    with get_conn() as conn, conn.cursor() as cur:
        if body.status == "awaiting":
            cur.execute("DELETE FROM ci_safety_review WHERE safety_key = %s", (body.safety_key,))
        else:
            cur.execute("""INSERT INTO ci_safety_review (safety_key, status, reviewed_at) VALUES (%s, %s, %s)
                           ON CONFLICT (safety_key) DO UPDATE SET status = EXCLUDED.status, reviewed_at = EXCLUDED.reviewed_at""",
                        (body.safety_key, body.status, datetime.now(timezone.utc)))
    clear_cache()
    return {"safety_key": body.safety_key, "status": body.status}


@router.get("/calls/{call_id}/audio")
def call_audio(call_id: UUID):
    path = next(AUDIO_DIR.glob(f"{call_id}.*"), None)
    if not path:
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path, media_type="audio/mpeg" if path.suffix == ".mp3" else None)


# ====================================================================== v2 Screen 4 · Patient journey
STOP_SIGNALS = {"S31", "S27", "S26", "S29"}
JOURNEY_TITLE = {"Enrollment": "Enroll", "Benefits verification": "Benefits", "Prior authorization & appeal": "Prior auth",
                 "Copay & assistance": "Copay", "Specialty pharmacy & first fill": "SP", "Nurse education": "Nurse start",
                 "Adherence & refill": "On therapy"}


def _journey_v2(d: Data, patient_id, calls, timeline, ins, day0):
    """Deck screen 4: day-scaled stage band, the key moments (what was said and what it means), what to do next,
    and what the conversations show. Deterministic, from the stored signals, promises and safety findings."""
    by_ext = {t["external_call_id"]: t for t in timeline}
    spans = d.stage_spans({patient_id})[patient_id]
    friction_by_call = Counter(i["call_id"] for i in d.friction(calls))
    # Whole journey, as in the deck: stages heard on calls (sized by days, coloured by what was heard), earlier stages
    # with no calls (completed before or between calls) and the stages still to come.
    heard = []
    for n, sp in enumerate(spans):
        fr = sum(friction_by_call[str(c["call_id"])] for c in sp["calls"])
        sig = {s["signal_id"] for c in sp["calls"] for s in d.sig[c["call_id"]]}
        tone = ("teal" if sp["stage"] == "Adherence & refill" else "red" if "S15" in sig or fr >= 4
                else "amber" if fr else "green")
        heard.append({"stage": sp["stage"], "title": JOURNEY_TITLE.get(sp["stage"], sp["stage"]), "from": (sp["start"] - day0).days,
                      "to": ((sp["end"] or AS_OF) - day0).days, "tone": tone, "kind": "heard", "current": n == len(spans) - 1,
                      "friction": fr})
    idx = {st: i for i, st in enumerate(STAGE_ORDER)}
    seen = {h["stage"] for h in heard}
    reached = max((idx.get(h["stage"], 0) for h in heard), default=-1)
    band = []
    pending = [st for st in STAGE_ORDER if st not in seen]
    for h in heard:
        # stages that come before this one in the hub's journey and were never heard on a call: completed without a call
        for st in [st for st in pending if idx[st] < idx.get(h["stage"], 0)]:
            band.append({"stage": st, "title": JOURNEY_TITLE.get(st, st), "from": h["from"], "to": h["from"], "tone": "done",
                         "kind": "passed", "current": False, "friction": 0})
            pending.remove(st)
        band.append(h)
    for st in pending:
        passed = idx[st] < reached
        band.append({"stage": st, "title": JOURNEY_TITLE.get(st, st), "from": (AS_OF - day0).days, "to": (AS_OF - day0).days,
                     "tone": "done" if passed else "next", "kind": "passed" if passed else "next", "current": False, "friction": 0})

    missed = {p["call_id"] for p in d.promises if p["status"] == "missed"}
    r1_calls = {e["external_call_id"] for i in ins if i["rule_id"] == "R1" for e in i["evidence"]}
    pr = engines.patient_risk(d, patient_id)
    moments = []
    for c in calls:
        t = by_ext[c["external_call_id"]]
        sig = {s["signal_id"]: s for s in d.sig[c["call_id"]]}
        safety = t["safety"]
        score, tag, quote, tone = 0, None, None, "navy"
        if safety:
            score, tag, quote, tone = 6, f"{safety[0]['kind_label']} → {'safety team' if safety[0]['kind'] != 'medical_question' else 'Medical Information'}", safety[0]["quote"], "red"
        elif sig.keys() & STOP_SIGNALS:
            s = sig[next(k for k in ("S31", "S27", "S26", "S29") if k in sig)]
            score, tag, quote, tone = 5, "Drop-off risk", s["quote"], "red"
        elif any(s["issue"] in engines.RISK_OF_ISSUE for s in sig.values()):
            s = max((s for s in sig.values() if s["issue"] in engines.RISK_OF_ISSUE), key=lambda s: engines.RISK_OF_ISSUE[s["issue"]][2])
            _, label, w = engines.RISK_OF_ISSUE[s["issue"]]
            score, tag, quote, tone = 4.5, f"Drop-off risk: {label}", s["quote"], "red" if w >= 2 else "orange"
        elif c["call_id"] in missed:
            p = next(p for p in d.promises if p["call_id"] == c["call_id"] and p["status"] == "missed")
            score, tag, quote, tone = 4, "Promised callback missed", p["quote"], "orange"
        elif "S15" in sig:
            # the clearest of the call's payer-requirement lines (transcription can garble a short one)
            q = max((sig[k]["quote"] or "" for k in ("S15", "S18", "S12", "S13") if k in sig), key=len)
            score, tag, quote, tone = 4, "PA pended for missing documents", q, "orange"
        elif c["external_call_id"] in r1_calls:
            told = "; ".join(t["requested"][:2]) or "a partial list"
            said = next((sig[k]["quote"] for k in ("S17", "S22", "S18") if k in sig), None)
            score, tag, quote, tone = 3, f"Gap: office was told '{told}'", said, "navy"
        elif sig.keys() & {"S23", "S24"}:
            s = sig.get("S23") or sig.get("S24")
            score, tag, quote, tone = 3, "Cost worry", s["quote"], "orange"
        elif any(s["issue"] in ("step_therapy", "new_pa_form", "pa_denied") for s in sig.values()):
            s = next(s for s in sig.values() if s["issue"] in ("step_therapy", "new_pa_form", "pa_denied"))
            score, tag, quote, tone = 3.5, s["signal_name"], s["quote"], "orange"
        elif friction_by_call[str(c["call_id"])]:
            it = next(i for i in d.friction([c]))
            score, tag, quote = 1, it["label"], it["quote"]
        if score:
            moments.append({"day": t["day"], "call_id": t["call_id"], "external_call_id": t["external_call_id"], "kind": "Call",
                            "quote": quote, "tag": tag, "tone": tone, "score": score})
    moments = sorted(sorted(moments, key=lambda m: -m["score"])[:4], key=lambda m: m["day"])

    show = []
    if spans:
        longest = max(spans, key=d.span_days)
        reason = Counter(i["label"] for c in longest["calls"] for i in d.friction([c])).most_common(1)
        show.append({"text": f"{STAGE_TITLE.get(longest['stage'], longest['stage'])} took {d.span_days(longest)} days"
                             + (f" – {reason[0][0].lower()} heard most" if reason else "")
                             + (" (still in progress)" if longest["end"] is None else ""),
                     "call_id": str(longest["calls"][-1]["call_id"])})
    cost = [t for t in timeline if {s["signal_id"] for s in t["signals"]} & {"S23", "S24"}]
    if cost:
        show.append({"text": f"Cost came up on {plural_n(len(cost), 'call')} (first on Day {cost[0]['day']})", "call_id": cost[0]["call_id"]})
    moods = [t for t in timeline if t["sentiment"] in ("negative", "mixed")]
    stop = [t for t in timeline if {s["signal_id"] for s in t["signals"]} & STOP_SIGNALS]
    if moods:
        show.append({"text": f"Mood turned {moods[0]['sentiment']} from Day {moods[0]['day']}"
                             + (f"; drop-off language on Day {stop[-1]['day']}" if stop else ""), "call_id": moods[0]["call_id"]})
    misses = [t for t in timeline if t["call_id"] in {str(x) for x in missed}]
    if misses:
        show.append({"text": f"{plural_n(len(misses), 'promised follow-up')} not made (Day {misses[0]['day']})", "call_id": misses[0]["call_id"]})
    if not show:
        show.append({"text": "No delays or worries heard on this patient's calls", "call_id": timeline[-1]["call_id"]})

    r3 = next((i for i in ins if i["rule_id"] == "R3"), None)
    level = pr["level"] if pr else None
    risk = ({"label": "High risk of stopping", "tone": "red"} if (r3 and r3["band"] == "high") or level == "High" else
            {"label": "At risk – watch", "tone": "amber"} if r3 or level == "Medium" else
            {"label": "Open gap", "tone": "amber"} if any(i["rule_id"] != "IDCHECK" for i in ins) else
            {"label": "On track", "tone": "green"})
    nxt = next((i for i in sorted(ins, key=lambda i: SEVERITY.get(i["rule_id"], 5)) if i["rule_id"] != "IDCHECK"), None)
    risk_next = ({"action": pr["next_step"], "owner": pr["owner"], "detail": "Heard on the calls: " + ", ".join(pr["categories"]).lower()
                  + (f" – latest: “{pr['quote']}”" if pr["quote"] else "")} if pr and pr["level"] != "Low" else None)
    return {"band": band, "moments": moments, "show": show, "risk": risk, "next": nxt, "risk_next": risk_next}
