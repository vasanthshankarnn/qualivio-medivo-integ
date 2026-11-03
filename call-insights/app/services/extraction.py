"""Per-call AI extraction: signals, promises, documents, names heard, stage and sentiment (one Gemini call).

The model only sees the conversation plus what a phone system would send (date, direction, agent, case id).
Names it hears are returned as text; mapping them to master-data IDs is deterministic (see resolver.py).
"""
import json
from typing import Optional

from pydantic import BaseModel, Field

from app.config import GEMINI_MODEL_EXTRACT, GEMINI_THINKING_EXTRACT
from app.logger import logger
from app.services.gemini import build_config, get_client

STAGES = ["Enrollment", "Benefits verification", "Prior authorization & appeal", "Copay & assistance",
          "Specialty pharmacy & first fill", "Nurse education", "Adherence & refill", "Unknown"]
PARTY_TYPES = ["patient", "caregiver", "provider_office", "payer", "specialty_pharmacy", "voicemail", "unknown"]
CONTACT_REASONS = ["Enrollment", "Benefits & coverage", "Prior authorization", "Affordability / copay",
                   "Prescription / shipment status", "Therapy start & education", "Side effects / dosing", "Other"]
MEDICAL_TOPICS = ["Drug interactions", "Dosing & food", "Missed dose", "Storage & travel", "Pregnancy",
                  "Side effects", "Use outside the label", "Other"]


class Speaker(BaseModel):
    label: str = Field(description="Speaker label exactly as it appears in the transcript")
    role: str = Field(description="hub_staff | nurse_educator | specialty_pharmacy | patient | caregiver | provider_office | payer | voicemail_greeting | other")
    name: Optional[str] = None


class PatientMention(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = Field(default=None, description="YYYY-MM-DD if stated on the call")


class Entities(BaseModel):
    patient: Optional[PatientMention] = None
    practice: Optional[str] = Field(default=None, description="Provider office / practice name as heard")
    prescriber: Optional[str] = Field(default=None, description="Prescribing doctor as heard, e.g. 'Doctor Patel'")
    payer: Optional[str] = Field(default=None, description="Insurance company / health plan as heard")
    drug: Optional[str] = None
    office_contact: Optional[str] = Field(default=None, description="Name of the person at the office, if any")


class SignalHit(BaseModel):
    signal_id: str = Field(description="Signal ID from the library, e.g. S06")
    quote: str = Field(description="Verbatim words from the transcript that show the signal (short)")
    timestamp: Optional[str] = Field(default=None, description="mm:ss of the quoted line")
    speaker_role: str
    confidence: float = Field(description="0 to 1")


class Promise(BaseModel):
    made_by_role: str = Field(description="hub_staff | provider_office | patient | other")
    action: str
    due_text: Optional[str] = Field(default=None, description="When, as said: 'Monday afternoon', 'by Thursday March 4'")
    due_date: Optional[str] = Field(default=None, description="YYYY-MM-DD resolved against the call date, if possible")
    quote: str
    timestamp: Optional[str] = None


class Documents(BaseModel):
    payer_required: list[str] = Field(default_factory=list, description="Documents the payer requires, as stated on this call")
    requested_from_office: list[str] = Field(default_factory=list, description="Documents the hub asked the office for, worded as the hub said them")
    missing_items: list[str] = Field(default_factory=list, description="Items said to be missing or incomplete")
    confirmed_sent: list[str] = Field(default_factory=list, description="Items confirmed as sent or received")


class Handoff(BaseModel):
    to: str = Field(description="Team or party the case / caller is handed to, e.g. 'specialty pharmacy', 'nurse educator'")
    confirmed: bool = Field(description="True if it was a warm transfer or the receiving side / next step was explicitly confirmed")
    quote: str


class TimeBlock(BaseModel):
    kind: str = Field(description="hold | transfer")
    start: str = Field(description="mm:ss when the hold / transfer starts")
    end: Optional[str] = Field(default=None, description="mm:ss when the conversation resumes")


class MedicalQuestion(BaseModel):
    topic: str
    question: str = Field(description="The question in the asker's words (short)")
    asked_by: str = Field(description="patient | caregiver | provider_office | other")
    timestamp: Optional[str] = None
    hub_answered_medically: bool = Field(description="True if hub staff gave medical advice themselves")
    referred: bool = Field(description="True if hub staff referred it to Medical Information, the doctor or the nurse")


class SafetyMention(BaseModel):
    kind: str = Field(description="adverse_event | quality_complaint")
    mention: str = Field(description="Plain short description, e.g. 'Itching since starting'")
    quote: str
    timestamp: Optional[str] = None
    acknowledged: bool = Field(description="True if hub staff acknowledged it and said it would be passed on / reported")


class CallExtraction(BaseModel):
    summary: str = Field(description="2-3 sentences: who called whom, why, what was agreed")
    other_party_type: str
    journey_stage: str
    contact_reason: str = Field(description="Main reason this conversation happened")
    resolved_on_call: bool = Field(description="True only if the need behind the call was completed on this call")
    resolution_note: str = Field(description="One short line: what was resolved, or what is still outstanding")
    speakers: list[Speaker]
    entities: Entities
    identity_verified: bool
    identity_quote: Optional[str] = None
    signals: list[SignalHit]
    promises: list[Promise]
    documents: Documents
    handoffs: list[Handoff] = Field(default_factory=list)
    hold_or_transfer: list[TimeBlock] = Field(default_factory=list)
    medical_questions: list[MedicalQuestion] = Field(default_factory=list)
    safety_mentions: list[SafetyMention] = Field(default_factory=list)
    other_party_sentiment: str = Field(description="positive | neutral | negative | mixed")
    sentiment_reason: str


SYSTEM_PROMPT = f"""You analyse recorded phone calls of a rare-disease patient support hub (Iqirvo, Bylvay).
Calls are between hub staff (access specialists, case managers, nurse educators, specialty pharmacy intake)
and patients, caregivers, provider (doctor's) offices or payers.

Rules:
- Use only what is said in this call. Never invent facts. If something is not said, leave it empty.
- Signals: report a library signal only when this call contains direct evidence. Quote the exact words
  (short) and give the mm:ss timestamp of that line. The same signal may appear once per distinct piece of evidence.
  Keywords in the library are hints, not requirements: match on meaning.
- Call-close signals (S19-S22) describe how the hub staff member ended the call.
- S37 / identity_verified: true if the patient was identified by name AND date of birth (asked for or stated, by
  either side) before case details were discussed on this call. The usual form is the hub saying "I'm calling about
  <name>, date of birth <date>"; that counts. A date of birth that was mis-transcribed but clearly given still counts.
- S07: this call is a repeat or follow-up contact about an item that is still open - e.g. the hub says it is
  "following up on" something, "calling again", or refers to an earlier request that is still outstanding
  ("we asked for ... two weeks ago").
- S38: someone refers to the same kind of problem across several patients of the same office.
- S30 (support offer) and S36 (positive resolution) are protective signals; report them too.
- Promises: every commitment with a time reference, by either side. Resolve due_date against the call date.
- other_party_type is one of: {", ".join(PARTY_TYPES)}.
- journey_stage is one of: {", ".join(STAGES)}.
- contact_reason is the main reason this conversation happened (for outbound calls: why the hub called), one of:
  {", ".join(CONTACT_REASONS)}.
- resolved_on_call (first-contact resolution): true if the purpose of this call was achieved on this call - the
  question was answered, or the request was accepted with a clear next step, an owner and a date, so nobody needs to
  contact anyone again about the same item. False if the right person was not reached (voicemail, no answer), the
  question was not answered, the call ended without a clear next step, or the hub must call back about the same item.
- handoffs: each time the case or caller is passed to another team or party (transfer, referral to specialty
  pharmacy, nurse, payer, Medical Information, safety team). confirmed = warm transfer or explicitly confirmed.
- hold_or_transfer: each period a party is put on hold or transferred, with the mm:ss where it starts and where
  the conversation resumes.
- medical_questions: questions about the medicine itself (interactions, dosing and food, missed dose, storage and
  travel, pregnancy, side effects, use outside the label such as other ages or conditions). topic is one of:
  {", ".join(MEDICAL_TOPICS)}. Access, cost or paperwork questions are not medical questions.
- safety_mentions: any possible adverse event (a symptom, side effect or change in health mentioned by or about a
  patient on therapy, even if nobody links it to the medicine) and any product quality complaint (damaged
  packaging, wrong product, temperature problem). Report them even if minor.
Return JSON only, matching the schema."""


def _library_text(signals: list[dict]) -> str:
    lines = []
    for s in signals:
        if s["rule_based"]:
            continue  # cross-call rules (e.g. S16) are computed later from several calls, not per call
        lines.append(f"{s['signal_id']} | {s['signal_name']} | {s['insight_type']} | means: {s['meaning']} | "
                     f"said by: {s['who_says']} | hints: {s['keywords']} | example: {s['example_line']}")
    return "\n".join(lines)


def _fmt_ts(seconds) -> str:
    s = int(float(seconds or 0))
    return f"{s // 60:02d}:{s % 60:02d}"


def transcript_text(segments: list[dict]) -> str:
    return "\n".join(f"[{_fmt_ts(s['start_s'])}] {s['speaker_label']}: {s['text']}" for s in segments)


def extract(segments: list[dict], call_context: dict, signals: list[dict]) -> tuple[CallExtraction, dict]:
    context = "\n".join(f"- {k}: {v}" for k, v in call_context.items() if v not in (None, ""))
    user = (f"CALL DETAILS FROM THE PHONE SYSTEM\n{context}\n\n"
            f"SIGNAL LIBRARY (id | name | insight type | meaning | said by | hints | example)\n{_library_text(signals)}\n\n"
            f"TRANSCRIPT\n{transcript_text(segments)}")
    client = get_client()
    cfg = build_config(GEMINI_MODEL_EXTRACT, thinking_level=GEMINI_THINKING_EXTRACT, temperature=0.2,
                       system_instruction=SYSTEM_PROMPT, response_mime_type="application/json",
                       response_schema=CallExtraction)
    last_error = None
    for attempt in (1, 2):
        try:
            resp = client.models.generate_content(model=GEMINI_MODEL_EXTRACT, contents=user, config=cfg)
            result = CallExtraction.model_validate(json.loads(resp.text))
            usage = getattr(resp, "usage_metadata", None)
            meta = {"model": GEMINI_MODEL_EXTRACT,
                    "prompt_tokens": getattr(usage, "prompt_token_count", None),
                    "output_tokens": getattr(usage, "candidates_token_count", None)}
            return result, meta
        except Exception as e:  # malformed JSON or transient API error: retry once
            last_error = e
            logger.warning("Extraction attempt %s failed: %s", attempt, e)
    raise RuntimeError(f"Extraction failed: {last_error}")
