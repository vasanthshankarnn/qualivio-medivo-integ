"""The four Summary boxes as their own tabs (Neil, 16 Oct review): every item in the category, grouped by signal,
sliced by the filter bar. Deterministic: counts and comparisons over Data, no AI.

* access_issues  – Emerging access issues: each issue heard (step therapy, shipment delay, ...) per payer / pharmacy /
                   office, now vs its own normal.
* at_risk        – Patients at risk of dropping off: every patient whose calls carry drop-off signals, grouped by what
                   was heard, with a level and a suggested next step.
* call_summary   – Why patients and offices called: every conversation by reason and sub-reason, and who it was about.
* stuck          – Where patients get stuck: per journey stage, how much friction is heard, why and with whom.
"""
from collections import Counter, defaultdict
from datetime import timedelta
from functools import wraps

from app.analytics import (ACCESS_CATEGORIES, AS_OF, HUB, ISSUES, ON_THERAPY, PARTY_OF_CALL, RISK_CATEGORIES,
                           STAGE_ORDER, STAGE_SHORT, STAGE_SLUG, STAGE_TITLE, Data, pct)
from app.services.extraction import CONTACT_REASONS

WEEKS = 17          # trend charts: the 13-week normal plus the latest 4 weeks
WAIT_DAYS = 10
CAP = 15            # evidence excerpts sent with any one number (recorded calls first)
ROW_CAP = 6         # ... and with each row of a long list


# ------------------------------------------------------------------ evidence lists: recorded calls first, then newest
def cap_evidence(obj, n=CAP):
    """Copy of a payload with every evidence list cut to n excerpts (recorded calls first, then the newest)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.startswith("evidence") and isinstance(v, list):
                if v and isinstance(v[0], dict):
                    real = [e for e in v if not e.get("mock")]
                    sim = sorted((e for e in v if e.get("mock")), key=lambda e: str(e.get("date") or ""), reverse=True)
                    out[k] = (real + sim)[:n]
                else:
                    out[k] = v[:n]
            else:
                out[k] = cap_evidence(v, n)
        return out
    if isinstance(obj, list):
        return [cap_evidence(v, n) for v in obj]
    return obj


def capped(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return cap_evidence(fn(*args, **kwargs))
    return wrapper


# ------------------------------------------------------------------ shared helpers
def week_starts(n=WEEKS):
    return [AS_OF - timedelta(days=7 * (n - i) - 1) for i in range(n)]


def series(days, n=WEEKS):
    """Weekly counts for the last n weeks (oldest first), weeks ending on the demo 'today'."""
    starts = week_starts(n)
    first = starts[0]
    out = [0] * n
    for d in days:
        if first <= d <= AS_OF:
            out[min(n - 1, (d - first).days // 7)] += 1
    return out


def week_labels(n=WEEKS):
    return [f"{d.strftime('%b')} {d.day}" for d in week_starts(n)]


def entity_of(c, kind):
    if kind == "payer":
        return c["payer_id"] if c["payer_display"] else None, c["payer_display"]
    if kind == "pharmacy":
        return c["sp_id"], c["sp_name"]
    if kind == "office":
        return c["practice_id"], c["practice_name"]
    return None, None


def vs_text(ratio, status):
    if status == "New":
        return "new"
    if ratio is None:
        return "–"
    if ratio >= 1.95:
        return f"{ratio:.1f}".rstrip("0").rstrip(".") + "×"
    if ratio >= 1.05:
        return f"+{round((ratio - 1) * 100)}%"
    if ratio <= .95:
        return f"−{round((1 - ratio) * 100)}%"
    return "same"


def _status(cur, prior_n, ratio, expected, days):
    """cur / prior_n / expected count patients (one patient calling five times is one signal, not five). A week has
    few patients, so the bar for "new" and "rising" scales with the period."""
    need = 2 if days <= 7 else 3 if days <= 14 else 4
    if prior_n == 0 and cur >= need + (0 if days <= 7 else 0):
        return "New"
    if ratio is not None and ratio >= (2.2 if days <= 7 else 1.8) and cur >= need + 1 and cur - expected >= need:
        return "Rising"
    if ratio is not None and ratio <= .6 and expected >= need + 1:
        return "Easing"
    return "Steady"


STATUS_ORDER = {"New": 0, "Rising": 1, "Steady": 2, "Easing": 3}


def _top(counter: Counter, n=6):
    total = sum(counter.values()) or 1
    return [{"name": k, "count": v, "share": round(100 * v / total)} for k, v in counter.most_common(n) if k]


# ====================================================================== Emerging access issues
def access_issues(d: Data) -> list[dict]:
    """One row per issue x entity (payer / pharmacy / office): patients who raised it now vs in the 13 weeks before,
    per call at the same stages (so a growing hub does not make everything look like it is rising). The ratio is
    smoothed (+1) so a handful of patients cannot produce a 10x."""
    groups = defaultdict(list)
    for c in d.scope:
        if c["day"] < d.prior_start:
            continue
        for s in d.sig[c["call_id"]]:
            meta = ISSUES.get(s["issue"])
            if not meta or meta["category"] not in ACCESS_CATEGORIES:
                continue
            eid, name = entity_of(c, meta["entity"])
            groups[(s["issue"], eid, name)].append((c, s))
    cur_stage = Counter(c["journey_stage"] for c in d.recent)
    prior_stage = Counter(c["journey_stage"] for c in d.prior)
    rows = []
    for (iss, eid, name), occ in groups.items():
        meta = ISSUES[iss]
        cur = [(c, s) for c, s in occ if c["day"] >= d.cur_start]
        prev = [(c, s) for c, s in occ if c["day"] < d.cur_start]
        stages = {c["journey_stage"] for c, _ in occ}
        den_cur, den_prev = sum(cur_stage[x] for x in stages), sum(prior_stage[x] for x in stages)
        p_cur = len({c["patient_id"] or c["call_id"] for c, _ in cur})
        # the 13 weeks before, cut into blocks as long as the period: patients counted per block, like the period
        blocks = defaultdict(set)
        for c, _ in prev:
            blocks[(d.cur_start - c["day"]).days // d.cur_days].add(c["patient_id"] or c["call_id"])
        p_prev = sum(len(b) for b in blocks.values())
        expected = p_prev / den_prev * den_cur if den_prev else 0
        ratio = round((p_cur + 1) / (expected + 1), 2) if p_prev else None
        status = _status(p_cur, p_prev, ratio, expected, d.cur_days)
        if meta["category"] == HUB and status in ("New", "Rising") and not (ratio and ratio >= 3 and p_cur >= 8):
            status = "Steady"
        if len(cur) < 2 and status != "Easing":
            continue
        progs = Counter(c["drug"] for c, _ in cur)
        st = Counter(c["journey_stage"] for c, _ in cur).most_common(1)
        rows.append({
            "key": f"{iss}|{eid or 'all'}", "issue": iss, "label": meta["label"], "category": meta["category"],
            "entity_kind": meta["entity"] if eid else None, "entity_id": eid, "entity": name if eid else None,
            "title": f"{name} – {_lower(meta['label'])}" if eid else meta["label"],
            "status": status, "mentions": len(cur), "prior_mentions": len(prev), "ratio": ratio,
            "vs": vs_text(ratio, status), "per_week": round(len(cur) / (d.cur_days / 7), 1),
            "normal_per_week": round(len(prev) / 13, 1), "expected": round(expected, 1),
            "patients": len({c["patient_id"] for c, _ in cur if c["patient_id"]}),
            "programs": [k for k, _ in progs.most_common()], "stage": STAGE_TITLE.get(st[0][0]) if st else None,
            "owner": meta["owner"], "meaning": meta["meaning"], "action": meta["action"],
            "first_heard": min((c["day"] for c, _ in cur), default=None),
            "series": series([c["day"] for c, _ in occ]),
            "score": (ratio or (3 if status == "New" else 1)) * (p_cur ** .5),
            "evidence": [d.ev(c, s["quote"], meta["label"]) for c, s in sorted(cur, key=lambda x: x[0]["call_datetime"], reverse=True)],
        })
    rows.sort(key=lambda r: (STATUS_ORDER[r["status"]], -r["score"] if r["status"] in ("New", "Rising") else -r["mentions"]))
    return rows


def _lower(label):
    return label if label[1:2].isupper() else label[0].lower() + label[1:]


def emerging_top(rows, n=3):
    return [r for r in rows if r["status"] in ("New", "Rising")][:n]


def issues_page(d: Data) -> dict:
    rows = access_issues(d)
    hot = [r for r in rows if r["status"] in ("New", "Rising")]
    weekly = {cat: [0] * WEEKS for cat in ACCESS_CATEGORIES}
    for c in d.scope:
        for s in d.sig[c["call_id"]]:
            meta = ISSUES.get(s["issue"])
            if meta and meta["category"] in ACCESS_CATEGORIES:
                ser = series([c["day"]])
                weekly[meta["category"]] = [a + b for a, b in zip(weekly[meta["category"]], ser)]
    cats = []
    for cat in ACCESS_CATEGORIES:
        rs = [r for r in rows if r["category"] == cat]
        cats.append({"category": cat, "issues": len(rs), "mentions": sum(r["mentions"] for r in rs),
                     "hot": sum(1 for r in rs if r["status"] in ("New", "Rising"))})
    return {
        "window": "this period" if d.f.days else "last 4 weeks", "cur_days": d.cur_days,
        "kpis": {"tracked": len(rows), "new": sum(1 for r in rows if r["status"] == "New"),
                 "rising": sum(1 for r in rows if r["status"] == "Rising"),
                 "patients": len({e["patient_id"] for r in hot for e in r["evidence"] if e.get("patient_id")}),
                 "mentions": sum(r["mentions"] for r in rows),
                 "payers": len({r["entity_id"] for r in hot if r["entity_kind"] == "payer"}),
                 "pharmacies": len({r["entity_id"] for r in hot if r["entity_kind"] == "pharmacy"}),
                 "offices": len({r["entity_id"] for r in hot if r["entity_kind"] == "office"})},
        "categories": cats, "weeks": week_labels(),
        "weekly": [{"week": w, **{cat: weekly[cat][i] for cat in ACCESS_CATEGORIES}} for i, w in enumerate(week_labels())],
        "rows": [cap_evidence(r, ROW_CAP) for r in rows],
    }


def issue_detail(d: Data, key: str) -> dict | None:
    rows = access_issues(d)
    row = next((r for r in rows if r["key"] == key), None)
    if not row:
        return None
    iss, eid = row["issue"], row["entity_id"]
    meta = ISSUES[iss]
    occ = [(c, s) for c in d.scope if c["day"] >= d.cur_start for s in d.sig[c["call_id"]]
           if s["issue"] == iss and (not eid or entity_of(c, meta["entity"])[0] == eid)]
    by_program = Counter(c["drug"] for c, _ in occ)
    by_stage = Counter(STAGE_TITLE.get(c["journey_stage"]) for c, _ in occ)
    by_office = Counter(c["practice_name"] for c, _ in occ)
    by_payer = Counter(c["payer_display"] for c, _ in occ)
    by_pharmacy = Counter(c["sp_name"] for c, _ in occ)
    who = Counter(PARTY_OF_CALL.get(c["other_party_type"], "Other") for c, _ in occ)
    patients = {}
    for c, s in sorted(occ, key=lambda x: x[0]["call_datetime"]):
        if c["patient_id"]:
            patients[c["patient_id"]] = {"patient_id": c["patient_id"], "patient_name": c["patient_name"], "case_id": c["case_id"],
                                         "drug": c["drug"], "stage": STAGE_TITLE.get(c["journey_stage"]), "office": c["practice_name"],
                                         "last_heard": c["day"].isoformat(), "quote": s["quote"],
                                         "calls": patients.get(c["patient_id"], {}).get("calls", 0) + 1}
    unresolved = [c for c, _ in occ if c["live"] and c["resolved_on_call"] is False]
    window = "this week" if d.f.days == 7 else f"last {d.f.days} days" if d.f.days else "last 4 weeks"
    if row["status"] == "New":
        why = f"New: {row['patients']} patients since {row['first_heard']:%b} {row['first_heard'].day}; none in the prior 13 weeks."
    else:
        why = f"{row['patients']} patients {window} vs ~{max(1, round(row['expected']))} normally – {row['vs']}."
    related = [r for r in rows if r["entity_id"] and r["entity_id"] == eid and r["key"] != key][:4]
    return {**row, "why": why, "window": window, "cur_days": d.cur_days,
            "unresolved_pct": pct(len(unresolved), len([c for c, _ in occ if c["live"]])),
            "breakdowns": {"program": _top(by_program), "stage": _top(by_stage), "office": _top(by_office),
                           "payer": _top(by_payer), "pharmacy": _top(by_pharmacy), "who": _top(who)},
            "weeks": week_labels(), "patients_list": sorted(patients.values(), key=lambda p: p["last_heard"], reverse=True)[:10],
            "related": [{k: r[k] for k in ("key", "title", "status", "vs", "mentions", "category")} for r in related]}


# ====================================================================== Patients at risk of dropping off
def at_risk(d: Data, calls=None) -> list[dict]:
    """Patients whose calls (the period's, or the ones given) carry drop-off signals."""
    cat_of = {iss: (key, label, w, nxt) for key, label, issues, w, nxt in RISK_CATEGORIES for iss in issues}
    weights = {key: w for key, _, _, w, _ in RISK_CATEGORIES}
    labels = {key: label for key, label, *_ in RISK_CATEGORIES}
    nexts = {key: nxt for key, _, _, _, nxt in RISK_CATEGORIES}
    r3 = {i["subject_id"]: i for i in d.open_insights if i["rule_id"] == "R3"}
    current = d.current_stage()
    pts = {}
    protect = defaultdict(list)
    for c in (d.calls if calls is None else calls):
        pid = c["patient_id"]
        if not pid:
            continue
        for s in d.sig[c["call_id"]]:
            if s["signal_id"] in ("S30", "S36"):
                protect[pid].append(c["call_datetime"])
            cat = cat_of.get(s["issue"])
            if not cat or (s["issue"] == "frustration" and c["other_party_type"] not in ("patient", "caregiver")):
                continue
            p = pts.setdefault(pid, {"cats": Counter(), "evidence": [], "first": c["day"], "last": c, "quote": None})
            p["cats"][cat[0]] += 1
            p["evidence"].append(d.ev(c, s["quote"], labels[cat[0]]))
            p["first"] = min(p["first"], c["day"])
            if c["call_datetime"] >= p["last"]["call_datetime"]:
                p["last"], p["quote"] = c, s["quote"] or p["quote"]
    first_ever = {}
    for pid in pts:
        for c in d.patient_calls.get(pid, []):
            if any(s["issue"] in cat_of for s in d.sig[c["call_id"]]):
                first_ever[pid] = c["day"]
                break
    out = []
    for pid, p in pts.items():
        cats = sorted(p["cats"], key=lambda k: -weights[k])
        mentions = sum(p["cats"].values())
        score = sum(weights[k] for k in cats) + .5 * min(2, mentions - len(cats))
        if any(t > p["last"]["call_datetime"] for t in protect[pid]):
            score -= 1  # support offered or relief heard after the last worry
        if pid in r3 and r3[pid]["band"] == "high":
            score = max(score, 3.5)
        level = "High" if score >= 3 else "Medium" if score >= 1.5 else "Low"
        last = p["last"]
        stage = current.get(pid)
        out.append({"patient_id": pid, "patient_name": last["patient_name"], "case_id": last["case_id"], "drug": last["drug"],
                    "program_id": last["program_id"], "stage": stage, "stage_title": STAGE_TITLE.get(stage, stage),
                    "phase": "On therapy" if stage in ON_THERAPY else "Before first shipment", "level": level,
                    "score": round(score, 1), "categories": [labels[k] for k in cats], "category_keys": cats, "mentions": mentions,
                    "first_heard": first_ever.get(pid, p["first"]).isoformat(),
                    "new_this_week": first_ever.get(pid, p["first"]) >= AS_OF - timedelta(days=6),
                    "last_heard_days": (AS_OF - last["day"]).days, "last_contact_days": (AS_OF - d.all_calls_last(pid)).days,
                    "quote": p["quote"], "payer": last["payer_display"], "pharmacy": last["sp_name"], "office": last["practice_name"],
                    "next_step": nexts[cats[0]], "owner": OWNER_OF_RISK.get(cats[0], "Patient Services"),
                    "recorded": not last["mock"], "evidence": p["evidence"]})
    order = {"High": 0, "Medium": 1, "Low": 2}
    out.sort(key=lambda p: (order[p["level"]], -p["score"], p["last_heard_days"]))
    return out


OWNER_OF_RISK = {"cost": "Patient Services", "think": "Nurse educator", "pharmacy": "Trade / pharmacy lead",
                 "side_effects": "Nurse educator", "stopping": "Nurse educator", "missed": "Nurse educator",
                 "logistics": "Patient Services", "declined": "Case manager", "application": "Patient Services",
                 "frustrated": "Case manager"}
RISK_OF_ISSUE = {iss: (key, label, w) for key, label, issues, w, _ in RISK_CATEGORIES for iss in issues}


def patient_risk(d: Data, patient_id) -> dict | None:
    """The same drop-off view as the at-risk tab, over all of one patient's calls."""
    rows = at_risk(d, d.patient_calls.get(patient_id, []))
    return rows[0] if rows else None


def risk_page(d: Data) -> dict:
    pts = at_risk(d)
    flagged = [p for p in pts if p["level"] in ("High", "Medium")]
    # the same patients one period earlier, for "vs before" on each category
    prev_ids = defaultdict(set)
    cat_of = {iss: key for key, _, issues, _, _ in RISK_CATEGORIES for iss in issues}
    lo = d.cur_start - timedelta(days=d.cur_days)
    for c in d.scope:
        if lo <= c["day"] < d.cur_start and c["patient_id"]:
            for s in d.sig[c["call_id"]]:
                if s["issue"] in cat_of:
                    prev_ids[cat_of[s["issue"]]].add(c["patient_id"])
    cats = []
    for key, label, _, _, nxt in RISK_CATEGORIES:
        who = [p for p in pts if key in p["category_keys"]]
        if not who:
            continue
        cats.append({"key": key, "label": label, "patients": len(who),
                     "flagged": sum(1 for p in who if p["level"] != "Low"), "before": len(prev_ids[key]), "next_step": nxt,
                     "evidence": [e for p in who for e in p["evidence"] if e["label"] == label]})
    cats.sort(key=lambda c: -c["flagged"])
    by_stage = Counter(p["stage_title"] for p in flagged)
    return {
        "kpis": {"flagged": len(flagged), "high": sum(1 for p in flagged if p["level"] == "High"),
                 "new_this_week": sum(1 for p in flagged if p["new_this_week"]),
                 "on_therapy": sum(1 for p in flagged if p["phase"] == "On therapy"),
                 "before_start": sum(1 for p in flagged if p["phase"] != "On therapy"), "heard": len(pts)},
        "categories": cats,
        "by_stage": [{"name": STAGE_TITLE[s], "count": by_stage.get(STAGE_TITLE[s], 0)} for s in STAGE_ORDER],
        "by_program": _top(Counter(p["drug"] for p in flagged)),
        "by_payer": _top(Counter(p["payer"] for p in flagged), 7),
        "patients": [cap_evidence(p, ROW_CAP) for p in pts],
    }


# ====================================================================== Call summary (why patients and offices called)
PARTY_GROUP = {"patient": "Patients & caregivers", "caregiver": "Patients & caregivers", "voicemail": "Patients & caregivers",
               "provider_office": "Offices", "payer": "Payers", "specialty_pharmacy": "Pharmacies"}
ENTITY_BY_REASON = {"Prescription / shipment status": "pharmacy", "Prior authorization": "payer", "Benefits & coverage": "payer",
                    "Affordability / copay": "payer", "Enrollment": "office", "Therapy start & education": "program",
                    "Side effects / dosing": "program", "Other": "program"}
ENTITY_LABEL = {"pharmacy": "Specialty pharmacy", "payer": "Payer", "office": "Physician office", "program": "Program"}


def _entity_name(c, kind):
    return c["drug"] if kind == "program" else entity_of(c, kind)[1]


def call_summary(d: Data, direction: str | None = None, party: str | None = None) -> dict:
    def keep(c):
        return ((not direction or (c["direction"] or "").lower() == direction)
                and (not party or PARTY_GROUP.get(c["other_party_type"]) == party))

    calls = [c for c in d.calls if keep(c)]
    prior = [c for c in d.prior if keep(c)]
    scope = [c for c in d.scope if keep(c)]
    total = len(calls)
    reasons = []
    for r in CONTACT_REASONS:
        cs = [c for c in calls if c["contact_reason"] == r]
        if not cs:
            continue
        ps = [c for c in prior if c["contact_reason"] == r]
        share, normal = pct(len(cs), total), pct(len(ps), len(prior)) if len(prior) >= 50 else d.baseline["contact_reason_share"].get(r)
        live = [c for c in cs if c["live"] and c["resolved_on_call"] is not None]
        kind = ENTITY_BY_REASON[r]
        ent, ent_prev = Counter(_entity_name(c, kind) for c in cs), Counter(_entity_name(c, kind) for c in ps)
        ent_fcr = defaultdict(list)
        for c in live:
            ent_fcr[_entity_name(c, kind)].append(c["resolved_on_call"])
        entities = []
        for name, n in ent.most_common(8):
            if not name:
                continue
            sh = n / len(cs)
            prev = ent_prev.get(name, 0) / len(ps) if ps else None
            ratio = round(sh / prev, 2) if prev else None
            shown = n >= 20 or (prev == 0 and n >= 5)  # small groups swing too much to compare
            entities.append({"name": name, "calls": n, "share": round(100 * sh), "ratio": ratio if shown else None,
                             "vs": vs_text(ratio, "New" if prev == 0 else "") if shown else "–",
                             "fcr": pct(sum(ent_fcr[name]), len(ent_fcr[name]))})
        subs = Counter(c["sub_reason"] for c in cs)
        sub_live = defaultdict(list)
        for c in live:
            sub_live[c["sub_reason"]].append(c["resolved_on_call"])
        issues = Counter(ISSUES[s["issue"]]["label"] for c in cs for s in d.sig[c["call_id"]]
                         if s["issue"] in ISSUES and ISSUES[s["issue"]]["category"] != HUB)
        samples = []
        for c in cs:
            q = next((s["quote"] for s in d.sig[c["call_id"]] if s["issue"] in ISSUES and ISSUES[s["issue"]]["category"] != HUB
                      and s["quote"] and len(s["quote"]) >= 30), None)
            samples.append((q is None, c["mock"], -c["call_datetime"].timestamp(), d.ev(c, q or c["resolution_note"], c["sub_reason"])))
        samples = [e for *_, e in sorted(samples, key=lambda x: x[:3])]
        reasons.append({
            "reason": r, "calls": len(cs), "share": share or 0, "normal": normal,
            "delta": (share - normal) if share is not None and normal is not None else None,
            "inbound": pct(sum(1 for c in cs if (c["direction"] or "").lower() == "inbound"), len(cs)),
            "fcr": pct(sum(1 for c in live if c["resolved_on_call"]), len(live)),
            "repeat": d.repeat_pct(cs)[0],
            "minutes": round(sum(float(c["audio_duration_s"] or 0) for c in cs if c["live"]) / max(1, sum(1 for c in cs if c["live"])) / 60, 1),
            "series": series([c["day"] for c in scope if c["contact_reason"] == r]),
            "subs": [{"name": k, "calls": v, "share": round(100 * v / len(cs)),
                      "fcr": pct(sum(sub_live[k]), len(sub_live[k]))} for k, v in subs.most_common(8)],
            "entity_kind": kind, "entity_label": ENTITY_LABEL[kind], "entities": entities,
            "issues": [{"name": k, "count": v} for k, v in issues.most_common(5)],
            "evidence": samples,
        })
    reasons.sort(key=lambda x: (x["reason"] == "Other", -x["calls"]))
    live = [c for c in calls if c["live"] and c["resolved_on_call"] is not None]
    prev_n = None
    if d.f.days:
        lo = d.cur_start - timedelta(days=d.cur_days)
        prev_n = sum(1 for c in scope if lo <= c["day"] < d.cur_start)
    fcr, fcr_normal = pct(sum(1 for c in live if c["resolved_on_call"]), len(live)), d.baseline["fcr"].get("all")
    rep = d.repeat_pct(calls)[0]
    return {
        "kpis": {"calls": total, "previous": prev_n, "change_pct": pct(total - prev_n, prev_n) if prev_n else None,
                 "inbound": pct(sum(1 for c in calls if (c["direction"] or "").lower() == "inbound"), total),
                 "fcr": fcr, "fcr_normal": fcr_normal, "fcr_target": d.baseline["fcr_target"].get("all"),
                 "repeat": rep, "repeat_normal": d.baseline["repeat_7d"].get("all"),
                 "minutes": round(sum(float(c["audio_duration_s"] or 0) for c in calls if c["live"]) / max(1, sum(1 for c in calls if c["live"])) / 60, 1),
                 "patients": len({c["patient_id"] for c in calls if c["patient_id"]})},
        "weeks": week_labels(), "series": series([c["day"] for c in scope]),
        "parties": [{"name": k, "calls": v} for k, v in Counter(PARTY_GROUP.get(c["other_party_type"], "Other") for c in calls).most_common()],
        "reasons": reasons,
    }


# ====================================================================== Where patients get stuck
def stuck(d: Data) -> dict:
    items = d.friction()
    # Everything on the page comes from the period's calls: per stage, the patients called about it and how long
    # they have been in it (from all their calls), so the numbers add up to the calls in the period.
    pids = {c["patient_id"] for c in d.calls if c["patient_id"]}
    spans = d.stage_spans(pids)
    all_live = [c for c in d.calls if c["live"] and c["resolved_on_call"] is not None]
    overall_open = pct(sum(1 for c in all_live if not c["resolved_on_call"]), len(all_live)) or 0
    overall_rate = len(items) / max(1, len(d.calls))
    stages = []
    for st in STAGE_ORDER:
        cs = [c for c in d.calls if c["journey_stage"] == st]
        called = {c["patient_id"] for c in cs if c["patient_id"]}
        here = [(pid, spans[pid][-1]) for pid in called if spans.get(pid) and spans[pid][-1]["stage"] == st]  # still in it
        passed = [sp for s in spans.values() for sp in s if sp["stage"] == st and sp["end"] is not None]
        ongoing = st == "Adherence & refill"
        waiting = [] if ongoing else [(pid, sp) for pid, sp in here if d.span_days(sp) > WAIT_DAYS]
        live = [c for c in cs if c["live"] and c["resolved_on_call"] is not None]
        st_items = [i for i in items if i["stage"] == st]
        heard = Counter()
        ev_by = defaultdict(list)
        for c in cs:
            for s in d.sig[c["call_id"]]:
                meta = ISSUES.get(s["issue"])
                if meta and meta["category"] != HUB:
                    heard[meta["label"]] += 1
                    ev_by[meta["label"]].append(d.ev(c, s["quote"], meta["label"]))
        n_heard = sum(heard.values()) or 1
        ents = Counter((i["with"], i["entity"]) for i in st_items if i["with"] in ("Physician office", "Payer", "Specialty pharmacy"))
        stages.append({
            "stage": st, "title": STAGE_TITLE[st], "short": STAGE_SHORT[st], "slug": STAGE_SLUG[st], "ongoing": ongoing,
            "patients": len(called), "waiting": len(waiting),
            "longest_days": max((d.span_days(sp) for _, sp in here), default=None) if not ongoing else None,
            "avg_days": round(sum(d.span_days(sp) for sp in passed) / len(passed)) if passed else None,
            "calls": len(cs), "friction": len(st_items), "friction_rate": round(len(st_items) / len(cs), 2) if cs else 0,
            "unresolved": pct(sum(1 for c in live if not c["resolved_on_call"]), len(live)),
            "repeat": d.repeat_pct(cs)[0],
            "reasons": [{"name": k, "count": v, "share": round(100 * v / n_heard),
                         "evidence": cap_evidence({"evidence": ev_by[k]}, ROW_CAP)["evidence"]} for k, v in heard.most_common(6)],
            "parties": _top(Counter(i["with"] for i in st_items), 5),
            "entities": [{"kind": w, "name": n, "count": v} for (w, n), v in ents.most_common(6)],
            "evidence_waiting": [d.ev(sp["calls"][-1], sp["calls"][-1]["resolution_note"], f"In {STAGE_TITLE[st].lower()} for {d.span_days(sp)} days")
                                 for _, sp in sorted(waiting, key=lambda x: -d.span_days(x[1]))],
            "evidence": [e for v in ev_by.values() for e in v],
        })
    slow = max((s for s in stages if s["waiting"]), key=lambda s: (s["waiting"], s["friction"]), default=None)
    for s in stages:
        busy = s["patients"] >= 3 and s["waiting"] / max(1, s["patients"]) >= .25
        noisy = s["calls"] >= 5 and (s["friction_rate"] >= 1.25 * overall_rate or (s["unresolved"] or 0) >= overall_open + 10)
        s["status"] = ("none" if not s["calls"] and not s["patients"] else "red" if s is slow
                       else "amber" if busy or noisy else "green")
    heat_types = sorted({i["type"] for i in items})
    heat = [{"stage": STAGE_TITLE[st], "cells": [{"type": t, "count": sum(1 for i in items if i["stage"] == st and i["type"] == t)}
                                                  for t in heat_types]} for st in STAGE_ORDER]
    return {"stages": stages, "slowest": slow and slow["stage"], "wait_days": WAIT_DAYS, "heat_types": heat_types, "heat": heat,
            "heat_max": max([c["count"] for r in heat for c in r["cells"]] + [1]),
            "overall": {"friction_rate": round(overall_rate, 2), "unresolved": overall_open}}
