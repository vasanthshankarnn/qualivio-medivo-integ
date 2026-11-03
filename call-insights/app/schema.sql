-- call-insights tables. Created in Qualivio's schema (DB_SCHEMA, via search_path); every table is
-- prefixed ci_ so nothing collides with Qualivio's own tables. Idempotent: safe to run repeatedly.

-- ---------------------------------------------------------------- master data ("name tags")
CREATE TABLE IF NOT EXISTS ci_programs (
  program_id   TEXT PRIMARY KEY,
  program_name TEXT NOT NULL,
  drug         TEXT NOT NULL,
  indications  TEXT,
  aliases      TEXT
);

CREATE TABLE IF NOT EXISTS ci_practices (
  practice_id   TEXT PRIMARY KEY,
  practice_name TEXT NOT NULL,
  aliases       TEXT,
  note          TEXT
);

CREATE TABLE IF NOT EXISTS ci_prescribers (
  prescriber_id   TEXT PRIMARY KEY,
  prescriber_name TEXT NOT NULL,
  practice_id     TEXT REFERENCES ci_practices (practice_id),
  specialty       TEXT
);

CREATE TABLE IF NOT EXISTS ci_payers (
  payer_id   TEXT PRIMARY KEY,
  payer_name TEXT NOT NULL,
  aliases    TEXT,
  status     TEXT
);

CREATE TABLE IF NOT EXISTS ci_staff (
  staff_id     TEXT PRIMARY KEY,
  staff_name   TEXT NOT NULL,
  role         TEXT NOT NULL,
  organisation TEXT
);

CREATE TABLE IF NOT EXISTS ci_patients (
  patient_id    TEXT PRIMARY KEY,
  case_id       TEXT UNIQUE,
  patient_name  TEXT NOT NULL,
  dob           DATE,
  program_id    TEXT REFERENCES ci_programs (program_id),
  practice_id   TEXT REFERENCES ci_practices (practice_id),
  prescriber_id TEXT REFERENCES ci_prescribers (prescriber_id),
  payer_id      TEXT REFERENCES ci_payers (payer_id)
);

-- ---------------------------------------------------------------- signal library and rules
CREATE TABLE IF NOT EXISTS ci_signals (
  signal_id     TEXT PRIMARY KEY,
  insight_type  TEXT,
  journey_stage TEXT,
  signal_name   TEXT NOT NULL,
  meaning       TEXT,
  who_says      TEXT,
  keywords      TEXT,
  example_line  TEXT,
  use_cases     TEXT,
  rule_based    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS ci_rules (
  rule_id     TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  use_cases   TEXT,
  level       TEXT,
  inputs      TEXT,
  logic       TEXT,
  output      TEXT,
  data_needed TEXT
);

-- ---------------------------------------------------------------- calls
-- Metadata a phone system / call centre would send, plus the labels (grouping keys) resolved by the pipeline.
CREATE TABLE IF NOT EXISTS ci_calls (
  call_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_call_id   TEXT UNIQUE,
  call_datetime      TIMESTAMPTZ,
  direction          TEXT,
  staff_id           TEXT REFERENCES ci_staff (staff_id),
  case_id            TEXT,
  channel_layout     JSONB,
  audio_filename     TEXT,
  audio_blob_key     TEXT,
  audio_duration_s   NUMERIC(10, 2),
  audio_channels     SMALLINT,
  transcript_source  TEXT,
  status             TEXT NOT NULL DEFAULT 'pending',
  error              TEXT,
  -- labels resolved after extraction (the keys calls are grouped by)
  patient_id         TEXT REFERENCES ci_patients (patient_id),
  practice_id        TEXT REFERENCES ci_practices (practice_id),
  prescriber_id      TEXT REFERENCES ci_prescribers (prescriber_id),
  payer_id           TEXT REFERENCES ci_payers (payer_id),
  program_id         TEXT REFERENCES ci_programs (program_id),
  other_party_type   TEXT,
  journey_stage      TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at       TIMESTAMPTZ,
  CONSTRAINT ci_calls_status_chk CHECK (status IN ('pending', 'transcribing', 'extracting', 'completed', 'failed')),
  CONSTRAINT ci_calls_transcript_source_chk CHECK (transcript_source IS NULL OR transcript_source IN ('azure', 'provided'))
);
CREATE INDEX IF NOT EXISTS idx_ci_calls_patient ON ci_calls (patient_id, call_datetime);
CREATE INDEX IF NOT EXISTS idx_ci_calls_practice ON ci_calls (practice_id, call_datetime);
CREATE INDEX IF NOT EXISTS idx_ci_calls_payer ON ci_calls (payer_id, call_datetime);
CREATE INDEX IF NOT EXISTS idx_ci_calls_case ON ci_calls (case_id, call_datetime);

CREATE TABLE IF NOT EXISTS ci_call_segments (
  id            BIGSERIAL PRIMARY KEY,
  call_id       UUID NOT NULL REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  seq           INTEGER NOT NULL,
  start_s       NUMERIC(10, 2),
  end_s         NUMERIC(10, 2),
  channel       SMALLINT,
  speaker_label TEXT,
  speaker_role  TEXT,
  text          TEXT NOT NULL,
  CONSTRAINT uq_ci_call_segments UNIQUE (call_id, seq)
);

-- One row per call: the AI's call-level output (raw JSON kept for audit).
CREATE TABLE IF NOT EXISTS ci_call_extractions (
  call_id            UUID PRIMARY KEY REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  model              TEXT,
  summary            TEXT,
  other_party_type   TEXT,
  journey_stage      TEXT,
  identity_verified  BOOLEAN,
  identity_quote     TEXT,
  sentiment          TEXT,
  sentiment_reason   TEXT,
  raw                JSONB,
  prompt_tokens      INTEGER,
  output_tokens      INTEGER,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ci_call_entities (
  id            BIGSERIAL PRIMARY KEY,
  call_id       UUID NOT NULL REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  entity_type   TEXT NOT NULL,
  heard_text    TEXT,
  resolved_id   TEXT,
  match_method  TEXT,
  confidence    NUMERIC(4, 2),
  CONSTRAINT ci_call_entities_type_chk
    CHECK (entity_type IN ('patient', 'practice', 'prescriber', 'payer', 'program', 'office_contact'))
);
CREATE INDEX IF NOT EXISTS idx_ci_call_entities_call ON ci_call_entities (call_id);

CREATE TABLE IF NOT EXISTS ci_call_signals (
  id            BIGSERIAL PRIMARY KEY,
  call_id       UUID NOT NULL REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  signal_id     TEXT NOT NULL REFERENCES ci_signals (signal_id),
  quote         TEXT,
  timestamp_s   NUMERIC(10, 2),
  speaker_role  TEXT,
  confidence    NUMERIC(4, 2)
);
CREATE INDEX IF NOT EXISTS idx_ci_call_signals_call ON ci_call_signals (call_id);
CREATE INDEX IF NOT EXISTS idx_ci_call_signals_signal ON ci_call_signals (signal_id);

CREATE TABLE IF NOT EXISTS ci_call_promises (
  id            BIGSERIAL PRIMARY KEY,
  call_id       UUID NOT NULL REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  made_by_role  TEXT,
  action        TEXT NOT NULL,
  due_text      TEXT,
  due_date      DATE,
  quote         TEXT,
  timestamp_s   NUMERIC(10, 2)
);
CREATE INDEX IF NOT EXISTS idx_ci_call_promises_call ON ci_call_promises (call_id);

CREATE TABLE IF NOT EXISTS ci_call_documents (
  id         BIGSERIAL PRIMARY KEY,
  call_id    UUID NOT NULL REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  list_type  TEXT NOT NULL,
  item       TEXT NOT NULL,
  CONSTRAINT ci_call_documents_type_chk
    CHECK (list_type IN ('payer_required', 'requested_from_office', 'missing_item', 'confirmed_sent'))
);
CREATE INDEX IF NOT EXISTS idx_ci_call_documents_call ON ci_call_documents (call_id);

-- Master rows can be registered automatically the first time a call mentions a new practice / payer / patient.
ALTER TABLE ci_practices ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE ci_payers ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE ci_prescribers ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE ci_patients ADD COLUMN IF NOT EXISTS source TEXT;

-- ---------------------------------------------------------------- insight workspace (deck screens 1-5)
-- Per-call fields used by the screens: why the contact happened and whether it was resolved on the call.
ALTER TABLE ci_call_extractions ADD COLUMN IF NOT EXISTS contact_reason TEXT;
ALTER TABLE ci_call_extractions ADD COLUMN IF NOT EXISTS resolved_on_call BOOLEAN;
ALTER TABLE ci_call_extractions ADD COLUMN IF NOT EXISTS resolution_note TEXT;

-- Safety & Medical Information queue items found on a call (rebuilt when the call is reprocessed).
CREATE TABLE IF NOT EXISTS ci_call_safety (
  id            BIGSERIAL PRIMARY KEY,
  call_id       UUID NOT NULL REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  kind          TEXT NOT NULL,
  topic         TEXT,
  mention       TEXT NOT NULL,
  quote         TEXT,
  timestamp_s   NUMERIC(10, 2),
  asked_by      TEXT,
  handled_ok    BOOLEAN,
  safety_key    TEXT NOT NULL,
  CONSTRAINT ci_call_safety_kind_chk
    CHECK (kind IN ('adverse_event', 'quality_complaint', 'medical_question', 'dosing_mistake'))
);
CREATE INDEX IF NOT EXISTS idx_ci_call_safety_call ON ci_call_safety (call_id);

-- What people did with an item. Keyed by a stable key so it survives recomputes and reprocessing.
CREATE TABLE IF NOT EXISTS ci_insight_actions (
  insight_key  TEXT PRIMARY KEY,           -- rule_id|subject_type|subject_id
  status       TEXT NOT NULL DEFAULT 'open',
  owner        TEXT,
  action_note  TEXT,
  action_date  DATE,
  useful       BOOLEAN,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ci_insight_actions_status_chk
    CHECK (status IN ('new', 'open', 'in_progress', 'watching', 'fixed', 'expected'))
);

CREATE TABLE IF NOT EXISTS ci_safety_review (
  safety_key   TEXT PRIMARY KEY,           -- external_call_id|kind|seconds
  status       TEXT NOT NULL,
  reviewed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ci_safety_review_status_chk
    CHECK (status IN ('awaiting', 'pharmacovigilance', 'medical_information', 'quality_complaint', 'not_safety'))
);

-- "Normal" reference values the screens compare against (13-week baseline). Synthetic for the demo.
CREATE TABLE IF NOT EXISTS ci_baseline (
  metric  TEXT NOT NULL,
  key     TEXT NOT NULL,
  normal  NUMERIC(10, 3) NOT NULL,
  unit    TEXT NOT NULL,
  source  TEXT NOT NULL,
  PRIMARY KEY (metric, key)
);
