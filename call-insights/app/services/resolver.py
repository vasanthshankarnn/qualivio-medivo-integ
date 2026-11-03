"""Deterministic label resolution: names heard on the call -> master-data IDs (no AI here).

Order of evidence per label: the case record (patient found by the case id from the phone system, else by name +
date of birth heard on the call) > what was heard on the call, matched against names and aliases. A label taken from
the call, or a call that names something different from the record, is flagged for a person to check.
"""
import re
import uuid
from datetime import date
from difflib import SequenceMatcher

from app.db import fetch_all, get_conn
from app.logger import logger

_STOP = {"the", "doctor", "dr", "of", "and", "s"}


def _norm(text: str | None) -> str:
    text = (text or "").lower().replace("&", " and ").replace("'", "")
    words = re.sub(r"[^a-z0-9 ]+", " ", text).split()
    return " ".join(w for w in words if w not in _STOP)


def _candidates(row: dict, name_key: str) -> list[str]:
    names = [row[name_key]] + [a for a in (row.get("aliases") or "").split("|") if a.strip()]
    return [n for n in (_norm(x) for x in names) if n]


# Words that may surround a known name without changing who it is ("insurance summit" is still Summit).
_FILLER = {"insurance", "health", "plan", "healthcare", "company", "office", "clinic", "practice", "medical", "group"}


def _contains(h: str, cand: str) -> bool:
    """Heard text is a shorter form of the known name, or the known name plus filler words only.
    'Summit Crest Health Plan' is not 'Summit': 'crest' is a distinguishing word, not filler."""
    if h in cand.split() or f" {h} " in f" {cand} ":
        return True
    if f" {cand} " in f" {h} ":
        return set(f" {h} ".replace(f" {cand} ", " ").split()) <= _FILLER
    return False


def _match(heard: str | None, rows: list[dict], id_key: str, name_key: str):
    h = _norm(heard)
    if not h:
        return None, "none", 0.0
    best = (None, "none", 0.0)
    for row in rows:
        for cand in _candidates(row, name_key):
            if h == cand:
                return row[id_key], "exact", 1.0
            if len(cand) >= 4 and _contains(h, cand):
                best = max(best, (row[id_key], "alias", 0.9), key=lambda b: b[2])
            elif len(h.split()) == len(cand.split()):  # fuzzy = a mis-heard name, not one with extra words
                ratio = SequenceMatcher(None, h, cand).ratio()
                if ratio >= 0.8:
                    best = max(best, (row[id_key], "fuzzy", round(ratio, 2)), key=lambda b: b[2])
    return best


def resolve(extraction, metadata: dict) -> tuple[dict, list[dict]]:
    """Return (labels for ci_calls, entity rows for ci_call_entities)."""
    patients = fetch_all("SELECT * FROM ci_patients")
    practices = fetch_all("SELECT * FROM ci_practices")
    prescribers = fetch_all("SELECT * FROM ci_prescribers")
    payers = fetch_all("SELECT * FROM ci_payers WHERE payer_name NOT LIKE '(%%'")
    programs = fetch_all("SELECT * FROM ci_programs")
    ent = extraction.entities
    rows, labels = [], {}
    drug_programs = [{**p, "aliases": f"{p['drug']}|{p.get('aliases') or ''}"} for p in programs]

    # 1. Patient: case id from the phone system first, else name + date of birth heard on the call.
    heard_name = ent.patient.name if ent.patient else None
    heard_dob = _iso_date(ent.patient.date_of_birth if ent.patient else None)
    patient = None
    if metadata.get("case_id"):
        patient = next((p for p in patients if p["case_id"] == str(metadata["case_id"])), None)
        method, conf = ("metadata", 1.0) if patient else ("none", 0.0)
        if patient and heard_name and _norm(heard_name) and _norm(patient["patient_name"]) not in _norm(heard_name)                 and _norm(heard_name) not in _norm(patient["patient_name"]):
            method, conf = "metadata_name_mismatch", 0.5
    else:
        by_name = [p for p in patients if heard_name and _norm(p["patient_name"]) == _norm(heard_name)]
        by_dob = [p for p in by_name if heard_dob and str(p["dob"]) == heard_dob]
        patient = (by_dob or by_name or [None])[0]
        method, conf = ("name+dob", 0.95) if by_dob else (("name", 0.7) if len(by_name) == 1 else ("none", 0.0))

    # 2. Each label: the case record wins. What the AI heard on the call is used only when the record has nothing
    #    (no case id, or the field is still empty) and is then flagged for a person to check; if the call names
    #    something different from the record, the record is kept and the difference is flagged.
    found = {}
    for kind, heard, table, id_key, name_key in (
            ("practice", ent.practice, practices, "practice_id", "practice_name"),
            ("payer", ent.payer, payers, "payer_id", "payer_name"),
            ("program", ent.drug, drug_programs, "program_id", "program_name"),
            ("prescriber", ent.prescriber, prescribers, "prescriber_id", "prescriber_name")):
        on_record = patient.get(id_key) if patient else None
        if on_record and str(on_record).endswith("99"):  # placeholder such as "payer not stated"
            on_record = None
        rid, how, score = _match(heard, table, id_key, name_key)
        if on_record:
            # A different known name on the call is a mismatch to check; an unknown one (often a mis-hearing,
            # e.g. "Harvo" for Iqirvo) is only noted. Either way the record is kept.
            m = ("case_record_mismatch" if rid and rid != on_record
                 else "case_record_unrecognised" if rid is None and _registrable(heard) else "case_record")
            found[kind] = [on_record, m, 1.0, heard]
        elif rid:
            found[kind] = [rid, f"from_call_{how}", score, heard]
        elif kind != "program" and _registrable(heard):  # programs are Ipsen's fixed list: never auto-registered
            practice_id = found["practice"][0] if "practice" in found else None  # a prescriber belongs to a practice
            found[kind] = [_register(kind, heard, practice_id=practice_id), "auto_registered", 0.6, heard]
        else:
            found[kind] = [None, "none", 0.0, heard]

    ids = {k: v[0] for k, v in found.items()}
    if patient is None and (metadata.get("case_id") or _registrable(heard_name)):
        patient = _register_patient(metadata.get("case_id"), heard_name, heard_dob, ids)
        method, conf = "auto_registered", 0.6
    elif patient:
        patient = _fill_patient_gaps(patient, ids)
    labels["patient_id"] = patient["patient_id"] if patient else None
    rows.append({"entity_type": "patient", "heard_text": " / ".join(x for x in (heard_name, heard_dob) if x) or None,
                 "resolved_id": labels["patient_id"], "match_method": method, "confidence": conf})
    for kind in ("practice", "prescriber", "payer", "program"):
        rid, m, c, heard = found[kind]
        labels[f"{kind}_id"] = rid
        rows.append({"entity_type": kind, "heard_text": heard, "resolved_id": rid, "match_method": m, "confidence": c})
    if ent.office_contact:
        rows.append({"entity_type": "office_contact", "heard_text": ent.office_contact, "resolved_id": None,
                     "match_method": "heard_only", "confidence": None})
    return labels, rows


# ---------------------------------------------------------------- auto-registration of new master data
_GENERIC = {"insurance", "plan", "health plan", "insurance company", "office", "clinic", "practice", "pharmacy",
            "specialty pharmacy", "unknown", "patient", "doctor", "physician", "provider", "payer"}
_PREFIX = {"practice": "PR", "payer": "PY", "prescriber": "DR", "patient": "PAT"}
_TABLE = {"practice": ("ci_practices", "practice_id", "practice_name"),
          "payer": ("ci_payers", "payer_id", "payer_name"),
          "prescriber": ("ci_prescribers", "prescriber_id", "prescriber_name")}


def _registrable(heard: str | None) -> bool:
    n = _norm(heard)
    return len(n) >= 3 and n not in _GENERIC and not n.startswith("unnamed")


def _iso_date(value: str | None) -> str | None:
    try:
        return date.fromisoformat(value).isoformat() if value else None
    except ValueError:
        return None


def _new_id(kind: str) -> str:
    return f"{_PREFIX[kind]}-{uuid.uuid4().hex[:6].upper()}"


def _register(kind: str, heard: str, practice_id: str | None = None) -> str:
    table, id_key, name_key = _TABLE[kind]
    new_id = _new_id(kind)
    cols = {id_key: new_id, name_key: heard.strip(), "source": "auto-registered from a call"}
    if kind == "prescriber":
        cols["practice_id"] = practice_id
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", list(cols.values()))
    logger.info("Registered new %s %s (%s)", kind, new_id, heard)
    return new_id


def _register_patient(case_id, name, dob, ids: dict) -> dict:
    row = {"patient_id": f"PAT-{case_id}" if case_id else _new_id("patient"), "case_id": str(case_id) if case_id else None,
           "patient_name": (name or f"Unknown patient (case {case_id})").strip(), "dob": dob,
           "program_id": ids.get("program"), "practice_id": ids.get("practice"), "prescriber_id": ids.get("prescriber"),
           "payer_id": ids.get("payer"), "source": "auto-registered from a call"}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""INSERT INTO ci_patients ({', '.join(row)}) VALUES ({', '.join(['%s'] * len(row))})
                        ON CONFLICT (patient_id) DO NOTHING""", list(row.values()))
    logger.info("Registered new patient %s", row["patient_id"])
    return row


def _fill_patient_gaps(patient: dict, ids: dict) -> dict:
    """A later call can tell us what an earlier one did not (e.g. the payer); fill only empty / placeholder fields."""
    updates = {f"{k}_id": v for k, v in ids.items()
               if v and (not patient.get(f"{k}_id") or str(patient.get(f"{k}_id")).endswith("99"))}
    if not updates:
        return patient
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE ci_patients SET {', '.join(f'{k} = %s' for k in updates)} WHERE patient_id = %s",
                    [*updates.values(), patient["patient_id"]])
    return {**patient, **updates}


# ---------------------------------------------------------------- hub agent from the call (when the phone system gave none)
_STAFF_ROLES = {"hub_staff": ("Hub staff", "Hub"), "nurse_educator": ("Nurse educator", "Hub"),
                "specialty_pharmacy": ("Specialty pharmacy intake", "Specialty pharmacy")}


def resolve_staff(extraction) -> str | None:
    """Hub-side speaker's name heard on the call -> ci_staff id (registered if new). None if no name was said."""
    speaker = next((s for s in extraction.speakers if s.role in _STAFF_ROLES and _registrable(s.name)), None)
    if not speaker:
        return None
    first = _norm(speaker.name).split()[0]
    match = next((s for s in fetch_all("SELECT * FROM ci_staff") if _norm(s["staff_name"]).split()[:1] == [first]), None)
    if match:
        return match["staff_id"]
    role, org = _STAFF_ROLES[speaker.role]
    staff_id = f"ST-{uuid.uuid4().hex[:6].upper()}"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO ci_staff (staff_id, staff_name, role, organisation) VALUES (%s, %s, %s, %s)",
                    (staff_id, speaker.name.strip(), role, org))
    logger.info("Registered new hub agent %s (%s)", staff_id, speaker.name)
    return staff_id
