"""Step 4 - cross-call rules and next-best actions. Deterministic: no AI in this module.

Calls are grouped by their labels (case / patient / practice / payer) and ordered by date; each rule checks its
condition across the group and fires at most one insight per subject, carrying exactly one action from
ci_action_catalog (one rule -> one action).
"""
import json
import os
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

import psycopg2.extras

from app.db import fetch_all, get_conn
from app.logger import logger

AS_OF = date.fromisoformat(os.getenv("CI_AS_OF_DATE", "2027-03-20"))  # demo "today" (calls are Feb-Mar 2027)

R3_WEIGHTS = {"S23": 2, "S24": 1, "S25": 2, "S26": 3, "S27": 2, "S28": 1, "S29": 3, "S30": -2}  # Atul, R3
R2_WEIGHTS = {"S01": 2, "S02": 2, "S03": 1, "S04": 2, "S05": 2, "S06": 1, "S07": 1, "S09": 2, "S10": 1,
              "S11": 0.5, "S38": 1}  # draft: Atul's 'Score examples' sheet was not supplied
R2_WINDOW_DAYS = 30

ACTIONS = [
    # rule, insight type, title, action, owner team, priority, source
    ("R1", "Payer requirements", "Asked vs told mismatch",
     "Send the office the payer's exact document list before the PA is submitted", "Patient Services (access team)", "High",
     "Deck slide 11 - 'Office corrected before submission'"),
    ("R2", "Process adherence", "Practice that keeps stalling",
     "Field Access team visits the practice and walks staff through the enrollment and PA forms", "Field Access", "Medium",
     "Deck slide 11 - 'Field Access team educates the practice'"),
    ("R3", "Sentiment & engagement", "Patient drifting before first dose",
     "Offer bridge / quick-start supply and assistance early; case manager outreach within 2 business days",
     "Patient Services", "High", "Deck slide 11 - 'Bridge supply or assistance offered early'"),
    ("R4", "Call quality", "Vague requirements on a PA call",
     "Update the hub call guide: close every PA requirements call with a document recap and a confirmed date",
     "Patient Services Lead / Quality", "Medium", "Signal library S19-S22; rule R4"),
    ("R6", "Process adherence", "Promise not kept",
     "Complete the promised follow-up and tell the patient or office", "Hub operations", "Medium", "Rule R6"),
    ("SAFETY", "Safety & compliance", "Possible adverse event / medical question",
     "Route to Pharmacovigilance or Medical Information for human review", "Pharmacovigilance / Medical Information",
     "High", "Signal library S32-S34; deck screen 5"),
    ("IDCHECK", "Safety & compliance", "Identity not confirmed",
     "Confirm name and date of birth before discussing case details", "Quality & Compliance", "Low",
     "Signal library S37"),
]

# Synthetic PA milestones until CRM / payer data is connected (Phase 2). Clearly labelled in the source column.
MILESTONES = [
    ("20501", "pa_submitted", "2027-03-04"), ("20501", "pa_decision", "2027-03-09"),
    ("20512", "pa_submitted", "2027-03-05"), ("20512", "pa_decision", "2027-03-11"),
    ("20504", "pa_submitted", "2027-03-03"), ("20504", "pa_pended", "2027-03-11"),
    ("20504", "pa_resubmitted", "2027-03-17"), ("20504", "pa_decision", "2027-03-24"),
    ("20515", "pa_submitted", "2027-03-05"), ("20515", "pa_pended", "2027-03-12"),
    ("20515", "pa_resubmitted", "2027-03-18"), ("20515", "pa_decision", "2027-03-26"),
    ("20455", "pa_decision", "2027-03-08"),
]

# Document buckets for R1: a requirement counts as communicated if any of its words appear.
DOC_BUCKETS = {
    "letter of medical necessity": ["medical necessity", "lmn", "necessity letter"],
    "clinic notes": ["note"],
    "labs (ALP)": ["lab", "alp"],
    "ursodiol history": ["ursodiol", "udca"],
    "genetic test result": ["genetic"],
    "current weight": ["weight"],
    "prescription with dose": ["prescription", "dose"],
}


def init_rules_schema():
    sql = (Path(__file__).parent / "rules_schema.sql").read_text(encoding="utf-8")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        for rule, weights, src in (("R3", R3_WEIGHTS, "Cross-call rule R3: signal weights"),
                                   ("R2", R2_WEIGHTS, "Draft weights, to be calibrated with Ipsen")):
            for sig, w in weights.items():
                cur.execute("""INSERT INTO ci_rule_weights (rule_id, signal_id, weight, source) VALUES (%s, %s, %s, %s)
                               ON CONFLICT (rule_id, signal_id) DO UPDATE SET weight = EXCLUDED.weight, source = EXCLUDED.source""",
                            (rule, sig, w, src))
        for a in ACTIONS:
            cur.execute("""INSERT INTO ci_action_catalog (rule_id, insight_type, title, action, owner_team, priority, source)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (rule_id) DO UPDATE SET insight_type = EXCLUDED.insight_type, title = EXCLUDED.title,
                             action = EXCLUDED.action, owner_team = EXCLUDED.owner_team, priority = EXCLUDED.priority,
                             source = EXCLUDED.source""", a)
        for case_id, milestone, day in MILESTONES:
            cur.execute("""INSERT INTO ci_case_milestones (case_id, milestone, occurred_on, source) VALUES (%s, %s, %s, %s)
                           ON CONFLICT (case_id, milestone) DO UPDATE SET occurred_on = EXCLUDED.occurred_on""",
                        (case_id, milestone, day, "synthetic demo data (CRM in Phase 2)"))


def _band(score, high, watch):
    return "high" if score >= high else ("watch" if score >= watch else "low")


def _buckets(items: list[str]) -> set[str]:
    text = " | ".join(items).lower()
    return {b for b, words in DOC_BUCKETS.items() if any(re.search(rf"\b{re.escape(w)}", text) for w in words)}


def _ev(call, signal_ids=None, quote=None):
    return {"call_id": str(call["call_id"]), "external_call_id": call["external_call_id"],
            "date": call["call_datetime"].date().isoformat(), "signals": sorted(signal_ids or []), "quote": quote}


def recompute() -> dict:
    init_rules_schema()
    calls = fetch_all("""SELECT * FROM ci_calls WHERE status = 'completed' ORDER BY call_datetime""")
    by_id = {c["call_id"]: c for c in calls}
    sigs = defaultdict(list)
    for s in fetch_all("SELECT * FROM ci_call_signals ORDER BY timestamp_s NULLS FIRST"):
        if s["call_id"] in by_id:
            sigs[s["call_id"]].append(s)
    sig_ids = {cid: {s["signal_id"] for s in rows} for cid, rows in sigs.items()}
    docs = defaultdict(lambda: defaultdict(list))
    for d in fetch_all("SELECT * FROM ci_call_documents"):
        docs[d["call_id"]][d["list_type"]].append(d["item"])
    actions = {a["rule_id"]: a for a in fetch_all("SELECT * FROM ci_action_catalog")}
    milestones = defaultdict(dict)
    for m in fetch_all("SELECT * FROM ci_case_milestones"):
        milestones[m["case_id"]][m["milestone"]] = m["occurred_on"]

    insights, risk_rows, promise_rows = [], [], []

    def fire(rule, level, subject_type, subject_id, detail, evidence, score=None, band=None, title=None):
        a = actions[rule]
        insights.append((rule, level, subject_type, subject_id, title or a["title"], detail, score, band,
                         json.dumps(evidence), a["action"], a["owner_team"], AS_OF))

    # ---------------------------------------------------------------- R3 abandonment risk (per patient)
    by_patient = defaultdict(list)
    for c in calls:
        if c["patient_id"]:
            by_patient[c["patient_id"]].append(c)
    for pid, pcalls in by_patient.items():
        running, contributing_calls = 0.0, []
        for c in pcalls:
            hit = sig_ids.get(c["call_id"], set()) & set(R3_WEIGHTS)
            call_score = float(sum(R3_WEIGHTS[s] for s in hit))
            running = max(0.0, running + call_score)
            band = _band(running, 6, 3)
            risk_rows.append((pid, c["call_id"], call_score, running, band, json.dumps(sorted(hit))))
            if hit - {"S30"}:
                contributing_calls.append(_ev(c, hit))
        if running >= 3:
            missed = [e["external_call_id"] for e in contributing_calls if "S30" not in e["signals"]]
            fire("R3", "patient", "patient", pid,
                 f"Risk score {running:g} ({_band(running, 6, 3)}). Signals across {len(contributing_calls)} calls; "
                 f"no support offer made on {', '.join(missed) or 'none'}.", contributing_calls, running, _band(running, 6, 3))

    # ---------------------------------------------------------------- R2 practice friction (per practice, 30 days)
    by_practice = defaultdict(list)
    for c in calls:
        if c["practice_id"] and c["other_party_type"] == "provider_office" and c["call_datetime"].date() <= AS_OF:
            by_practice[c["practice_id"]].append(c)
    for prac, pcalls in by_practice.items():
        # 30-day window ending at the practice's latest call, so a burst of activity is scored as a whole.
        last = max(x["call_datetime"].date() for x in pcalls)
        pcalls = [x for x in pcalls if (last - x["call_datetime"].date()).days <= R2_WINDOW_DAYS]
        score, evidence, patients = 0.0, [], set()
        for c in pcalls:
            hit = sig_ids.get(c["call_id"], set()) & set(R2_WEIGHTS)
            if hit:
                score += sum(R2_WEIGHTS[s] for s in hit)
                evidence.append(_ev(c, hit))
                patients.add(c["patient_id"])
        band = _band(score, 10, 5)
        if band != "low":
            fire("R2", "practice", "practice", prac,
                 f"Friction score {score:g} over {R2_WINDOW_DAYS} days: {len(evidence)} calls, {len(patients)} patients held up.",
                 evidence, score, band)

    # ---------------------------------------------------------------- R4 call close vs outcome (per PA requirements call)
    by_case = defaultdict(list)
    for c in calls:
        if c["case_id"]:
            by_case[c["case_id"]].append(c)
    for c in calls:
        s = sig_ids.get(c["call_id"], set())
        # Only prior-authorization requirement calls to an office are judged on how they close.
        if not (s & {"S19", "S20", "S21", "S22", "S17"}) or c["other_party_type"] != "provider_office"                 or not (c["journey_stage"] or "").startswith("Prior authorization"):
            continue
        close = "recap + date" if {"S19", "S20"} <= s else ("generic" if s & {"S22", "S17"} else "partial")
        later = [x for x in by_case.get(c["case_id"], []) if x["call_datetime"] > c["call_datetime"]]
        rework = any(sig_ids.get(x["call_id"], set()) & {"S15", "S18"} for x in later)
        ms = milestones.get(c["case_id"], {})
        days = (ms["pa_decision"] - c["call_datetime"].date()).days if ms.get("pa_decision") else None
        if close == "generic":
            fire("R4", "call", "call", c["external_call_id"] or str(c["call_id"]),
                 f"Requirements described vaguely, no document list or date. "
                 f"Outcome: {'PA pended - rework' if rework else 'pending'}; "
                 f"{f'decision {days} days after this call (synthetic milestone)' if days is not None else 'no decision yet'}.",
                 [_ev(c, s & {"S17", "S22"})] + [_ev(x, sig_ids.get(x['call_id'], set()) & {'S15', 'S18'}) for x in later])

    # ---------------------------------------------------------------- R1 asked vs told (per case)
    # What the office was told is compared with what the payer requires: stated on a payer call for the same
    # case, or (until UC1 payer calls arrive) stated for the same payer + drug on another case within 14 days.
    for case_id, ccalls in by_case.items():
        told_so_far, flagged = [], None
        for c in ccalls:  # date order
            if sig_ids.get(c["call_id"], set()) & {"S15", "S18"}:
                continue  # rework call after a pend: it lists only the missing items, by design
            told = docs[c["call_id"]].get("requested_from_office") or []
            if not told or c["other_party_type"] != "provider_office" or not c["payer_id"]:
                continue
            told_so_far += told
            reqs, sources = set(), set()
            for x in calls:
                if x["payer_id"] == c["payer_id"] and x["program_id"] == c["program_id"] \
                        and abs((x["call_datetime"] - c["call_datetime"]).days) <= 14:
                    found = _buckets(docs[x["call_id"]].get("payer_required") or [])
                    if found:
                        reqs |= found
                        sources.add(x["case_id"])
            missing = reqs - _buckets(told_so_far)
            flagged = (c, told_so_far[:], missing, sources) if missing else None
        if flagged:
            c, told, missing, sources = flagged
            later = [x for x in ccalls if x["call_datetime"] > c["call_datetime"]
                     and sig_ids.get(x["call_id"], set()) & {"S15", "S18"}]
            src = "this case" if sources == {case_id} else f"same payer and drug, cases {', '.join(sorted(sources))}"
            fire("R1", "case", "case", case_id,
                 f"Office was told: {'; '.join(told)}. Payer requires ({src}), not passed on: "
                 f"{', '.join(sorted(missing))}." + (" Confirmed: PA later pended for the missing items." if later else ""),
                 [_ev(c)] + [_ev(x, sig_ids[x['call_id']] & {'S15', 'S18'}) for x in later],
                 score=len(missing), band="confirmed" if later else "predicted")

    # ---------------------------------------------------------------- R6 promise kept (per case)
    # Only contact promises can be checked against calls; faxes / emails / internal notes are not visible here.
    contact = re.compile(r"\b(call|check|follow|reach|ring|touch base|let .* know|update)", re.I)
    promises = fetch_all("SELECT * FROM ci_call_promises WHERE made_by_role = 'hub_staff'")
    for p in promises:
        c = by_id.get(p["call_id"])
        if not c:
            continue
        if not p["due_date"]:
            promise_rows.append((p["id"], "no date", None, AS_OF))
            continue
        if not contact.search(p["action"] or ""):
            promise_rows.append((p["id"], "not observable", None, AS_OF))
            continue
        later = [x for x in by_case.get(c["case_id"], []) if x["call_datetime"] > c["call_datetime"]]
        kept = next((x for x in later if x["call_datetime"].date() <= p["due_date"]), None)
        if kept:
            status = "kept"
        elif p["due_date"] >= AS_OF:
            status = "open"
        else:
            status = "missed" if later else "not verifiable"
        promise_rows.append((p["id"], status, kept["call_id"] if kept else None, AS_OF))
        if status == "missed":
            fire("R6", "case", "case", c["case_id"], f"Promised: {p['action']} (due {p['due_date']}). No contact on the case by then.",
                 [_ev(c, quote=p["quote"])])

    # ---------------------------------------------------------------- signal -> action (single-call rules)
    for c in calls:
        for s in sigs.get(c["call_id"], []):
            if s["signal_id"] in ("S32", "S33", "S34"):
                fire("SAFETY", "call", "call", c["external_call_id"] or str(c["call_id"]),
                     f"{s['signal_id']} heard: \"{s['quote']}\". Needs human review.", [_ev(c, {s['signal_id']}, s["quote"])])
        if c["other_party_type"] in ("patient", "caregiver", "provider_office") and "S37" not in sig_ids.get(c["call_id"], set()):
            fire("IDCHECK", "call", "call", c["external_call_id"] or str(c["call_id"]),
                 "Case details discussed without confirming name and date of birth on this call.", [_ev(c)])

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('ci_rules_recompute'))")  # one recompute at a time
        cur.execute("DELETE FROM ci_insights")
        cur.execute("DELETE FROM ci_patient_risk")
        cur.execute("DELETE FROM ci_promise_status")
        if insights:
            psycopg2.extras.execute_values(cur, """INSERT INTO ci_insights (rule_id, level, subject_type, subject_id, title, detail,
                score, band, evidence, action, owner_team, as_of) VALUES %s""", insights)
        if risk_rows:
            psycopg2.extras.execute_values(cur, "INSERT INTO ci_patient_risk (patient_id, call_id, call_score, running, band, contributing) VALUES %s",
                                           risk_rows)
        if promise_rows:
            psycopg2.extras.execute_values(cur, "INSERT INTO ci_promise_status (promise_id, status, kept_by_call_id, as_of) VALUES %s",
                                           promise_rows)
    summary = defaultdict(int)
    for i in insights:
        summary[i[0]] += 1
    logger.info("Rules recomputed as of %s: %s", AS_OF, dict(summary))
    return {"as_of": AS_OF.isoformat(), "insights": dict(summary), "calls": len(calls)}
