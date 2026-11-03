# Call Insights – to do

Noted for later (2026-10-15). Not started.

## Live data, batch upload and background processing

Goal: upload one or many calls, then do other work or leave the site. Each call is processed in the background and
every screen updates on its own when it finishes.

- [ ] **Live updates on every screen.** Today only the call page refreshes (it polls every 4 s while the call is processing);
  the five insight screens update only when they are opened again. Push a "call completed / insights recomputed" event
  (server-sent events or a websocket) so open screens refresh themselves, with a small "new data" notice.
- [ ] **Batch upload.** Upload several recordings at once, with call ID, date, direction and case ID per file (or
  read from a CSV / the file name), and a progress list per call.
- [ ] **Background queue / parallel processing.** Today each upload runs in the API process (FastAPI background task):
  if the API restarts, a call in progress is left half-done, and there is no limit on how many run at once.
  Move processing to a persistent job queue with workers so it:
  - survives restarts and resumes / retries failed steps (transcription, AI extraction);
  - runs several calls in parallel, within Azure Speech and Gemini rate limits;
  - recomputes the cross-call insights once per batch, not once per call.
- [ ] **Leave-the-site experience.** A "Processing" list (calls waiting / running / done / failed) and an alert when a
  batch finishes, so nobody has to keep the page open.
