"""Numbers behind the insight workspace screens. Deterministic: no AI in this module.

Inputs are what the pipeline stored per call (signals, contact reason, resolved on the call, holds, handoffs, safety
findings) and the cross-call rule outputs (ci_insights), plus the simulated demo volume (app.mock) when it is on.
"Normal" is the previous 13 weeks of conversations; with too little history it falls back to ci_baseline (synthetic).
"""
from bisect import bisect_right
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta

from app import mock
from app.cache import cached
from app.db import POOL_READY, fetch_all
from app.rules import AS_OF
from app.services.extraction import CONTACT_REASONS

STAGE_ORDER = ["Enrollment", "Benefits verification", "Prior authorization & appeal", "Copay & assistance",
               "Specialty pharmacy & first fill", "Nurse education", "Adherence & refill"]
FRICTION_TYPES = ["Missing documents", "Unclear next step", "Waiting, no update", "Cost worry",
                  "Hesitation & logistics", "Handoff / transfer"]
PARTIES = ["Physician office", "Payer", "Hub process", "Patient", "Specialty pharmacy"]

# Signal -> (friction type, who the friction is with). None = the other party on that call.
FRICTION = {
    "S01": ("Missing documents", "Physician office"), "S02": ("Missing documents", "Physician office"),
    "S03": ("Missing documents", "Physician office"), "S04": ("Missing documents", "Physician office"),
    "S05": ("Missing documents", "Patient"), "S28": ("Missing documents", "Patient"),
    "S15": ("Missing documents", "Payer"),
    "S17": ("Unclear next step", "Hub process"), "S22": ("Unclear next step", "Hub process"),
    "S18": ("Unclear next step", "Hub process"),
    "S06": ("Waiting, no update", "Physician office"), "S09": ("Waiting, no update", "Physician office"),
    "S07": ("Waiting, no update", None), "S10": ("Waiting, no update", "Patient"), "S29": ("Waiting, no update", "Patient"),
    "S23": ("Cost worry", "Patient"), "S24": ("Cost worry", "Patient"),
    "S25": ("Hesitation & logistics", "Patient"), "S26": ("Hesitation & logistics", "Patient"),
    "S27": ("Hesitation & logistics", "Patient"), "S31": ("Hesitation & logistics", "Patient"),
    "S11": ("Handoff / transfer", None),
    # issues the signal library has no signal for (simulated demo volume)
    "M01": ("Waiting, no update", "Specialty pharmacy"), "M02": ("Hesitation & logistics", "Patient"),
    "M03": ("Missing documents", "Payer"), "M04": ("Waiting, no update", "Payer"), "M05": ("Missing documents", "Payer"),
    "M06": ("Cost worry", "Patient"),
}
FRICTION_BY_ISSUE = {"step_therapy": ("Missing documents", "Payer")}  # S13 is informational unless it is a new rule
PARTY_OF_CALL = {"provider_office": "Physician office", "payer": "Payer", "patient": "Patient", "caregiver": "Patient",
                 "voicemail": "Patient", "specialty_pharmacy": "Specialty pharmacy"}
PAYER_REQUIREMENT = {"S12", "S13", "S15", "S17", "S18"}
DROP_OFF = {"S23", "S24", "S25", "S26", "S27", "S28", "S29", "S31"}
NOT_A_REASON = {"S08", "S19", "S20", "S21", "S30", "S36", "S37"}  # protective / bookkeeping signals

# What a friction pattern usually means, and who usually owns the fix (suggested only: Ipsen decides who acts).
MEANING = {
    "Missing documents": "Office needs support with enrollment / PA paperwork",
    "Unclear next step": "Requirements or next steps not communicated clearly",
    "Waiting, no update": "Items stall between parties; nobody owns the next update",
    "Cost worry": "Affordability barrier: copay support or assistance not yet in place",
    "Hesitation & logistics": "Patient unsure about starting: education or logistics support needed",
    "Handoff / transfer": "Handoffs between teams are not confirmed",
}
# Neil (16 Oct review): group by signal, not by program. Every signal heard maps to one issue; every issue to a category.
PAY, AFF, PHA, OFF, HUB = "Payer & authorization", "Affordability", "Pharmacy & dispensing", "Paperwork & offices", "Hub service"
PAT, SAF = "Patient", "Safety & medical"
ACCESS_CATEGORIES = [PAY, AFF, PHA, OFF, HUB]


def _i(label, category, entity, owner, meaning, action):
    return {"label": label, "category": category, "entity": entity, "owner": owner, "meaning": meaning, "action": action}


ISSUES = {
    "step_therapy": _i("Step therapy required", PAY, "payer", "Market Access",
                       "Payer now wants proof of a prior therapy before it approves",
                       "Market Access confirms the new criteria; offices get a step-therapy checklist"),
    "pa_docs": _i("PA pended: missing documents", PAY, "payer", "Field Access team",
                  "PAs go in without the clinical documents the payer needs",
                  "Send offices the payer's document checklist before they submit"),
    "lmn": _i("Medical necessity letter needed", PAY, "payer", "Market Access",
              "Payer requires a letter that offices don't send up front", "Add the letter template to the office starter pack"),
    "payer_criteria": _i("Payer clinical criteria stated", PAY, "payer", "Market Access",
                         "Payer lists the clinical documents it needs", "Keep the hub payer guide current"),
    "req_surprise": _i("Requirement not passed on", PAY, "payer", "Patient Services Lead",
                       "What the payer asks for is not what offices are told", "One answer per payer rule in the hub payer guide"),
    "pa_denied": _i("PA denied, appeal needed", PAY, "payer", "Market Access",
                    "Denials push patients into appeals and add weeks", "Review the denial reasons with Market Access"),
    "new_pa_form": _i("New PA form required", PAY, "payer", "Market Access",
                      "Payer changed its PA form; submissions on the old one bounce back",
                      "Send offices the new form and update the hub template"),
    "reauth": _i("Re-authorization due", PAY, "payer", "Field Access team",
                 "Renewals need updated labs from the office", "Start re-authorizations 30 days before they expire"),
    "coverage_change": _i("Plan changed at renewal", PAY, "payer", "Patient Services",
                          "New plan year: benefits must be checked again", "Re-check benefits proactively in December"),
    "oop": _i("Out-of-pocket cost worry", AFF, "payer", "Patient Services",
              "Patients worry about what they will pay", "Offer copay support on the first call"),
    "copay_not_applied": _i("Copay card not applied", AFF, "payer", "Market Access",
                            "The plan no longer counts the copay card – patients are charged full price",
                            "Copay vendor and Market Access review the plan's accumulator rules"),
    "deductible": _i("Deductible reset", AFF, "payer", "Patient Services",
                     "Seasonal: January deductibles raise the cost of the first refill",
                     "Warn patients in December; check copay program maximums"),
    "hardship": _i("Financial hardship", AFF, None, "Patient Services",
                   "A change in income puts therapy at risk", "Foundation referral on the same call"),
    "assist_incomplete": _i("Assistance form unfinished", AFF, None, "Patient Services",
                            "Patients start the assistance application but don't finish it",
                            "Finish the application with the patient on the call"),
    "medicare_copay": _i("Copay card not allowed (Medicare)", AFF, "payer", "Patient Services",
                         "Medicare patients can't use the copay card and need a foundation",
                         "Route Medicare patients to the foundation at the benefits check"),
    "shipment_delay": _i("Shipment delayed", PHA, "pharmacy", "Trade / pharmacy lead",
                         "The specialty pharmacy holds or delays the first fill",
                         "Trade team reviews the pharmacy's turnaround; proactive status updates to patients"),
    "refill_delay": _i("Late refills", PHA, "pharmacy", "Trade / pharmacy lead",
                       "Refills arrive late and patients run short", "Pharmacy service review; refill reminders 10 days out"),
    "sp_unreachable": _i("Pharmacy can't reach the patient", PHA, "pharmacy", "Patient Services",
                         "Referral at risk of closing before the first fill", "Hub sets up a three-way call with the pharmacy"),
    "missing_signature": _i("Prescriber signature missing", OFF, "office", "Field Access team",
                            "Forms come back unsigned", "Field Access visit; offer e-signature"),
    "missing_card": _i("Insurance card copy missing", OFF, None, "Patient Services",
                       "The benefits check waits on the insurance card", "Ask for a photo of the card on the welcome call"),
    "fax_incomplete": _i("Fax incomplete", OFF, "office", "Field Access team",
                         "Pages are lost in fax transmission", "Offer portal upload instead of fax"),
    "missing_clinical": _i("Notes or labs missing", OFF, "office", "Field Access team",
                           "The office sends forms without the clinical data the PA needs",
                           "Field Access reviews the PA checklist with the office"),
    "missing_consent": _i("Patient consent missing", OFF, None, "Patient Services",
                          "Consent page not signed", "Collect consent electronically on the welcome call"),
    "office_unavailable": _i("Office staff unavailable", OFF, "office", "Field Access team",
                             "Only one person at the office handles the forms", "Agree a set weekly time to reach the office"),
    "office_backlog": _i("Practice backlog", OFF, "office", "Field Access team",
                         "The office admits a backlog", "Field Access support visit"),
    "office_education": _i("Same office, same mistake", OFF, "office", "Field Access team",
                           "The same office repeats the same error", "Targeted office education"),
    "repeat_contact": _i("Repeat calls", HUB, None, "Patient Services Lead",
                         "People call back because nothing moved", "Give a dated status update so nobody needs to call back"),
    "vague_req": _i("Requirements explained vaguely", HUB, None, "Patient Services Lead",
                    "Loose instructions from the hub; offices send the wrong thing",
                    "Close requirement calls with the exact document list"),
    "generic_close": _i("No next step agreed", HUB, None, "Patient Services Lead",
                        "Calls end with no owner or date", "Close every call with the next step, an owner and a date"),
    "hold_transfer": _i("Hold or transfer", HUB, None, "Patient Services Lead",
                        "Callers wait while the hub checks with others", "Give agents direct view of pharmacy and payer status"),
    "unreachable": _i("Patient unreachable / voicemail", HUB, None, "Patient Services",
                      "Outreach doesn't land", "Text before calling; agree a callback time"),
    "frustration": _i("Caller frustrated", HUB, None, "Patient Services Lead",
                      "Callers repeat themselves across calls", "One case owner; notes visible to every agent"),
    "hesitation": _i('Hesitation – "need to think about it"', PAT, None, "Nurse educator",
                     "Patient unsure about starting", "Nurse educator call to talk it through"),
    "declines": _i("Declines the next step", PAT, None, "Case manager", "Patient puts off the next step", "Case manager follow-up"),
    "logistics": _i("Travel or delivery barrier", PAT, None, "Patient Services",
                    "Travel or delivery makes therapy hard", "Arrange home delivery or a local lab"),
    "stop_intent": _i("Thinking of stopping", PAT, None, "Nurse educator",
                      "Patient may stop therapy", "Nurse educator call within 48 hours"),
    "missed_doses": _i("Missed doses", PAT, None, "Nurse educator", "Doses are being missed", "Adherence check-in and reminders"),
    "side_effect": _i("Possible side effect", SAF, None, "Safety reviewer",
                      "Side effect mentioned on a call", "Human safety review; nurse follow-up"),
    "medical_q": _i("Medical question", SAF, None, "Medical Information",
                    "A question the hub must refer", "Refer to Medical Information"),
}
ISSUE_OF_SIGNAL = {"S01": "missing_signature", "S02": "missing_card", "S03": "fax_incomplete", "S04": "missing_clinical",
                   "S05": "missing_consent", "S06": "office_unavailable", "S07": "repeat_contact", "S09": "office_backlog",
                   "S10": "unreachable", "S11": "hold_transfer", "S12": "lmn", "S13": "payer_criteria", "S15": "pa_docs",
                   "S16": "req_surprise", "S17": "vague_req", "S18": "req_surprise", "S22": "generic_close", "S23": "oop",
                   "S24": "hardship", "S25": "logistics", "S26": "hesitation", "S27": "declines", "S28": "assist_incomplete",
                   "S29": "sp_unreachable", "S31": "stop_intent", "S32": "missed_doses", "S33": "side_effect",
                   "S34": "medical_q", "S35": "frustration", "S38": "office_education"}
# Patients at risk of dropping off: what was heard, how much it weighs, and the suggested next step.
RISK_CATEGORIES = [
    ("cost", "Cost worries", {"oop", "copay_not_applied", "deductible", "hardship", "medicare_copay"}, 1.5,
     "Patient Services: copay or foundation options this week"),
    ("think", '"Need to think about it"', {"hesitation"}, 2.0, "Nurse educator call to talk it through"),
    ("pharmacy", "Waiting on pharmacy", {"shipment_delay", "refill_delay", "sp_unreachable"}, 1.0,
     "Chase the specialty pharmacy and give the patient a date"),
    ("side_effects", "Side-effect worries", {"side_effect"}, 1.5, "Nurse educator follow-up (safety report already routed)"),
    ("stopping", "Thinking of stopping", {"stop_intent"}, 3.0, "Nurse educator call within 48 hours"),
    ("missed", "Missed doses", {"missed_doses"}, 1.5, "Adherence check-in and a reminder plan"),
    ("logistics", "Distance / logistics", {"logistics"}, 1.5, "Arrange home delivery or a local lab"),
    ("declined", "Declined next step", {"declines"}, 2.5, "Case manager follow-up call"),
    ("application", "Application not finished", {"assist_incomplete"}, 1.5, "Finish the assistance application together"),
    ("frustrated", "Frustrated with the process", {"frustration"}, 1.0, "One case owner calls back with a dated plan"),
]
ON_THERAPY = {"Nurse education", "Adherence & refill"}  # after the first shipment
# Call summary sub-reasons: what a call was about, in more detail than the contact reason.
SUB_OF_ISSUE = {
    "pa_docs": "Documents for PA", "lmn": "Documents for PA", "req_surprise": "Documents for PA", "vague_req": "Documents for PA",
    "step_therapy": "Step therapy", "pa_denied": "Denial & appeal", "new_pa_form": "New PA form", "reauth": "Re-authorization",
    "payer_criteria": "Benefits check", "coverage_change": "Coverage changed at plan renewal",
    "missing_signature": "Missing paperwork", "missing_card": "Missing paperwork", "fax_incomplete": "Missing paperwork",
    "missing_consent": "Missing paperwork", "office_unavailable": "Enrollment form status", "office_backlog": "Enrollment form status",
    "oop": "Copay card enrollment", "copay_not_applied": "Copay card not applied", "deductible": "Deductible reset",
    "hardship": "Foundation / assistance", "assist_incomplete": "Foundation / assistance", "medicare_copay": "Foundation / assistance",
    "shipment_delay": "Where is my shipment", "refill_delay": "Where is my shipment", "sp_unreachable": "Pharmacy can't reach patient",
    "hesitation": "First fill scheduling", "declines": "First fill scheduling", "logistics": "Travel & logistics",
    "side_effect": "Side effect reported", "medical_q": "Dosing question", "missed_doses": "Missed doses",
    "stop_intent": "Thinking of stopping",
}
DEFAULT_SUB = {"Enrollment": "Enrollment form status", "Benefits & coverage": "Benefits check",
               "Prior authorization": "PA status check", "Affordability / copay": "Copay card enrollment",
               "Prescription / shipment status": "Where is my shipment", "Therapy start & education": "Nurse onboarding",
               "Side effects / dosing": "Side effect reported", "Other": "General question"}
STAGE_SHORT = {"Enrollment": "Enroll", "Benefits verification": "Benefits", "Prior authorization & appeal": "Prior auth",
               "Copay & assistance": "Copay", "Specialty pharmacy & first fill": "Pharmacy", "Nurse education": "Nurse",
               "Adherence & refill": "Refill"}
STAGE_SLUG = {"Enrollment": "enrollment", "Benefits verification": "benefits", "Prior authorization & appeal": "prior-authorization",
              "Copay & assistance": "copay", "Specialty pharmacy & first fill": "pharmacy", "Nurse education": "nurse-start",
              "Adherence & refill": "refills"}
STAGE_TITLE = {"Enrollment": "Enrollment", "Benefits verification": "Benefits check", "Prior authorization & appeal": "Prior auth",
               "Copay & assistance": "Copay help", "Specialty pharmacy & first fill": "Pharmacy", "Nurse education": "Nurse start",
               "Adherence & refill": "Refills"}

OWNER = {"Physician office": "Field Access team", "Payer": "Market Access", "Hub process": "Patient Services Lead",
         "Patient": "Patient Services", "Specialty pharmacy": "Trade / pharmacy lead"}


@dataclass(frozen=True)
class Filters:
    program: str | None = None
    stage: str | None = None
    payer: str | None = None
    days: int = 0  # 0 = every analysed call
    sp: str | None = None  # specialty pharmacy

    def in_scope(self, c: dict) -> bool:
        """Every filter except the period."""
        return ((not self.program or c["program_id"] == self.program) and (not self.payer or c["payer_id"] == self.payer)
                and (not self.stage or c["journey_stage"] == self.stage) and (not self.sp or c.get("sp_id") == self.sp))

    def keep(self, c: dict) -> bool:
        d = c["call_datetime"].date()
        return self.in_scope(c) and (not self.days or AS_OF - timedelta(days=self.days - 1) <= d <= AS_OF)


def pct(n, d):
    return round(100 * n / d) if d else None


def vs_pct(observed, normal):
    if observed is None or normal is None:
        return None
    delta = observed - normal
    return {"normal": normal, "delta": round(delta), "direction": "up" if delta >= 3 else "down" if delta <= -3 else "flat"}


def vs_rate(count, weeks, normal_per_week):
    rate = count / weeks if weeks else 0
    ratio = rate / normal_per_week if normal_per_week else None
    return {"count": count, "per_week": round(rate, 2), "normal": normal_per_week,
            "ratio": round(ratio, 1) if ratio is not None else None,
            "direction": "up" if ratio and ratio >= 1.5 else "down" if ratio is not None and ratio <= 0.67 else "flat"}


def _mmss(v):
    try:
        m, s = str(v).split(":")[-2:]
        return int(m) * 60 + int(s)
    except (ValueError, TypeError):
        return None


def display_payer(name):
    return None if not name or name.startswith("(") else name


SCORE_AREAS = ["process_adherence", "behavioral", "sentiment", "communication", "compliance"]


def demo_scores(call_id) -> dict:
    """MOCK quality scores for the Qualivio-style agent screens (not computed from the call). Derived from the call id so
    a call always shows the same numbers; replaced by Qualivio's real AI scoring when the two products are joined."""
    import hashlib
    h = hashlib.sha256(str(call_id).encode()).digest()
    return {a: min(100.0, round(78 + (h[i] % 23) + (h[i + 5] % 10) / 10, 1)) for i, a in enumerate(SCORE_AREAS)}


def insight_key(i: dict) -> str:
    return f"{i['rule_id']}|{i['subject_type']}|{i['subject_id']}"


# Every table the screens read. Loaded together, in parallel: the database is a ~250 ms round trip away, so one
# query after another would make every screen take seconds.
TABLES = {
    "baseline": "SELECT * FROM ci_baseline",
    "calls": """
        SELECT c.*, p.patient_name, p.dob, pr.practice_name, py.payer_name, pg.drug, pg.program_name,
               st.staff_name, st.role AS staff_role, e.summary, e.contact_reason, e.resolved_on_call,
               e.resolution_note, e.identity_verified, e.sentiment, e.raw
        FROM ci_calls c
        LEFT JOIN ci_patients p ON p.patient_id = c.patient_id
        LEFT JOIN ci_practices pr ON pr.practice_id = c.practice_id
        LEFT JOIN ci_payers py ON py.payer_id = c.payer_id
        LEFT JOIN ci_programs pg ON pg.program_id = c.program_id
        LEFT JOIN ci_staff st ON st.staff_id = c.staff_id
        LEFT JOIN ci_call_extractions e ON e.call_id = c.call_id
        WHERE c.status = 'completed' ORDER BY c.call_datetime""",
    "signals": """SELECT cs.*, s.signal_name, s.insight_type FROM ci_call_signals cs JOIN ci_signals s USING (signal_id)
                  ORDER BY cs.timestamp_s NULLS FIRST""",
    "promises": """SELECT cp.*, ps.status, ps.kept_by_call_id FROM ci_call_promises cp
                   JOIN ci_promise_status ps ON ps.promise_id = cp.id""",
    "actions": "SELECT * FROM ci_insight_actions",
    "insights": """SELECT i.*, a.priority, a.insight_type FROM ci_insights i
                   LEFT JOIN ci_action_catalog a USING (rule_id) ORDER BY i.rule_id, i.subject_id""",
    "documents": "SELECT * FROM ci_call_documents",
    "risk": "SELECT * FROM ci_patient_risk",
    "safety": """SELECT s.*, r.status AS review_status, r.reviewed_at FROM ci_call_safety s
                 LEFT JOIN ci_safety_review r USING (safety_key) ORDER BY s.call_id, s.timestamp_s""",
    "segments": "SELECT call_id, start_s, end_s FROM ci_call_segments",
    "milestones": "SELECT * FROM ci_case_milestones",
    "patients": """SELECT p.*, pg.drug, pg.program_name, pr.practice_name, py.payer_name, dr.prescriber_name
                   FROM ci_patients p LEFT JOIN ci_programs pg USING (program_id)
                   LEFT JOIN ci_practices pr USING (practice_id) LEFT JOIN ci_payers py USING (payer_id)
                   LEFT JOIN ci_prescribers dr USING (prescriber_id) ORDER BY p.patient_name""",
    "signal_library": "SELECT signal_id, signal_name, insight_type FROM ci_signals",
}


@cached
def load_tables() -> dict:
    with ThreadPoolExecutor(max_workers=POOL_READY) as pool:
        t = dict(zip(TABLES, pool.map(fetch_all, TABLES.values())))
    return mock.augment(t) if mock.ENABLED else t


class Data:
    """Everything the screens need for one filter selection (the endpoints cache the results)."""

    def __init__(self, f: Filters):
        self.f = f
        t = load_tables()
        self.baseline = defaultdict(dict)
        for b in t["baseline"]:
            self.baseline[b["metric"]][b["key"]] = float(b["normal"])
        self.all_calls = [dict(c) for c in t["calls"]]
        for c in self.all_calls:
            c["raw"] = c["raw"] or {}
            c["payer_display"] = display_payer(c["payer_name"])
            c["live"] = c["other_party_type"] not in ("voicemail", "unknown", None)
            c["day"] = c["call_datetime"].date()
            c.setdefault("mock", False)
            c.setdefault("sp_id", None)
            c.setdefault("sp_name", None)
        self.by_id = {c["call_id"]: c for c in self.all_calls}
        self.by_ext = {c["external_call_id"]: c for c in self.all_calls}
        self.calls = [c for c in self.all_calls if f.keep(c)]
        self.ids = {c["call_id"] for c in self.calls}
        self.sig = defaultdict(list)
        for s in t["signals"]:
            s = dict(s)
            s["issue"] = s.get("issue") or ISSUE_OF_SIGNAL.get(s["signal_id"])
            if s.get("mock") and s["issue"] in ISSUES:  # simulated calls: name the specific issue, not the library signal
                s["signal_name"] = ISSUES[s["issue"]]["label"]
            self.sig[s["call_id"]].append(s)
        for c in self.all_calls:  # recorded calls: a sub-reason from the first issue heard (simulated ones carry their own)
            if not c.get("sub_reason"):
                iss = next((s["issue"] for s in self.sig[c["call_id"]] if s["issue"] in SUB_OF_ISSUE), None)
                c["sub_reason"] = SUB_OF_ISSUE[iss] if iss else DEFAULT_SUB.get(c["contact_reason"], "General question")
        first = self.calls[0]["call_datetime"].date() if self.calls else AS_OF
        self.start = max(first, AS_OF - timedelta(days=f.days - 1)) if f.days else first
        self.weeks = max(1.0, ((AS_OF - self.start).days + 1) / 7)
        # "Now" vs "normal": the period (the last 4 weeks when every call is selected) against the 13 weeks before it.
        self.cur_days = f.days or 28
        self.cur_start = AS_OF - timedelta(days=self.cur_days - 1)
        self.prior_start = self.cur_start - timedelta(days=91)
        self.scope = [c for c in self.all_calls if f.in_scope(c)]
        self.recent = [c for c in self.scope if c["day"] >= self.cur_start]
        self.prior = [c for c in self.scope if self.prior_start <= c["day"] < self.cur_start]
        self.case_calls = defaultdict(list)
        self.patient_calls = defaultdict(list)
        for c in self.all_calls:
            if c["case_id"]:
                self.case_calls[c["case_id"]].append(c)
            if c["patient_id"]:
                self.patient_calls[c["patient_id"]].append(c)
        self.case_times = defaultdict(list)  # (case, stage) -> call times: a repeat is about the same open item
        for c in self.all_calls:
            if c["case_id"]:
                self.case_times[(c["case_id"], c["journey_stage"])].append(c["call_datetime"])
        self.promises = t["promises"]
        self.documents, self.risk, self.safety_raw = t["documents"], t["risk"], t["safety"]
        self.segments, self.milestones = t["segments"], t["milestones"]
        self.patients = {p["patient_id"]: p for p in t["patients"]}
        self.actions = {a["insight_key"]: a for a in t["actions"]}
        self.insights = []
        for i in t["insights"]:
            calls = {self.by_ext.get(e["external_call_id"], {}).get("call_id") for e in i["evidence"]}
            if not calls & self.ids:
                continue
            self.insights.append(self.decorate(dict(i)))
        self.open_insights = [i for i in self.insights if i["status"] not in ("fixed", "expected")]
        if len(self.prior) >= 150:
            self._baseline_from_history()

    def _baseline_from_history(self):
        """Normal = the 13 weeks before the period, for the same programs / payers / stages / pharmacies."""
        b, prior = self.baseline, self.prior
        live = [c for c in prior if c["live"] and c["resolved_on_call"] is not None]
        b["fcr"]["all"] = pct(sum(1 for c in live if c["resolved_on_call"]), len(live))
        rep = [c for c in prior if c["live"]]
        b["repeat_7d"]["all"] = pct(sum(1 for c in rep if self.repeat_7d(c)), len(rep))
        for r in CONTACT_REASONS:
            cs = [c for c in prior if c["contact_reason"] == r]
            b["contact_reason_share"][r] = pct(len(cs), len(prior)) or 0
            lv = [c for c in cs if c["live"] and c["resolved_on_call"] is not None]
            if len(lv) >= 20:
                b["fcr"][r] = pct(sum(1 for c in lv if c["resolved_on_call"]), len(lv))
            rp = [c for c in cs if c["live"]]
            if len(rp) >= 20:
                b["repeat_7d"][r] = pct(sum(1 for c in rp if self.repeat_7d(c)), len(rp))
        drop = sum(1 for c in prior for s in self.sig[c["call_id"]] if s["signal_id"] in DROP_OFF)
        b["drop_off_weekly"]["all"] = round(drop / 13, 2)

    # ------------------------------------------------------------------ insight status (actions survive recomputes)
    def decorate(self, i: dict) -> dict:
        key = insight_key(i)
        a = self.actions.get(key)
        latest = max((e["date"] for e in i["evidence"]), default=None)
        default = "new" if latest and date.fromisoformat(latest) >= AS_OF - timedelta(days=7) else "open"
        i.update(insight_key=key, status=a["status"] if a else default,
                 owner=(a["owner"] if a and a["owner"] else i["owner_team"]),
                 useful=a["useful"] if a else None, action_note=a["action_note"] if a else None,
                 action_date=a["action_date"].isoformat() if a and a["action_date"] else None,
                 score=float(i["score"]) if i.get("score") is not None else None,
                 patient=self.patient_of(i))
        return i

    def status_of(self, key: str, latest: date | None) -> dict:
        a = self.actions.get(key)
        default = "new" if latest and latest >= AS_OF - timedelta(days=7) else "open"
        return {"insight_key": key, "status": a["status"] if a else default, "owner": a["owner"] if a else None,
                "action_note": a["action_note"] if a else None,
                "action_date": a["action_date"].isoformat() if a and a["action_date"] else None,
                "useful": a["useful"] if a else None}

    def patient_of(self, i: dict):
        if i["subject_type"] == "patient":
            c = next((c for c in self.all_calls if c["patient_id"] == i["subject_id"]), None)
        elif i["subject_type"] == "case":
            c = next((c for c in self.all_calls if c["case_id"] == i["subject_id"]), None)
        elif i["subject_type"] == "call":
            c = self.by_ext.get(i["subject_id"])
        else:
            return None
        return {"patient_id": c["patient_id"], "patient_name": c["patient_name"]} if c and c["patient_id"] else None

    # ------------------------------------------------------------------ evidence
    def ev(self, c: dict, quote=None, label=None) -> dict:
        return {"call_id": str(c["call_id"]), "external_call_id": c["external_call_id"],
                "date": c["call_datetime"].date().isoformat(), "patient_id": c["patient_id"],
                "patient_name": c["patient_name"], "party": PARTY_OF_CALL.get(c["other_party_type"], "Other"),
                "practice_name": c["practice_name"], "payer_name": c["payer_display"], "stage": c["journey_stage"],
                "quote": quote, "label": label, "mock": c["mock"], "pharmacy": c["sp_name"]}

    def insight_evidence(self, i: dict) -> list[dict]:
        out = []
        for e in i["evidence"]:
            c = self.by_ext.get(e["external_call_id"])
            if c:
                out.append(self.ev(c, e.get("quote"), ", ".join(e.get("signals") or []) or None))
        return out

    # ------------------------------------------------------------------ friction (what is in the way, and with whom)
    def entity(self, c: dict, party: str) -> tuple[str, str]:
        if party == "Physician office":
            return c["practice_id"] or "office", c["practice_name"] or "Physician office"
        if party == "Payer":
            return c["payer_id"] or "payer", c["payer_display"] or "Payer (not named)"
        if party == "Patient":
            return c["patient_id"] or "patient", c["patient_name"] or "Patient"
        if party == "Specialty pharmacy":
            return c["sp_id"] or "pharmacy", c["sp_name"] or "Specialty pharmacy"
        return "hub", "Hub"

    def friction(self, calls=None) -> list[dict]:
        calls = self.calls if calls is None else calls
        ids = {c["call_id"] for c in calls}
        items = []
        for c in calls:
            for s in self.sig.get(c["call_id"], []):
                rule = FRICTION_BY_ISSUE.get(s["issue"]) or FRICTION.get(s["signal_id"])
                if not rule:
                    continue
                ftype, party = rule
                party = party or PARTY_OF_CALL.get(c["other_party_type"]) or "Hub process"
                items.append(self._item(c, ftype, party, s["quote"], s["signal_name"]))
            for h in c["raw"].get("handoffs", []):
                if not h.get("confirmed"):
                    items.append(self._item(c, "Handoff / transfer", "Hub process", h.get("quote"),
                                            f"Handoff to {h.get('to')} not confirmed"))
        for p in self.promises:
            if p["status"] == "missed" and p["call_id"] in ids:
                items.append(self._item(self.by_id[p["call_id"]], "Waiting, no update", "Hub process", p["quote"],
                                        "Promised follow-up missed"))
        return items

    def _item(self, c, ftype, party, quote, label):
        eid, name = self.entity(c, party)
        return {**self.ev(c, quote, label), "type": ftype, "with": party, "entity_id": eid, "entity": name,
                "day": c["day"]}

    # ------------------------------------------------------------------ per-call measures
    def repeat_7d(self, c: dict) -> bool:
        """Another contact on the same case and the same journey stage within 7 days."""
        if not c["case_id"]:
            return False
        times = self.case_times.get((c["case_id"], c["journey_stage"]), [])
        t = c["call_datetime"]
        i = bisect_right(times, t)
        return i < len(times) and times[i] <= t + timedelta(days=7)

    def later_calls(self, c: dict) -> list:
        """Calls on the same case after this one."""
        return [x for x in self.case_calls.get(c["case_id"], []) if x["call_datetime"] > c["call_datetime"]] if c["case_id"] else []

    def time_split(self, c: dict, segments: list[dict]) -> dict | None:
        if c.get("time"):
            return dict(c["time"])
        total = float(c["audio_duration_s"] or 0)
        if not total:
            return None
        merged = []
        for a, b in sorted((float(s["start_s"] or 0), float(s["end_s"] or s["start_s"] or 0)) for s in segments):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        blocks = []
        for blk in c["raw"].get("hold_or_transfer", []):
            a, b = _mmss(blk.get("start")), _mmss(blk.get("end"))
            if a is None:
                continue
            if b is None or b <= a:
                b = next((m[0] for m in merged if m[0] > a + 1), a)  # resumes at the next speech
            blocks.append(("transfer" if blk.get("kind") == "transfer" else "hold", a, min(b, total)))
        overlap = sum(max(0, min(b, y) - max(a, x)) for a, b in merged for _, x, y in blocks)
        talking = max(0.0, sum(b - a for a, b in merged) - overlap)
        hold = sum(y - x for k, x, y in blocks if k == "hold")
        transfer = sum(y - x for k, x, y in blocks if k == "transfer")
        return {"talking": talking, "hold": hold, "transfer": transfer, "silence": max(0.0, total - talking - hold - transfer),
                "total": total}

    def weekly(self, days: list[date]) -> list[dict]:
        n = max(1, -(-((AS_OF - self.start).days + 1) // 7))
        out = []
        for i in range(n):
            ws = AS_OF - timedelta(days=7 * (n - i) - 1)
            we = ws + timedelta(days=6)
            out.append({"week": ws.isoformat(), "label": f"{ws.strftime('%b')} {ws.day}",
                        "count": sum(1 for d in days if ws <= d <= we)})
        return out

    def fcr(self, calls) -> tuple[int | None, list]:
        live = [c for c in calls if c["live"] and c["resolved_on_call"] is not None]
        return pct(sum(1 for c in live if c["resolved_on_call"]), len(live)), live

    def repeat_pct(self, calls) -> tuple[int | None, list]:
        live = [c for c in calls if c["live"]]
        return pct(sum(1 for c in live if self.repeat_7d(c)), len(live)), live

    def current_stage(self) -> dict:
        return {pid: cs[-1]["journey_stage"] for pid, cs in self.patient_calls.items()}

    def stage_spans(self, patient_ids=None) -> dict:
        """Per patient, the stages in order as heard on the calls: [{stage, start, end, calls}].
        A stage ends when the next one starts; the current stage runs to the demo 'today' (end None)."""
        spans = defaultdict(list)
        pids = self.patient_calls if patient_ids is None else [p for p in patient_ids if p in self.patient_calls]
        for c in (c for pid in pids for c in self.patient_calls[pid]):
            pid = c["patient_id"]
            day = c["day"]
            if spans[pid] and spans[pid][-1]["stage"] == c["journey_stage"]:
                spans[pid][-1]["calls"].append(c)
            else:
                if spans[pid]:
                    spans[pid][-1]["end"] = day
                spans[pid].append({"stage": c["journey_stage"], "start": day, "end": None, "calls": [c]})
        return spans

    def all_calls_last(self, patient_id) -> date:
        return self.patient_calls[patient_id][-1]["day"]

    @staticmethod
    def span_days(span) -> int:
        return ((span["end"] or AS_OF) - span["start"]).days


def reasons_list():
    return list(CONTACT_REASONS)
