"""Demo volume: a simulated hub population that sits next to the recorded demo calls.

The recorded calls are real pipeline output, but there are only a handful of them – too few for trends, filters and
"vs normal". This module simulates five months of hub conversations for three programs so every screen looks like a
running hub: patients move through the journey, hit friction (missing paperwork, payer rules, cost, shipments), call
the hub, and some of those patterns grow into emerging issues in the last few weeks.

* Deterministic (fixed seed): the same numbers on every restart.
* In memory only: nothing is written to the database. Switch it off with CI_DEMO_VOLUME=0.
* Every simulated row carries mock=True. Simulated conversations have no recording, so the evidence drawer shows
  their excerpt without an "Open call" button.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable

from app.rules import AS_OF

ENABLED = os.getenv("CI_DEMO_VOLUME", "1").strip().lower() not in ("0", "false", "no", "off")
DST_FROM = date(2027, 3, 14)  # US Eastern (the hub's time zone; Windows has no tz database to look it up)
START = AS_OF - timedelta(days=150)
SEED = 20270320
N_NEW, N_ON_THERAPY = 270, 120
AVG_CALL_MINUTES = 12.0  # live calls in the default week average exactly this (durations are scaled to it)

# Dates the emerging patterns start (the "story" the demo tells in the last few weeks).
STEP_FROM = date(2027, 2, 22)      # Keystone starts asking for step-therapy proof on Iqirvo
SHIP_FROM = date(2027, 2, 20)      # BrightPath Specialty shipments start slipping
NOTES_FROM = date(2027, 2, 25)     # Riverbend GI stops sending chart notes with PAs
COPAY_FROM = date(2027, 3, 1)      # Harbor Mutual accumulator: copay card no longer counts
FORM_FROM = date(2027, 3, 14)      # Meridian rolls out a new PA form (this week: a brand-new issue)
NEW_YEAR = (date(2027, 1, 1), date(2027, 2, 6))  # deductibles reset and plans change

# ------------------------------------------------------------------ master data the simulation adds
PROGRAMS = [{"program_id": "PG03", "program_name": "Sohonos Patient Support Program", "drug": "Sohonos",
             "indications": "FOP", "aliases": None}]
PROGRAM = {"PG01": ("Iqirvo", "Iqirvo Patient Support Program"), "PG02": ("Bylvay", "Bylvay Patient Support Program"),
           "PG03": ("Sohonos", "Sohonos Patient Support Program")}
PAYERS = [{"payer_id": "PY11", "payer_name": "Keystone Health Plan", "aliases": None, "status": "demo volume"},
          {"payer_id": "PY12", "payer_name": "Harbor Mutual", "aliases": None, "status": "demo volume"},
          {"payer_id": "PY13", "payer_name": "Meridian Medicare Advantage", "aliases": None, "status": "demo volume"},
          {"payer_id": "PY14", "payer_name": "Pinecrest Medicaid", "aliases": None, "status": "demo volume"},
          {"payer_id": "PY15", "payer_name": "Northgate BlueCare", "aliases": None, "status": "demo volume"},
          {"payer_id": "PY16", "payer_name": "Atlas Health", "aliases": None, "status": "demo volume"}]
PAYER_NAME = {"PY01": "Summit Health Plan", "PY02": "Crestline Insurance", **{p["payer_id"]: p["payer_name"] for p in PAYERS}}
PAYER_MIX = {"PY15": .18, "PY11": .17, "PY01": .13, "PY13": .13, "PY12": .12, "PY02": .10, "PY14": .11, "PY16": .07}
PHARMACIES = [{"sp_id": "SP1", "sp_name": "Apex Specialty Pharmacy"}, {"sp_id": "SP2", "sp_name": "BrightPath Specialty"},
              {"sp_id": "SP3", "sp_name": "CuraRx Specialty"}, {"sp_id": "SP4", "sp_name": "Delta Specialty Rx"}]
SP_NAME = {p["sp_id"]: p["sp_name"] for p in PHARMACIES}
SP_MIX = {"PG01": {"SP1": .34, "SP2": .34, "SP3": .19, "SP4": .13}, "PG02": {"SP1": .5, "SP3": .5},
          "PG03": {"SP2": .6, "SP4": .4}}
# (practice id, name, programs, weight, prescriber)
PRACTICES = [
    ("PR01", "Lakeview Liver and Digestive Health", ("PG01", "PG02"), 1.4, "Dr. Amelia Grant"),
    ("PR02", "Northside Hepatology", ("PG01",), 1.0, "Dr. Samuel Okafor"),
    ("PR03", "Riverbend GI", ("PG01",), 1.7, "Dr. Laura Chen"),
    ("PR04", "Children's Liver Clinic of Westfield", ("PG02",), 1.2, "Dr. Miriam Patel"),
    ("PR11", "Harborview Hepatology Associates", ("PG01",), 1.0, "Dr. Victor Ramos"),
    ("PR12", "Cedar Valley Gastroenterology", ("PG01",), .9, "Dr. Helen Brooks"),
    ("PR13", "Lakeshore Liver Institute", ("PG01",), 1.0, "Dr. Ian Whitaker"),
    ("PR14", "Bayside GI Partners", ("PG01",), .8, "Dr. Nadia Rahman"),
    ("PR15", "Summit Ridge Digestive Health", ("PG01",), .7, "Dr. Paul Lindqvist"),
    ("PR16", "Northpoint Internal Medicine", ("PG01",), .5, "Dr. Grace Liu"),
    ("PR21", "Mercy Children's Hepatology", ("PG02",), 1.0, "Dr. Daniel Moreau"),
    ("PR22", "Pediatric GI of Oakridge", ("PG02",), .8, "Dr. Erin Walsh"),
    ("PR23", "St. Anne's Children's Liver Center", ("PG02",), .7, "Dr. Omar Haddad"),
    ("PR31", "Metro Orthopedic Genetics Clinic", ("PG03",), 1.0, "Dr. Rebecca Stone"),
    ("PR32", "University Bone & Mineral Center", ("PG03",), 1.0, "Dr. Martin Alvarez"),
    ("PR33", "Fairview Rare Bone Disease Center", ("PG03",), .8, "Dr. Sophie Klein"),
]
PRACTICE = {p[0]: p for p in PRACTICES}
# (staff id, name, role, stages they handle)
STAFF = [
    ("ST-JES", "Jessica", "Hub access specialist", "EBP"), ("ST-MAR", "Marcus", "Hub case manager", "EBPCS"),
    ("ST-RAC", "Rachel", "Nurse educator", "NA"), ("ST-PRI", "Priya", "Access specialist", "BP"),
    ("ST-TYL", "Tyler", "Access specialist", "EBP"), ("ST-M01", "Maria", "Hub case manager", "ECSA"),
    ("ST-M02", "Daniel", "Access specialist", "BP"), ("ST-M03", "Aisha", "Reimbursement specialist", "BCA"),
    ("ST-M04", "Kevin", "Hub case manager", "EPSA"), ("ST-M05", "Grace", "Nurse educator", "NA"),
    ("ST-M06", "Luis", "Patient advocate", "CSA"), ("ST-M07", "Hannah", "Access specialist", "EBP"),
    ("ST-M08", "Omar", "Reimbursement specialist", "CS"), ("ST-M09", "Nora", "Nurse educator", "NA"),
]
STAGES = ["Enrollment", "Benefits verification", "Prior authorization & appeal", "Copay & assistance",
          "Specialty pharmacy & first fill", "Nurse education", "Adherence & refill"]
STAGE_CODE = dict(zip(STAGES, "EBPCSNA"))
STAGE_REASON = {"Enrollment": "Enrollment", "Benefits verification": "Benefits & coverage",
                "Prior authorization & appeal": "Prior authorization", "Copay & assistance": "Affordability / copay",
                "Specialty pharmacy & first fill": "Prescription / shipment status",
                "Nurse education": "Therapy start & education", "Adherence & refill": "Prescription / shipment status"}
BASE_DAYS = {"Enrollment": (1, 2, 6), "Benefits verification": (1, 3, 6), "Prior authorization & appeal": (4, 8, 15),
             "Copay & assistance": (1, 2, 5), "Specialty pharmacy & first fill": (2, 4, 8), "Nurse education": (1, 3, 6)}
BASE_CALLS = {"Enrollment": (1, 1), "Benefits verification": (1, 1), "Prior authorization & appeal": (1, 2),
              "Copay & assistance": (1, 1), "Specialty pharmacy & first fill": (1, 2), "Nurse education": (1, 1)}
MINUTES = {"Enrollment": (3, 6, 12), "Benefits & coverage": (4, 8, 16), "Prior authorization": (5, 11, 20),
           "Affordability / copay": (4, 9, 17), "Prescription / shipment status": (2, 4, 9),
           "Therapy start & education": (8, 15, 28), "Side effects / dosing": (5, 10, 18), "Other": (2, 3, 7)}

FIRST = ["Linda", "Karen", "Susan", "Patricia", "Deborah", "Maria", "Angela", "Sandra", "Donna", "Carol", "Ruth", "Sharon",
         "Michelle", "Laura", "Diane", "Janet", "Teresa", "Gloria", "Denise", "Rosa", "Yvonne", "Anita", "Helen", "Joyce",
         "Brenda", "Marilyn", "Elena", "Priya", "Mei", "Fatima", "Grace", "Lucia", "Irene", "Nancy", "Paula", "Wendy",
         "James", "Robert", "Michael", "David", "Thomas", "Carlos", "Kevin", "Brian", "Anthony", "Steven"]
KIDS = ["Liam", "Noah", "Olivia", "Emma", "Ava", "Mason", "Sophia", "Lucas", "Mia", "Ethan", "Isabella", "Aiden",
        "Harper", "Elijah", "Amelia", "Leo", "Chloe", "Mateo", "Zoe", "Caleb", "Nora", "Owen", "Lily", "Ezra"]
LAST = ["Johnson", "Williams", "Brown", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
        "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
        "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
        "Mitchell", "Carter", "Roberts", "Patel", "Kim", "Shah", "Murphy", "Cooper", "Reed", "Bailey", "Bell", "Kelly"]


# ------------------------------------------------------------------ friction a patient can hit at a stage
@dataclass(eq=False)
class Fr:
    key: str                 # issue key (analytics.ISSUES)
    signal: str              # library signal id; M.. where the library has no signal for it
    w: float                 # base weight against "no friction"
    party: str               # who the calls about it are with
    inbound: float           # share of those calls the other side starts
    days: tuple              # extra days it adds to the stage
    calls: tuple             # extra calls it causes
    reason: str
    sub: str
    quotes: tuple
    open: str                # resolution note while it is open
    fix: str                 # note once fixed
    boost: Callable | None = None  # (patient, day) -> weight multiplier


def _after(d0, hi, lo=1.0):
    return lambda p, day: hi if day >= d0 else lo


def _new_year(mult):
    return lambda p, day: mult if NEW_YEAR[0] <= day <= NEW_YEAR[1] else 1.0


def _payer(pid, mult, since=None, before=1.0):
    return lambda p, day: (mult if p["payer_id"] == pid and (since is None or day >= since)
                           else before if p["payer_id"] == pid else 1.0)


def _sp(spid, mult, since, before):
    return lambda p, day: mult if p["sp_id"] == spid and day >= since else before if p["sp_id"] == spid else 1.0


def _step(p, day):
    if p["payer_id"] == "PY11" and p["program_id"] == "PG01":
        return 4.0
    return .6


def _riverbend(p, day):
    return 2.0 if p["practice_id"] == "PR03" else 1.0


def _meridian_form(p, day):
    return 0.0


def _medicare(p, day):
    return 1.0 if p["payer_id"] == "PY13" else 0.0


FRICTIONS = {
    "Enrollment": (.60, [
        Fr("missing_signature", "S01", .09, "provider_office", .15, (2, 6), (1, 2), "Enrollment", "Missing paperwork",
           ("The form came back without {doctor}'s signature, so we can't open the case yet.",
            "Page two is still unsigned – can you have the doctor sign it and fax it back today?",
            "We received the enrollment form but the prescriber attestation is blank."),
           "Waiting on {office} to return the signed enrollment form.", "Signed enrollment form received; case opened."),
        Fr("missing_card", "S02", .07, "patient", .4, (1, 4), (1, 2), "Enrollment", "Missing paperwork",
           ("We still need a copy of the front and back of your insurance card before we can check benefits.",
            "I sent the card last week, I don't understand why you don't have it.",
            "Can you snap a photo of both sides of the card and text it to us?"),
           "Insurance card copy still outstanding from the patient.", "Insurance card received; benefits check started."),
        Fr("fax_incomplete", "S03", .05, "provider_office", .3, (1, 4), (1, 1), "Enrollment", "Missing paperwork",
           ("Only three of the seven pages came through on the fax.",
            "Our fax log says it went through, but the clinical pages were blank on your side?"),
           "Fax incomplete – office to resend the clinical pages.", "Complete fax received; case opened."),
        Fr("missing_clinical", "S04", .06, "provider_office", .2, (2, 5), (1, 2), "Enrollment", "Missing paperwork",
           ("We're missing the diagnosis code and the patient's weight on the form.",
            "The prescription has no dose and the NPI field is empty."),
           "Form missing clinical fields – office to complete and resend.", "Completed form received; case opened."),
        Fr("missing_consent", "S05", .06, "patient", .3, (1, 4), (1, 2), "Enrollment", "Missing paperwork",
           ("We still need your signature on the consent page before we can talk to your insurance.",
            "I didn't realise there was a second page I had to sign."),
           "Consent page not yet signed by the patient.", "Signed consent received; case opened."),
        Fr("office_unavailable", "S06", .05, "provider_office", .1, (2, 5), (1, 2), "Enrollment", "Enrollment form status",
           ("The person who handles the forms is out until Monday.",
            "She's the only one who does these and she's with patients all afternoon."),
           "Office contact unavailable; hub to call back.", "Reached the office; enrollment form completed."),
    ]),
    "Benefits verification": (.70, [
        Fr("coverage_change", "M04", .04, "patient", .75, (2, 5), (1, 2), "Benefits & coverage", "Coverage changed at plan renewal",
           ("My employer switched plans in January – is the medication still covered?",
            "Your new plan started on the first, so we need to run your benefits again.",
            "I got a new insurance card in the mail, does that change anything?"),
           "New plan details needed to re-run benefits.", "Benefits re-verified on the new plan.", _new_year(7.0)),
        Fr("oop", "S23", .08, "patient", .6, (0, 2), (0, 1), "Affordability / copay", "Cost estimate",
           ("How much is this going to cost me each month?", "I can't do five hundred dollars a month, I just can't.",
            "Is there anything that brings the out-of-pocket down?"),
           "Patient worried about out-of-pocket cost; copay options to be explained.",
           "Copay options explained; patient enrolling in the copay program."),
        Fr("lmn", "S12", .07, "payer", 0, (1, 3), (0, 1), "Benefits & coverage", "Benefits check",
           ("We'll need a letter of medical necessity before we can review this.",
            "The plan requires an LMN for {drug}; without it the request will pend."),
           "{payer} requires a letter of medical necessity; request sent to {office}.", "Letter of medical necessity received."),
    ]),
    "Prior authorization & appeal": (.40, [
        Fr("pa_docs", "S15", .13, "provider_office", .25, (3, 8), (1, 2), "Prior authorization", "Documents for PA",
           ("The PA was pended – they're asking for chart notes and the most recent labs.",
            "It came back pended for missing documentation again.",
            "{payer} won't review it until they get the last two sets of ALP results."),
           "PA pended – {office} to send chart notes and recent labs.", "Documents sent; PA resubmitted and approved."),
        Fr("step_therapy", "S13", .02, "provider_office", .2, (5, 10), (2, 3), "Prior authorization", "Step therapy",
           ("{payer} now requires proof the patient was on ursodiol for twelve months before they'll approve {drug}.",
            "They pended it for step therapy – they want documentation of the prior treatment.",
            "This is new – {payer} started asking for step-therapy records on every {drug} request.",
            "We didn't know about the step therapy rule, we sent what we always send."),
           "{payer} asking for proof of prior ursodiol therapy; {office} to send records.",
           "Step-therapy records accepted; PA approved.", _step),
        Fr("lmn", "S12", .06, "provider_office", .2, (2, 5), (1, 1), "Prior authorization", "Documents for PA",
           ("The plan needs a letter of medical necessity signed by the doctor.",
            "Can the doctor write the medical necessity letter this week?"),
           "{payer} requires a letter of medical necessity; {office} drafting it.", "Letter received; PA submitted."),
        Fr("req_surprise", "S18", .05, "provider_office", .6, (2, 5), (1, 2), "Prior authorization", "Documents for PA",
           ("Nobody told us they needed the liver biopsy report.",
            "This is the first we're hearing about a letter of medical necessity."),
           "Office unaware of the payer requirement; hub resending the full document list.",
           "Office sent the missing item; PA resubmitted."),
        Fr("vague_req", "S17", .04, "provider_office", .1, (2, 4), (1, 1), "Prior authorization", "Documents for PA",
           ("Just send over whatever clinicals you have and we'll go from there.",
            "They need some kind of supporting documentation, the usual."),
           "Requirements given loosely; office unsure what to send.", "Full document list sent; PA submitted."),
        Fr("pa_denied", "S15", .035, "provider_office", .2, (6, 12), (2, 3), "Prior authorization", "Denial & appeal",
           ("The prior auth was denied, so we'll start the appeal with the office.",
            "{payer} denied it as not medically necessary; the doctor needs to sign the appeal letter."),
           "PA denied by {payer}; appeal letter with the prescriber.", "Appeal approved.", _payer("PY14", 2.5)),
        Fr("new_pa_form", "M05", 0, "provider_office", .4, (3, 6), (1, 2), "Prior authorization", "New PA form",
           ("{payer} rolled out a new PA form this month – the old one is being rejected.",
            "We sent it on the old form and it bounced back; they want the new {payer} form.",
            "Where do we even get the new form? Their portal still shows the old one."),
           "Submitted on the old form; {office} to resubmit on {payer}'s new PA form.",
           "Resubmitted on the new form; PA approved.", _meridian_form),
        Fr("missing_clinical", "S04", .03, "provider_office", .15, (3, 7), (1, 2), "Prior authorization", "Documents for PA",
           ("The PA can't go in without the latest chart notes and the ALP labs.",
            "We're still waiting on {office} for the clinical notes – third time asking.",
            "The notes they sent are from last year, the payer wants the last 90 days."),
           "PA on hold – chart notes and ALP labs missing from {office}.", "Clinical notes received; PA submitted.", _riverbend),
        Fr("office_unavailable", "S06", .04, "provider_office", .05, (2, 4), (1, 1), "Prior authorization", "PA status check",
           ("The PA coordinator is out this week.", "Nobody at the office can find the fax we sent."),
           "Office PA coordinator unavailable; hub to call back.", "Reached the office; PA submitted."),
    ]),
    "Copay & assistance": (.56, [
        Fr("oop", "S23", .11, "patient", .6, (1, 4), (0, 1), "Affordability / copay", "Copay card enrollment",
           ("How much is this going to cost me each month?", "Is there anything that brings the out-of-pocket down?",
            "With my deductible I'll be paying over a thousand before it kicks in."),
           "Patient worried about out-of-pocket cost; copay options being set up.",
           "Patient enrolled in the copay program."),
        Fr("copay_not_applied", "S23", .02, "patient", .85, (2, 5), (1, 2), "Affordability / copay", "Copay card not applied",
           ("I have the copay card but the pharmacy still charged me the full {amount}.",
            "They told me my plan doesn't count the copay card toward my deductible anymore.",
            "The card didn't go through at {sp} – they said the plan blocked it."),
           "Copay card not applied at the pharmacy ({payer} accumulator); escalated to the copay vendor.",
           "Copay card re-processed; patient charged the copay amount.", _payer("PY12", 3.0)),
        Fr("deductible", "S23", .02, "patient", .85, (1, 3), (0, 1), "Affordability / copay", "Deductible reset",
           ("My deductible reset in January and now the refill is {amount}.",
            "Nobody told me the new year would start the deductible over."),
           "New-year deductible reset; copay program maximum being checked.", "Copay program covers the deductible.",
           _new_year(18.0)),
        Fr("hardship", "S24", .035, "patient", .6, (2, 6), (1, 1), "Affordability / copay", "Foundation / assistance",
           ("I lost my job last month and I don't know how I'll keep paying for this.",
            "We're down to one income right now."),
           "Financial hardship; foundation referral started.", "Foundation grant approved."),
        Fr("assist_incomplete", "S28", .06, "patient", .3, (3, 8), (1, 2), "Affordability / copay", "Foundation / assistance",
           ("I started the foundation application but I never sent the tax forms.",
            "I wasn't sure what proof of income they wanted, so it's still sitting here."),
           "Assistance application started; income documents still missing.", "Application completed and approved."),
        Fr("medicare_copay", "M06", 0, "patient", .5, (3, 7), (1, 1), "Affordability / copay", "Foundation / assistance",
           ("Because you're on a Medicare plan we can't use the copay card, so let's look at the foundation.",
            "Medicare won't let me use the card? Then what are my options?"),
           "Medicare plan – copay card not allowed; foundation referral in progress.", "Foundation grant approved.",
           _medicare),
    ]),
    "Specialty pharmacy & first fill": (.54, [
        Fr("shipment_delay", "M01", .06, "patient", .85, (2, 6), (1, 2), "Prescription / shipment status", "Where is my shipment",
           ("I was told it would ship Tuesday and I still haven't got a tracking number.",
            "{sp} says the order is on hold – nobody told me why.",
            "It's the third time I've called about this shipment.",
            "They keep saying it's in process at {sp}."),
           "First fill on hold at {sp}; hub chasing a delivery date.",
           "{sp} confirmed delivery; patient received the first fill."),
        Fr("sp_unreachable", "S29", .06, "specialty_pharmacy", .7, (3, 8), (1, 2), "Prescription / shipment status",
           "Pharmacy can't reach patient",
           ("We've tried the patient three times and can't reach them to schedule delivery.",
            "If we can't reach her by Friday we'll have to close the referral."),
           "{sp} unable to reach the patient to schedule delivery.", "Patient reached; delivery scheduled."),
        Fr("hesitation", "S26", .055, "patient", .2, (4, 10), (1, 2), "Therapy start & education", "First fill scheduling",
           ("I need to think about it before I start.", "My husband wants us to talk to the doctor again first.",
            "I'm just not sure I want to start something new right now."),
           "Patient not ready to start; nurse educator call offered.", "Patient agreed to start after the nurse call."),
        Fr("declines", "S27", .02, "patient", .1, (5, 12), (1, 1), "Prescription / shipment status", "First fill scheduling",
           ("Can you just call me back next month? I'm not ready to schedule.",),
           "Patient declined to schedule the first delivery for now.", "Patient scheduled the first delivery."),
        Fr("logistics", "S25", .035, "patient", .4, (2, 6), (1, 1), "Therapy start & education", "Travel & logistics",
           ("The lab is an hour away and I can't take another day off work.",
            "I don't have anyone to drive me to the appointments.",
            "Nobody's home during the day to sign for the delivery."),
           "Travel / delivery barrier; options being arranged.", "Home delivery and local lab arranged."),
    ]),
    "Nurse education": (.76, [
        Fr("medical_q", "S34", .08, "patient", .8, (0, 1), (0, 1), "Side effects / dosing", "Dosing question",
           ("Can I take it with my cholesterol medicine?", "Should I take it with food or on an empty stomach?",
            "Is it okay to take it if I'm also on ursodiol?"),
           "Medical question referred to Medical Information.", "Medical Information answered the question."),
        Fr("side_effect", "S33", .06, "patient", .7, (0, 3), (0, 1), "Side effects / dosing", "Side effect reported",
           ("Since I started it I've had itching that's worse at night.",
            "He's had stomach pain and loose stools since the dose went up.",
            "I've been really tired and a bit nauseous the past week."),
           "Possible side effect reported; sent to safety review.", "Nurse educator followed up; reported to pharmacovigilance."),
        Fr("logistics", "S25", .035, "patient", .4, (1, 4), (0, 1), "Therapy start & education", "Travel & logistics",
           ("I don't have anyone to drive me to the appointments.",),
           "Travel barrier to the lab visits; options being arranged.", "Local lab arranged."),
        Fr("hesitation", "S26", .03, "patient", .2, (2, 6), (1, 1), "Therapy start & education", "Nurse onboarding",
           ("I'm nervous about the side effects, I'm not sure about this.",),
           "Patient hesitant; second nurse call booked.", "Patient comfortable starting after the nurse call."),
    ]),
    "Adherence & refill": (.76, [
        Fr("refill_delay", "M01", .04, "patient", .85, (0, 0), (1, 2), "Prescription / shipment status", "Where is my shipment",
           ("My refill was supposed to arrive Friday and I'm down to my last two doses.",
            "{sp} pushed the refill back again.", "The tracking hasn't moved in four days."),
           "Refill late at {sp}; hub chasing the shipment.", "Refill delivered."),
        Fr("side_effect", "S33", .045, "patient", .7, (0, 0), (0, 1), "Side effects / dosing", "Side effect reported",
           ("The itching has come back the last couple of weeks.", "I've had headaches since the last refill."),
           "Possible side effect reported; sent to safety review.", "Reported to pharmacovigilance; nurse follow-up done."),
        Fr("stop_intent", "S31", .018, "patient", .4, (0, 0), (1, 1), "Side effects / dosing", "Thinking of stopping",
           ("Honestly I'm thinking of stopping – I don't feel any different.",
            "If the itching doesn't get better I'm going to stop taking it."),
           "Patient considering stopping therapy; nurse educator call booked.", "Patient staying on therapy after the nurse call."),
        Fr("missed_doses", "M02", .035, "patient", .5, (0, 0), (0, 1), "Side effects / dosing", "Missed doses",
           ("I've missed a few doses this month, it's hard to remember the evening one.",
            "We ran out over the weekend so he missed two days."),
           "Missed doses reported; reminder plan set up.", "Back on schedule with reminders."),
        Fr("deductible", "S23", .012, "patient", .9, (0, 0), (1, 1), "Affordability / copay", "Deductible reset",
           ("My deductible reset in January and now the refill is {amount}.",
            "Nobody told me the new year would start the deductible over."),
           "New-year deductible reset; copay program maximum being checked.", "Copay program covers the deductible.",
           _new_year(20.0)),
        Fr("copay_not_applied", "S23", .008, "patient", .9, (0, 0), (1, 1), "Affordability / copay",
           "Copay card not applied",
           ("The pharmacy charged me the full {amount} even with the copay card.",),
           "Copay card not applied on the refill ({payer}); escalated to the copay vendor.", "Copay card re-processed.",
           _payer("PY12", 2.0)),
        Fr("reauth", "M03", .03, "provider_office", .2, (0, 0), (1, 2), "Prior authorization", "Re-authorization",
           ("The authorization runs out at the end of the month, so the office needs to submit the renewal.",
            "{payer} needs updated labs for the re-authorization."),
           "Re-authorization due with {payer}; {office} to send updated labs.", "Re-authorization approved.",
           _payer("PY14", 2.0)),
        Fr("medical_q", "S34", .025, "patient", .8, (0, 0), (0, 1), "Side effects / dosing", "Dosing question",
           ("I'm travelling next month, how should I store it?", "What do I do if I miss a dose?"),
           "Medical question referred to Medical Information.", "Medical Information answered the question."),
    ]),
}
DROP_KEYS = {"hesitation", "declines", "stop_intent", "assist_incomplete", "hardship", "sp_unreachable"}
COST_KEYS = {"oop", "copay_not_applied", "deductible", "hardship", "medicare_copay", "assist_incomplete"}

# Routine calls (no friction): (sub reason, party, inbound share, resolved share, note)
ROUTINE = {
    "Enrollment": [("Enrollment form status", "provider_office", .55, .86, "Form received and complete; case opened."),
                   ("Welcome call", "patient", .05, .9, "Welcome call done; next steps explained.")],
    "Benefits verification": [("Benefits check", "payer", 0, .86, "Benefits confirmed: covered with prior authorization."),
                              ("Benefits check", "patient", .3, .86, "Benefits explained to the patient."),
                              ("Cost estimate", "patient", .6, .8, "Expected costs explained; copay program offered.")],
    "Prior authorization & appeal": [("PA status check", "provider_office", .55, .72, "PA status given: under review, decision expected this week."),
                                     ("PA status check", "patient", .8, .76, "Patient updated on the PA status."),
                                     ("PA submitted", "payer", 0, .86, "PA submitted to {payer} with full documentation.")],
    "Copay & assistance": [("Copay card enrollment", "patient", .4, .9, "Patient enrolled in the copay program.")],
    "Specialty pharmacy & first fill": [("First fill scheduling", "patient", .3, .86, "First delivery scheduled with {sp}."),
                                        ("Where is my shipment", "patient", .9, .82, "Tracking number given; delivery confirmed."),
                                        ("First fill scheduling", "specialty_pharmacy", .5, .9, "{sp} confirmed the referral and delivery date.")],
    "Nurse education": [("Nurse onboarding", "patient", .1, .92, "Nurse educator went through dosing and what to expect."),
                        ("How to take it", "patient", .85, .9, "Questions on taking the medicine answered.")],
    "Adherence & refill": [("Refill reminder", "patient", .05, .93, "Refill confirmed with the patient."),
                           ("Where is my shipment", "patient", .9, .86, "Refill shipping confirmed with {sp}.")],
}
ROUTINE_REASON = {"Cost estimate": "Affordability / copay", "How to take it": "Therapy start & education"}
EXTRA = {  # sprinkled hub-side signals: id -> (quotes, speaker)
    "S07": (("I'm calling again about the {topic} we discussed last week.", "Just following up on the open {topic}.",
             "This is my second call about this."), "hub_staff"),
    "S10": (("Hi, this is {agent} from the {drug} support program – please call us back when you can.",), "hub_staff"),
    "S11": (("Let me put you on a brief hold while I check with the pharmacy.",
             "I'm going to transfer you to our reimbursement team."), "hub_staff"),
    "S22": (("Okay, just let us know if you need anything else.", "Alright, we'll be in touch."), "hub_staff"),
    "S30": (("I can enroll you in the copay program today – most patients pay as little as ten dollars.",
             "There's a foundation that may cover the cost; I can start that application with you now."), "hub_staff"),
    "S35": (("This is the fourth time I'm explaining the same thing.", "Nobody ever calls me back.",
             "I've been waiting two weeks for an answer."), "patient"),
    "S36": (("Oh, that was fast – thank you so much.", "That's a relief, thank you."), "patient"),
}
PSEUDO = {  # issues the signal library has no signal for: id -> (name, insight type)
    "M01": ("Shipment delayed", "Process adherence"), "M02": ("Missed doses", "Therapy adherence"),
    "M03": ("Re-authorization due", "Payer requirements"), "M04": ("Coverage changed at plan renewal", "Payer requirements"),
    "M05": ("New PA form required", "Payer requirements"), "M06": ("Copay card not allowed (Medicare)", "Payer requirements"),
}


class _Sim:
    def __init__(self, library: dict):
        self.rng = random.Random(SEED)
        self.library = library
        self.patients, self.calls, self.signals, self.safety = [], [], [], []
        self.n_call = self.n_sig = 0
        self.names = set()
        self.windows = {}  # patient id -> stage -> (from, to)
        self.mention_from = {}  # issue -> first day it can be heard (a change that started on a known date)

    # ------------------------------------------------------------ helpers
    def pick(self, weights: dict):
        r, acc = self.rng.random() * sum(weights.values()), 0.0
        for k, w in weights.items():
            acc += w
            if r <= acc:
                return k
        return k

    def tri(self, lo, mode, hi):
        return self.rng.triangular(lo, hi, mode)

    def patient(self, prog=None, payer=None, practice=None, sp=None) -> dict:
        rng = self.rng
        prog = prog or self.pick({"PG01": .60, "PG02": .28, "PG03": .12})
        practice = practice or self.pick({p[0]: p[3] for p in PRACTICES if prog in p[2]})
        payers = dict(PAYER_MIX)
        if prog != "PG01":
            payers["PY13"] *= .15  # Medicare Advantage: mostly the adult PBC program
            payers["PY14"] *= 2.0
        payer = payer or self.pick(payers)
        sp = sp or self.pick(SP_MIX[prog])
        while True:
            if prog == "PG02":
                first, age = rng.choice(KIDS), rng.randint(1, 14)
            elif prog == "PG03":
                first, age = (rng.choice(KIDS) if rng.random() < .35 else rng.choice(FIRST)), rng.randint(8, 38)
            else:
                first, age = rng.choice(FIRST[:36] if rng.random() < .9 else FIRST[36:]), rng.randint(44, 74)
            name = f"{first} {rng.choice(LAST)}"
            if name not in self.names:
                self.names.add(name)
                break
        case = str(31000 + len(self.patients) * 7 + rng.randint(0, 6))
        dob = date(AS_OF.year - age, rng.randint(1, 12), rng.randint(1, 28))
        drug, prog_name = PROGRAM[prog]
        pr = PRACTICE[practice]
        p = {"patient_id": f"PAT-{case}", "case_id": case, "patient_name": name, "dob": dob, "program_id": prog,
             "practice_id": practice, "prescriber_id": f"DR-{practice}", "payer_id": payer, "source": "demo volume",
             "drug": drug, "program_name": prog_name, "practice_name": pr[1], "payer_name": PAYER_NAME[payer],
             "prescriber_name": pr[4], "sp_id": sp, "sp_name": SP_NAME[sp], "mock": True,
             "child": prog == "PG02" or (prog == "PG03" and age < 18)}
        self.patients.append(p)
        return p

    def staff(self, stage):
        code = STAGE_CODE[stage]
        return self.rng.choice([s for s in STAFF if code in s[3]])

    def when(self, day: date) -> datetime:
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        minutes = self.rng.randint(8 * 60 + 30, 17 * 60 + 15)
        tz = timezone(timedelta(hours=-4 if day >= DST_FROM else -5))
        return datetime.combine(day, time(minutes // 60, minutes % 60), tz)

    def fmt(self, text, p, extra=None):
        drug = p["drug"]
        amount = f"${self.rng.choice([340, 420, 575, 680, 850, 1150])}"
        return text.format(payer=p["payer_name"], sp=p["sp_name"], office=p["practice_name"], doctor=p["prescriber_name"],
                           drug=drug, amount=amount, agent="the hub", topic=(extra or "case"))

    # ------------------------------------------------------------ one conversation
    def call(self, p, stage, day, fr: Fr | None, role: str, nth: int):
        rng = self.rng
        if day < START or day > AS_OF:
            return
        if fr and day < self.mention_from.get(fr.key, START):
            fr, role = None, "intake" if role != "resolve" else role  # before the change: a routine call
        dt = self.when(day)
        if dt.date() < START:
            return
        sid, sname, srole, _ = self.staff(stage)
        if fr:
            party, inbound_p, resolved_p = fr.party, fr.inbound, .2 if role != "resolve" else .95
            reason, sub = fr.reason, fr.sub
            if role == "follow" and stage == "Prior authorization & appeal":
                sub = sub if rng.random() < .55 else "PA status check"
        else:
            sub, party, inbound_p, resolved_p, note = rng.choice(ROUTINE[stage])
            reason = ROUTINE_REASON.get(sub, STAGE_REASON[stage])
            if rng.random() < .025:
                sub, party, inbound_p, resolved_p, reason = "General question", "patient", .9, .95, "Other"
        if role == "resolve":
            resolved_p = .95
        inbound = rng.random() < inbound_p
        if party == "patient" and p["child"]:
            party = "caregiver"
        other = party
        signals = []
        resolved = rng.random() < resolved_p
        voicemail = not inbound and party in ("patient", "caregiver") and rng.random() < .11
        mention = fr is not None and role != "resolve"
        if voicemail:
            other, resolved, mention = "voicemail", False, False
            signals.append(("S10", self.fmt(rng.choice(EXTRA["S10"][0]), p), "hub_staff", "unreachable"))
        if mention:
            signals.append((fr.signal, self.fmt(rng.choice(fr.quotes), p),
                            "hub_staff" if fr.signal in ("S17",) else ("caregiver" if party == "caregiver" else party),
                            fr.key))
            if role == "follow" and rng.random() < .55:
                signals.append(("S07", self.fmt(rng.choice(EXTRA["S07"][0]), p, sub.lower()), "hub_staff", "repeat_contact"))
            if nth >= 2 and rng.random() < .35:
                speaker = party if party != "specialty_pharmacy" else "patient"
                signals.append(("S35", rng.choice(EXTRA["S35"][0]), speaker, "frustration"))
            if fr.key in COST_KEYS and rng.random() < .5:
                signals.append(("S30", rng.choice(EXTRA["S30"][0]), "hub_staff", None))
        if not voicemail and rng.random() < .08:
            signals.append(("S11", rng.choice(EXTRA["S11"][0]), "hub_staff", "hold_transfer"))
        if not voicemail and not inbound and party == "provider_office" and not resolved and rng.random() < .16:
            signals.append(("S22", rng.choice(EXTRA["S22"][0]), "hub_staff", "generic_close"))
        if role == "resolve" and rng.random() < .25:
            signals.append(("S36", rng.choice(EXTRA["S36"][0]), "caregiver" if party == "caregiver" else "patient", None))

        lo, mode, hi = MINUTES.get(reason, MINUTES["Other"])
        secs = (self.tri(.4, .7, 1.2) if voicemail else self.tri(lo, mode, hi)) * 60
        hold = 0.0
        blocks = []
        s11 = next((s for s in signals if s[0] == "S11"), None)
        if s11:
            hold = rng.uniform(90, 300)
            secs += hold
            at = rng.uniform(.2, .6) * secs
            blocks.append({"kind": "transfer" if "transfer" in s11[1] else "hold",
                           "start": f"{int(at // 60):02d}:{int(at % 60):02d}",
                           "end": f"{int((at + hold) // 60):02d}:{int((at + hold) % 60):02d}"})
        talk = (secs - hold) * rng.uniform(.84, .93)

        self.n_call += 1
        cid = f"SIM-{self.n_call:05d}"
        note_open = self.fmt(fr.open, p) if fr else None
        note_fix = self.fmt(fr.fix, p) if fr else self.fmt(note, p)
        if voicemail:
            resolution = "Voicemail left; patient not reached."
        elif resolved:
            resolution = note_fix if (role == "resolve" or not fr) else self.fmt(fr.open, p).split(";")[0] + "; next step agreed with a date."
        else:
            resolution = note_open or ("Still open: " + self.fmt(note, p)[0].lower() + self.fmt(note, p)[1:])
        who = {"patient": "the patient", "caregiver": "the patient's parent", "provider_office": p["practice_name"],
               "payer": p["payer_name"], "specialty_pharmacy": p["sp_name"], "voicemail": "the patient"}[other]
        if inbound:
            summary = f"{who[0].upper() + who[1:]} called the {p['drug']} support program about {sub.lower()}."
        else:
            summary = f"{sname} from the {p['drug']} support program called {who} about {sub.lower()}."
        summary += f" {resolution}"
        raw = {"handoffs": [], "hold_or_transfer": blocks, "speakers": []}
        if fr and mention and fr.key in ("side_effect",):
            raw["handoffs"].append({"to": "Pharmacovigilance", "confirmed": True, "quote": None})
        if fr and mention and fr.key == "medical_q":
            raw["handoffs"].append({"to": "Medical Information", "confirmed": rng.random() < .85, "quote": None})
        if fr and mention and fr.key in ("hardship", "medicare_copay"):
            raw["handoffs"].append({"to": "Foundation", "confirmed": rng.random() < .8, "quote": None})
        sentiment = ("neutral" if voicemail else rng.choice(["negative", "mixed", "mixed", "neutral"]) if mention
                     else rng.choice(["positive", "neutral", "neutral"]))
        c = {"call_id": cid, "external_call_id": f"C-{dt:%y%m%d}-{self.n_call:04d}", "call_datetime": dt,
             "direction": "Inbound" if inbound else "Outbound", "staff_id": sid, "case_id": p["case_id"],
             "channel_layout": None, "audio_filename": None, "audio_blob_key": None, "audio_duration_s": round(secs, 1),
             "audio_channels": 2, "transcript_source": "simulated", "status": "completed", "error": None,
             "patient_id": p["patient_id"], "practice_id": p["practice_id"], "prescriber_id": p["prescriber_id"],
             "payer_id": p["payer_id"], "program_id": p["program_id"], "other_party_type": other, "journey_stage": stage,
             "created_at": dt, "updated_at": dt, "processed_at": dt + timedelta(minutes=25),
             "patient_name": p["patient_name"], "dob": p["dob"], "practice_name": p["practice_name"],
             "payer_name": p["payer_name"], "drug": p["drug"], "program_name": p["program_name"], "staff_name": sname,
             "staff_role": srole, "summary": summary, "contact_reason": reason, "resolved_on_call": resolved,
             "resolution_note": resolution, "identity_verified": voicemail or rng.random() < .95, "sentiment": sentiment,
             "raw": raw, "mock": True, "sp_id": p["sp_id"], "sp_name": p["sp_name"], "sub_reason": sub,
             "time": {"talking": talk, "hold": hold if blocks and blocks[0]["kind"] == "hold" else 0.0,
                      "transfer": hold if blocks and blocks[0]["kind"] == "transfer" else 0.0,
                      "silence": max(0.0, secs - talk - hold), "total": secs}}
        self.calls.append(c)
        for sig, quote, speaker, issue in signals:
            self.n_sig += 1
            name, itype = self.library.get(sig) or PSEUDO.get(sig, (sig, "Other"))
            self.signals.append({"id": 10_000_000 + self.n_sig, "call_id": cid, "signal_id": sig, "quote": quote,
                                 "timestamp_s": round(rng.uniform(.15, .85) * secs), "speaker_role": speaker,
                                 "confidence": 0.9, "signal_name": name, "insight_type": itype, "issue": issue,
                                 "mock": True})
            if sig in ("S33", "S34"):
                hours = rng.uniform(2, 20)
                self.safety.append({"safety_key": f"SIM-{cid}-{sig}", "call_id": cid,
                                    "kind": "adverse_event" if sig == "S33" else "medical_question",
                                    "topic": None if sig == "S33" else rng.choice(["Dosing & food", "Drug interactions",
                                                                                    "Storage & travel", "Missed dose"]),
                                    "mention": quote, "quote": quote, "timestamp_s": None, "asked_by": speaker,
                                    "handled_ok": True, "review_status": "reviewed",
                                    "reviewed_at": c["processed_at"] + timedelta(hours=hours), "mock": True})

    # ------------------------------------------------------------ one patient's journey
    def friction(self, stage, p, day) -> Fr | None:
        none_w, frs = FRICTIONS[stage]
        weights = {None: none_w}
        for f in frs:
            w = f.w * (f.boost(p, day) if f.boost else 1.0)
            if f.boost and f.w == 0:
                w = f.boost(p, day) * .5
            if w > 0:
                weights[f] = weights.get(f, 0) + w
        return self.pick(weights)

    def stage_calls(self, p, stage, start: date, end: date, n: int, fr: Fr | None, completed: bool):
        span = max(1, (end - start).days)
        days = sorted(start + timedelta(days=int(self.rng.uniform(0, span))) for _ in range(n))
        first_mention = 0 if self.rng.random() < .65 else 1
        for k, d in enumerate(days):
            if completed and k == n - 1 and n > 1:
                role = "resolve"
            elif k == 0:
                role = "intake"
            else:
                role = "follow"
            self.call(p, stage, d, fr if (fr and k >= min(first_mention, n - 1)) else None, role, k)

    def onboarding(self, p, referral: date, forced: dict | None = None):
        rng, t = self.rng, referral
        for stage in STAGES[:-1]:
            fr = forced[stage] if forced and stage in forced else self.friction(stage, p, t)
            lo, mode, hi = BASE_DAYS[stage]
            days = round(self.tri(lo, mode, hi))
            if stage == "Prior authorization & appeal":
                days += {"PY14": 3, "PY13": 2}.get(p["payer_id"], 0)
            n = rng.randint(*BASE_CALLS[stage])
            if fr:
                days += rng.randint(*fr.days)
                n += rng.randint(*fr.calls)
            end = t + timedelta(days=max(1, days))
            stalled = fr is not None and fr.key in DROP_KEYS and rng.random() < .14
            self.windows.setdefault(p["patient_id"], {})[stage] = (t, AS_OF if stalled else end)
            if stalled or end > AS_OF:
                # still in this stage today: calls keep their place in the stage, the ones after today never happened
                self.stage_calls(p, stage, t, end if not stalled else t + timedelta(days=days + 12),
                                 n + (1 if stalled else 0), fr, False)
                return
            self.stage_calls(p, stage, t, end, n, fr, True)
            t = end
        self.adherence(p, t)

    def adherence(self, p, since: date):
        rng = self.rng
        self.windows.setdefault(p["patient_id"], {})["Adherence & refill"] = (since, AS_OF)
        first = since + timedelta(days=rng.randint(4, 12))
        if START <= first <= AS_OF:
            self.call(p, "Adherence & refill", first, None, "intake", 0)  # first refill check-in after the nurse start
        d = first + timedelta(days=rng.randint(24, 32))
        while d <= AS_OF:
            if d >= START:
                fr = self.friction("Adherence & refill", p, d)
                if fr:
                    n = 1 + rng.randint(*fr.calls)
                    self.stage_calls(p, "Adherence & refill", d, d + timedelta(days=rng.randint(2, 7)), n, fr, True)
                    if fr.key == "stop_intent" and rng.random() < .3:
                        return  # stopped therapy: no more refills
                elif rng.random() < .5:  # most refills ship without a call
                    self.call(p, "Adherence & refill", d, None, "intake", 0)
                if rng.random() < .08:
                    self.call(p, "Adherence & refill", d + timedelta(days=rng.randint(3, 14)), None, "intake", 0)
            d += timedelta(days=rng.randint(26, 33))
            if rng.random() < .03:
                self.windows[p["patient_id"]]["Adherence & refill"] = (since, d)
                return  # left the program (switched therapy, moved, insurance ended)

    def run(self):
        rng = self.rng
        for _ in range(N_NEW):
            p = self.patient()
            # a steady flow of new referrals (starting before the window, so the hub is already at full load)
            referral = AS_OF - timedelta(days=rng.randint(1, (AS_OF - START).days + 45))
            self.onboarding(p, referral)
        for _ in range(N_ON_THERAPY):
            p = self.patient()
            self.adherence(p, START - timedelta(days=rng.randint(0, 60)))
        self.stories()
        self.calls.sort(key=lambda c: c["call_datetime"])
        seen = {c["patient_id"] for c in self.calls}
        self.patients = [p for p in self.patients if p["patient_id"] in seen]


    def stories(self):
        """The emerging issues the demo tells, planted on their own random stream so tuning the background never
        moves them. Payer / office changes hit new patients at prior authorization; pharmacy and copay-card problems
        hit patients already on therapy. Most of it lands in the last week or two."""
        fr = {f.key + "|" + st: f for st, (_, frs) in FRICTIONS.items() for f in frs}
        pa, sp_stage, refill = "Prior authorization & appeal", "Specialty pharmacy & first fill", "Adherence & refill"
        new_patients = [  # (issue, stage, who, patients, referred this many days ago)
            ("step_therapy", pa, {"prog": "PG01", "payer": "PY11"}, 7, (10, 26)),
            ("new_pa_form", pa, {"prog": "PG01", "payer": "PY13"}, 5, (8, 15)),
            ("missing_clinical", pa, {"prog": "PG01", "practice": "PR03"}, 3, (10, 22)),
            ("shipment_delay", sp_stage, {"prog": "PG01", "sp": "SP2"}, 4, (18, 30)),
        ]
        on_therapy = [  # (issue, which patients, from, patients, share of them in the last 7 days)
            ("copay_not_applied", lambda p: p["payer_id"] == "PY12", COPAY_FROM, 10, .7),
            ("refill_delay", lambda p: p["sp_id"] == "SP2", SHIP_FROM, 9, .6),
        ]
        main, self.rng = self.rng, random.Random(SEED + 1)
        self.mention_from["new_pa_form"] = FORM_FROM
        try:
            for key, stage, who, n, ago in new_patients:
                for _ in range(n):
                    p = self.patient(**who)
                    before = {st: None for st in STAGES[:STAGES.index(stage)]}
                    self.onboarding(p, AS_OF - timedelta(days=self.rng.randint(*ago)), {**before, stage: fr[f"{key}|{stage}"]})
            for key, who, since, n, recent in on_therapy:
                f = fr[f"{key}|{refill}"]
                cands = [p for p in self.patients if who(p) and refill in self.windows.get(p["patient_id"], {})
                         and self.windows[p["patient_id"]][refill][1] >= AS_OF - timedelta(days=1)]
                self.rng.shuffle(cands)
                for p in cands[:n]:
                    lo, hi = (AS_OF - timedelta(days=6), AS_OF) if self.rng.random() < recent else (since, AS_OF - timedelta(days=7))
                    days = sorted(lo + timedelta(days=self.rng.randint(0, max(1, (hi - lo).days))) for _ in range(self.rng.randint(1, 2)))
                    for j, day in enumerate(days):
                        self.call(p, refill, day, f, "intake" if j == 0 else "follow", j)
        finally:
            self.rng = main
            self.mention_from.clear()


def _calibrate_minutes(real, sim):
    """Scale the simulated call lengths so live calls in the default week (recorded ones included) average
    AVG_CALL_MINUTES. Every other period then lands close to it too."""
    week = AS_OF - timedelta(days=6)

    def live(c):
        return c["other_party_type"] not in ("voicemail", "unknown", None) and c.get("audio_duration_s") \
            and c["call_datetime"].date() >= week

    r = [float(c["audio_duration_s"]) for c in real if live(c)]
    s = [c for c in sim if live(c)]
    if not s:
        return
    factor = (AVG_CALL_MINUTES * 60 * (len(r) + len(s)) - sum(r)) / sum(c["audio_duration_s"] for c in s)
    for c in sim:
        if c["other_party_type"] != "voicemail":
            c["audio_duration_s"] = c["audio_duration_s"] * factor
            c["time"] = {k: v * factor for k, v in c["time"].items()}


def augment(tables: dict) -> dict:
    """Add the simulated population to the tables the screens read (returns new lists; the input is not changed)."""
    library = {r["signal_id"]: (r["signal_name"], r["insight_type"]) for r in tables.get("signal_library", [])}
    sim = _Sim(library)
    sim.run()
    _calibrate_minutes(tables["calls"], sim.calls)
    out = dict(tables)
    out["calls"] = sorted(list(tables["calls"]) + sim.calls, key=lambda c: c["call_datetime"])
    out["signals"] = list(tables["signals"]) + sim.signals
    out["patients"] = sorted(list(tables["patients"]) + sim.patients, key=lambda p: p["patient_name"])
    out["safety"] = list(tables["safety"]) + sim.safety
    return out


def master_additions() -> dict:
    return {"programs": PROGRAMS, "payers": PAYERS, "pharmacies": PHARMACIES,
            "practices": [{"practice_id": p[0], "practice_name": p[1]} for p in PRACTICES if p[0] >= "PR10"],
            "staff": [{"staff_id": s[0], "staff_name": s[1], "role": s[2], "organisation": "Hub"} for s in STAFF if s[0].startswith("ST-M")]}
