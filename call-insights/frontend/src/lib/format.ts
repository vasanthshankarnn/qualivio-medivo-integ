// Calls are shown in the hub's timezone (US Eastern), not the viewer's.
const TZ = 'America/New_York';

const asDate = (v: string) => (/^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(`${v}T12:00:00Z`) : new Date(v)); // plain dates: no day shift

export const fmtDate = (v?: string | null) =>
  v ? asDate(v).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric', timeZone: TZ }) : '—';

export const fmtDay = (v?: string | null) =>
  v ? asDate(v).toLocaleDateString('en-US', { day: 'numeric', month: 'short', timeZone: TZ }) : '—';

export const fmtDateTime = (v?: string | null) =>
  v
    ? `${new Date(v).toLocaleString('en-US', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: TZ })} ET`
    : '—';

export const fmtClock = (s?: number | string | null) => {
  if (s === null || s === undefined || s === '') return '';
  const n = Math.max(0, Math.floor(Number(s)));
  return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`;
};

export const fmtMinutes = (s?: number | null) => (s ? `${Math.max(1, Math.round(Number(s) / 60))} min` : '');

/** The selected period in a few words: "this week", "last 30 days" ... */
export const periodWord = (days: number) => (days === 7 ? 'this week' : days === 0 ? 'all calls' : `last ${days} days`);

/** Lower-case the first letter of a label, but keep abbreviations ("PA pended" stays). */
export const lowerFirst = (s: string) => (s && !/^[A-Z]{2}/.test(s) ? s[0].toLowerCase() + s.slice(1) : s);

export const pctText = (v?: number | null) => (v === null || v === undefined ? '—' : `${v}%`);

export const plural = (n: number, word: string, many?: string) => `${n} ${n === 1 ? word : (many ?? `${word}s`)}`;

export const PARTY_LABEL: Record<string, string> = {
  patient: 'Patient',
  caregiver: 'Caregiver',
  provider_office: 'Provider office',
  payer: 'Payer',
  specialty_pharmacy: 'Specialty pharmacy',
  voicemail: 'Voicemail',
  unknown: 'Unknown',
};

/* Insight-type colours (deck: sentiment & engagement / process adherence / therapy adherence / payer requirements). */
export const INSIGHT_STYLE: Record<string, string> = {
  'Process adherence': 'bg-sky-50 text-sky-800 ring-sky-200',
  'Payer requirements': 'bg-violet-50 text-violet-800 ring-violet-200',
  'Sentiment & engagement': 'bg-amber-50 text-amber-800 ring-amber-200',
  'Therapy adherence': 'bg-teal-50 text-teal-800 ring-teal-200',
  'Call quality': 'bg-indigo-50 text-indigo-800 ring-indigo-200',
  'Safety & compliance': 'bg-rose-50 text-rose-800 ring-rose-200',
};

export const BAND_STYLE: Record<string, string> = {
  high: 'bg-rose-50 text-rose-700 ring-rose-200',
  watch: 'bg-amber-50 text-amber-700 ring-amber-200',
  low: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  confirmed: 'bg-rose-50 text-rose-700 ring-rose-200',
  predicted: 'bg-amber-50 text-amber-700 ring-amber-200',
};

export const RULE_LABEL: Record<string, string> = {
  R1: 'Asked vs told',
  R2: 'Practice friction',
  R3: 'Drop-off risk',
  R4: 'Call close',
  R6: 'Promise not kept',
  SAFETY: 'Safety review',
  IDCHECK: 'Identity check',
};

/** Insight lifecycle (deck slide 17: New · Template updated – watching · Open · Fixed – back to normal · Seasonal – expected). */
export const STATUS: Record<string, { label: string; icon: string; tone: string }> = {
  new: { label: 'New', icon: '●', tone: 'text-crm-orange-dark' },
  open: { label: 'Open', icon: '●', tone: 'text-amber-600' },
  in_progress: { label: 'In progress', icon: '◐', tone: 'text-crm-brand' },
  watching: { label: 'Action taken – watching', icon: '◐', tone: 'text-crm-brand' },
  fixed: { label: 'Fixed – back to normal', icon: '✓', tone: 'text-emerald-600' },
  expected: { label: 'Expected – no action', icon: '○', tone: 'text-slate-500' },
};

export const OWNERS = [
  'Patient Services',
  'Patient Services Lead',
  'Patient Services (access team)',
  'Field Access team',
  'Market Access',
  'Hub operations',
  'Trade / pharmacy lead',
  'Quality & Compliance',
  'Medical Information',
  'Pharmacovigilance',
];

/** Journey stage colours, alternating navy / orange like the deck's stage bands. */
export const STAGE_STYLE: Record<string, { bg: string; short: string }> = {
  Enrollment: { bg: 'bg-app-navy', short: 'Enrollment' },
  'Benefits verification': { bg: 'bg-crm-orange', short: 'Verify' },
  'Prior authorization & appeal': { bg: 'bg-crm-brand-dark', short: 'Prior authorization' },
  'Copay & assistance': { bg: 'bg-crm-orange', short: 'Copay' },
  'Specialty pharmacy & first fill': { bg: 'bg-app-navy', short: 'Specialty pharmacy' },
  'Nurse education': { bg: 'bg-crm-teal', short: 'Nurse education' },
  'Adherence & refill': { bg: 'bg-crm-orange', short: 'Persistence' },
  Unknown: { bg: 'bg-slate-400', short: 'Unknown' },
};

export const PARTY_COLOR: Record<string, string> = {
  'Physician office': '#1a56a8',
  Payer: '#6d4bd1',
  Patient: '#fe602f',
  'Specialty pharmacy': '#0f7c80',
  'Hub process': '#677284',
  Other: '#97a1b0',
};
