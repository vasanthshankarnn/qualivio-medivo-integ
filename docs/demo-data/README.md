# Call-insights demo data (step 1)

Generated from `usecase_2..4` and `signals/Conversational Signal Library.xlsx` by `build_demo_data.py`.
All people, practices and payers are fictional (Atul's synthetic demo calls).

| File | What |
|---|---|
| calls.csv | 15 calls with labels: case, patient, practice, payer, program, staff, call type, stereo channel roles |
| patients.csv, practices.csv, prescribers.csv, payers.csv, programs.csv, staff.csv | Master "name tag" lists used to label and group calls |
| transcripts_clean/ | Transcripts with the header removed (no gap / signal give-aways) - this is what the AI sees |
| signal_library.csv, cross_call_rules.csv | Atul's 38 signals and 6 rules, as CSV |
| answer_key_signals.csv | Expected signals per call (from the library) + a keyword check |
| answer_key_calls.csv | Expected gap / signal per call (from the manifests) |
| answer_key_rules.csv | Expected outcome per cross-call rule |

Answer-key files are for scoring only and must never be sent to the AI.
Open items: UC1 calls, payer names for UC2/UC3, R2 weights, NBA per signal, PA milestone dates.
