# Call Insights – conversation analytics POC

Call Insights turns patient-support hub phone calls into insight a program leader can act on. It was built as the
demo engine for a pharma patient-services RFP: three rare-disease programs (Iqirvo, Bylvay, Sohonos), a hub that
talks to patients, physician offices, payers and specialty pharmacies, and nothing recorded except the calls.

The question it answers is **why**: not "prior authorization takes 9 days" (the CRM already says that) but "prior auth
is slow because Keystone started asking for step-therapy proof and offices weren't told". Everything is derived from
what was said on the calls.

The app is in [`call-insights/`](call-insights). The master data it seeds from is in [`docs/demo-data/`](docs/demo-data).

---

## What you see

| Tab | What it shows |
|---|---|
| **Executive summary** | One page for leaders. Every number is a slice of the same calls: by stage, by emerging issue, by patient at risk, by call reason. Each box opens its own tab. |
| **Where patients get stuck** | Each journey stage: patients and calls this period, time in stage, patients waiting 10+ days, why they wait (signals heard), who it is with, and a stage × friction heat map. |
| **Emerging access issues** | Every access issue heard (step therapy, PA pended, copay card not applied, shipment delays …) per payer, pharmacy or office, compared with its own normal. **New** / **Rising** / **Steady** / **Easing**. Click one for the detail: trend, why it was flagged, patients affected, quotes, suggested owner and next step. |
| **Patients at risk of dropping off** | Every patient whose calls carry drop-off signals (cost worries, "need to think about it", pharmacy delays, side effects, missed doses, thinking of stopping), grouped by what was heard, with a risk level and next step. Opens the patient journey. |
| **Call summary** | Every call by reason and sub-reason, who it was about (pharmacy, payer, office, program), first-call resolution, length, trend and sample quotes. |
| **Hub quality** | Operational measures, each with the number, the cause and the fix: first-call resolution, handle time, repeat calls, escalations, ID checks, consistency, training needs, safety. |
| **Call analysis** | Volume and duration by direction and call type. |
| **Conversation analysis** | Recorded calls with AI scores, and a per-call view with the timeline player and the signals heard. |

All tabs share one filter bar (program, stage, payer, specialty pharmacy, period). **Normal** always means the 13 weeks
before the selected period. Every number opens an evidence drawer with the call excerpts behind it.

---

## How it works

```
call audio ──► ffmpeg (stereo kept) ──► Azure Blob ──► Azure Speech batch, one channel per party ─┐
optional transcript ──► parser ([mm:ss] lines only) ───────────────────────────────────────────────┤
                                                                                                    ▼
            Gemini extraction: signals (S01–S38) with quotes, contact reason, resolved on call,
            promises, documents, handoffs, holds, safety mentions, names heard
                                                                                                    ▼
            deterministic resolver: names heard → patient / practice / payer / program IDs
            (the case record wins; names heard fill gaps and are flagged)
                                                                                                    ▼
            ci_ tables in Postgres ──► cross-call rules (R1–R6, safety, ID check) ──► next-best action
                                                                                                    ▼
            analytics engines (no AI): issue taxonomy, emerging-issue detection, at-risk scoring,
            stage friction, call summary ──► FastAPI ──► React UI
```

- **Signals.** Each signal heard maps to one issue (e.g. S15 → "PA pended: missing documents"), and each issue to a
  category: Payer & authorization, Affordability, Pharmacy & dispensing, Paperwork & offices, Hub service, Patient,
  Safety & medical. That grouping drives the tabs ([`app/analytics.py`](call-insights/app/analytics.py)).
- **Emerging issues.** For each issue × payer / pharmacy / office, the engine counts *patients* who raised it in the
  period. It compares that with the same-length blocks in the 13 weeks before, per call at the same journey stages, so
  a growing hub doesn't make everything look like it's rising. The bar for "new" and "rising" scales with the period
  ([`app/engines.py`](call-insights/app/engines.py)).
- **At-risk patients.** Each distinct worry adds weight. Repeats add a little. Support offered afterwards lowers it.
  The total gives High / Medium / Low.
- **AI only extracts.** Counting, comparing, flagging and suggested actions are deterministic code.

### Demo volume (simulated)

The recorded demo calls are real pipeline output, but there are only 16 of them, too few for trends and filters.
[`app/mock.py`](call-insights/app/mock.py) simulates five months of hub activity in memory: about 400 patients and
about 150 calls a week, with a fixed seed. Planted stories give the demo something to find, e.g. a payer starting to ask for
step-therapy proof, a pharmacy shipping refills late, an accumulator plan stopping copay cards.

- Nothing simulated is written to the database.
- Simulated rows are flagged `mock`. Their evidence has no "Open call" link, because there is no recording.
- Turn it off with `CI_DEMO_VOLUME=0`; the screens then show only the recorded calls.
- Live calls in the default week average 12 minutes (`AVG_CALL_MINUTES` in `mock.py`).

---

## Setup

### Prerequisites

- Python **3.13** and [uv](https://docs.astral.sh/uv/)
- Node.js **18+** and npm
- **ffmpeg** on `PATH` (only for processing new audio)
- A **PostgreSQL** database. The app creates its own tables, all prefixed `ci_`, in the schema you configure.
- To process new calls: an **Azure Storage** account (Blob), **Azure Speech** (batch transcription), and **Google
  Vertex AI** (Gemini). The screens run without these.

### 1. Configure

Settings are read from `../caller-qa-py/.env` (the Qualivio service's env file) when it exists, then from a local
`call-insights/.env`, which overrides it. Set `CI_SHARED_ENV` to point at another file. Copy the template and fill in
your own values:

```bash
cd call-insights
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `DATABASE_URL`, `DB_SCHEMA` | Postgres connection and schema (tables are prefixed `ci_`) |
| `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_RECORDING_CONTAINER_NAME`, `CI_BLOB_PREFIX` | Where uploaded audio is stored |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `AZURE_SPEECH_BATCH_ENDPOINT` | Batch transcription |
| `GCP_PROJECT_ID`, `GCP_LOCATION`, `GCP_CLIENT_EMAIL`, `GCP_PRIVATE_KEY`, `GEMINI_MODEL_EXTRACT`, `GEMINI_THINKING_EXTRACT` | Gemini extraction |
| `CI_AS_OF_DATE` | The demo "today" (default `2027-03-20`; the demo calls are Feb–Mar 2027) |
| `CI_CALL_TIMEZONE` | Hub timezone for dates (default `America/New_York`) |
| `CI_DEMO_VOLUME` | `1` (default) adds the simulated volume; `0` shows recorded calls only |
| `CI_CORS_ORIGINS` | Allowed UI origins (default `http://localhost:5180`) |

Never commit `.env`. It is in `.gitignore`.

### 2. Install and seed

```bash
cd call-insights
uv sync
uv run python -m scripts.seed          # creates the ci_ tables, loads master data + signal library from docs/demo-data
```

### 3. Run

```bash
# API: http://localhost:8010 (Swagger at /docs)
cd call-insights
uv run uvicorn app.main:app --port 8010

# UI: http://localhost:5180 (proxies /v1 to the API)
cd call-insights/frontend
npm install
npm run dev
```

The API warms its screen cache at startup; the first page load after a restart can take a few seconds.

### 4. Process calls (optional)

- **One call:** upload it from **Analyse a call** in the UI, or `POST /v1/calls` with an audio file. A transcript is
  optional; if given, transcription is skipped.
- **The demo calls:** their audio is not in this repo.

```bash
uv run python -m scripts.ingest_demo_calls                     # audio → Azure transcription → Gemini
uv run python -m scripts.ingest_demo_calls --with-transcript   # use the cleaned transcripts in docs/demo-data
uv run python -m scripts.ingest_demo_calls --only ST01 --reset # one call, fresh
uv run python -m scripts.evaluate                              # score extraction against the answer key
uv run python -m scripts.checkpoint export <dir>               # back up every ci_ table to CSV (restore <dir> to load)
```

---

## Project layout

```
call-insights/
  app/
    main.py          FastAPI app, startup, upload/process endpoints, cache warm-up
    pipeline.py      register → transcribe → extract → resolve → store
    services/        Azure Blob, Azure Speech, Gemini extraction, transcript parser, resolver, audio
    rules.py         cross-call rules R1–R6, safety, ID check → ci_insights
    analytics.py     data loading, filters, issue taxonomy, "normal" from history
    engines.py       emerging issues, at-risk patients, call summary, stage friction
    dashboard.py     Executive summary, hub quality, call/conversation analysis, journey, alerts, brief
    tabs.py          endpoints for the tabs (stuck, access-issues, at-risk, call-summary)
    mock.py          simulated demo volume (in memory)
    schema.sql       ci_ tables
  scripts/           seed, ingest demo calls, evaluate, checkpoint export/restore
  frontend/          React 18 + Vite + Tailwind 4 + Recharts + React Query
    src/pages/       one file per screen
docs/demo-data/      master data, signal library, baseline, cleaned demo transcripts, answer keys (all synthetic)
```

Main read endpoints (all take `program`, `stage`, `payer`, `sp`, `days`, where `days=all` means every call):
`/v1/dashboard/summary`, `/stuck`, `/access-issues`, `/access-issues/{key}`, `/at-risk`, `/call-summary`,
`/hub-quality`, `/executive`, `/patient-calls`, `/v1/patients/{id}/journey`, `/v1/calls/{id}/conversation`,
`/v1/alerts`, `/v1/brief`.

---

## Notes and limits

- **POC.** It has no authentication and no automated tests. Uploads are processed in the API's background tasks, not
  a queue (see [`TODO.md`](call-insights/TODO.md)).
- **Data:** all patients, offices, payers and calls are fictional. The AI quality scores on Conversation analysis are
  demo values.
- **Phase 2 (not built):** CRM data (stage dates, outcomes, patient totals) and other channels (texts, emails, faxes).
  Today, stages and timings are inferred from the calls.
- **Shared schema:** if the `ci_` tables share a schema with other services, a tool that truncates that schema
  removes them too.
