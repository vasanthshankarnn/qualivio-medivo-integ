-- Step 4: cross-call rules output. Deterministic: recomputed from ci_calls / ci_call_signals / ci_call_promises /
-- ci_call_documents by app/rules.py. Idempotent DDL.

-- Draft signal weights per rule (R2 weights were not supplied by Atul; R3 weights are his).
CREATE TABLE IF NOT EXISTS ci_rule_weights (
  rule_id    TEXT NOT NULL REFERENCES ci_rules (rule_id),
  signal_id  TEXT NOT NULL REFERENCES ci_signals (signal_id),
  weight     NUMERIC(5, 2) NOT NULL,
  source     TEXT NOT NULL,
  PRIMARY KEY (rule_id, signal_id)
);

-- One action per rule (Neil: one signal / rule -> one deterministic next-best action).
CREATE TABLE IF NOT EXISTS ci_action_catalog (
  rule_id      TEXT PRIMARY KEY,
  insight_type TEXT NOT NULL,
  title        TEXT NOT NULL,
  action       TEXT NOT NULL,
  owner_team   TEXT NOT NULL,
  priority     TEXT NOT NULL,
  source       TEXT NOT NULL
);

-- PA milestones per case. Demo: synthetic until CRM / payer data is connected (Phase 2).
CREATE TABLE IF NOT EXISTS ci_case_milestones (
  case_id     TEXT NOT NULL,
  milestone   TEXT NOT NULL,
  occurred_on DATE NOT NULL,
  source      TEXT NOT NULL,
  PRIMARY KEY (case_id, milestone)
);

-- Fired insights (rule hits) with their action and evidence. Rebuilt on every recompute.
CREATE TABLE IF NOT EXISTS ci_insights (
  insight_id     BIGSERIAL PRIMARY KEY,
  rule_id        TEXT NOT NULL,
  level          TEXT NOT NULL,
  subject_type   TEXT NOT NULL,
  subject_id     TEXT NOT NULL,
  title          TEXT NOT NULL,
  detail         TEXT,
  score          NUMERIC(8, 2),
  band           TEXT,
  evidence       JSONB NOT NULL DEFAULT '[]'::jsonb,
  action         TEXT,
  owner_team     TEXT,
  status         TEXT NOT NULL DEFAULT 'open',
  as_of          DATE NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ci_insights_subject ON ci_insights (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_ci_insights_rule ON ci_insights (rule_id);

-- Per-call running risk score for R3 (patient timeline chart).
CREATE TABLE IF NOT EXISTS ci_patient_risk (
  patient_id   TEXT NOT NULL,
  call_id      UUID NOT NULL REFERENCES ci_calls (call_id) ON DELETE CASCADE,
  call_score   NUMERIC(6, 2) NOT NULL,
  running      NUMERIC(6, 2) NOT NULL,
  band         TEXT NOT NULL,
  contributing JSONB NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (patient_id, call_id)
);

-- R6 promise status.
CREATE TABLE IF NOT EXISTS ci_promise_status (
  promise_id      BIGINT PRIMARY KEY REFERENCES ci_call_promises (id) ON DELETE CASCADE,
  status          TEXT NOT NULL,
  kept_by_call_id UUID REFERENCES ci_calls (call_id) ON DELETE SET NULL,
  as_of           DATE NOT NULL
);
