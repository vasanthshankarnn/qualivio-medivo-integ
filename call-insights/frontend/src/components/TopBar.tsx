/* eslint-disable @typescript-eslint/no-explicit-any */
import { Bell, ChevronDown, FileText, RotateCcw, X } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAlerts, useBrief, useMaster } from '../lib/api';
import { DEFAULT_DAYS, PERIODS, toQuery, useFilters } from '../lib/filters';
import { fmtDate } from '../lib/format';

/** Sticky bar on every screen: the deck's filter bar, the Alerts button and the Weekly brief. */
export function TopBar() {
  const { pathname } = useLocation();
  const { f, set, active } = useFilters();
  const master = useMaster();
  const scoped = !pathname.startsWith('/journey') && !pathname.startsWith('/calls') && !['/upload', '/rules', '/signals', '/conversation'].includes(pathname);
  const programs = master.data?.programs ?? [];
  return (
    <div className="sticky top-0 z-30 flex h-[60px] items-center gap-3 border-b border-slate-200 bg-white/95 px-6 backdrop-blur">
      {scoped ? (
        <div className="scroll-quiet flex min-w-0 flex-1 items-center gap-1 overflow-x-auto text-[13px] whitespace-nowrap">
          <span className="mr-1 font-semibold text-crm-orange-dark">All patients</span>
          <Select value={f.program} onChange={(v) => set({ program: v })} label="All programs"
            options={programs.map((p: any) => ({ value: p.program_id, label: p.drug }))} />
          <Select value={f.stage} onChange={(v) => set({ stage: v })} label="All stages"
            options={(master.data?.stages ?? []).map((s: string) => ({ value: s, label: s }))} />
          <Select value={f.payer} onChange={(v) => set({ payer: v })} label="All payers"
            options={(master.data?.payers ?? []).map((p: any) => ({ value: p.payer_id, label: p.payer_name }))} />
          <Select value={f.sp} onChange={(v) => set({ sp: v })} label="All pharmacies"
            options={(master.data?.pharmacies ?? []).map((p: any) => ({ value: p.sp_id, label: p.sp_name }))} />
          <Select value="calls" onChange={() => undefined} label="Channel" fixed
            options={[{ value: 'calls', label: 'Calls' }, ...['Texts', 'Emails', 'Faxes', 'Portal notes', 'Visit summaries'].map((c) => ({ value: c, label: `${c} · Phase 2`, disabled: true }))]} />
          <Select value={String(f.days)} onChange={(v) => set({ days: Number(v) })} label="Period" fixed noEmpty
            options={PERIODS.map((p) => ({ value: String(p.days), label: p.label }))} />
          <span className="ml-1 hidden text-xs text-slate-400 2xl:inline">vs prior 13 weeks</span>
          {active && (
            <button type="button" onClick={() => set({ program: '', stage: '', payer: '', sp: '', days: DEFAULT_DAYS })}
              className="ml-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-100">
              <RotateCcw className="h-3 w-3" /> Reset
            </button>
          )}
        </div>
      ) : (
        <div className="flex-1" />
      )}
      <Alerts />
      <Brief />
    </div>
  );
}

function Select({ value, onChange, label, options, fixed, noEmpty }: {
  value: string; onChange: (v: string) => void; label: string; options: { value: string; label: string; disabled?: boolean }[];
  fixed?: boolean; noEmpty?: boolean;
}) {
  const current = options.find((o) => o.value === value);
  return (
    <label className={`relative inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-lg px-2.5 py-1.5 transition hover:bg-slate-100 ${current && !fixed ? 'bg-crm-brand-light font-semibold text-crm-brand-dark' : 'text-app-navy'}`}>
      <span className="truncate">{current?.label ?? label}</span>
      <ChevronDown className="h-3.5 w-3.5 opacity-60" />
      <select value={value} onChange={(e) => onChange(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0">
        {!noEmpty && <option value="">{label}</option>}
        {options.map((o) => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
      </select>
    </label>
  );
}

function usePopover() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  return { open, setOpen, ref };
}

const TONE: Record<string, { bar: string; text: string; btn: string }> = {
  orange: { bar: 'bg-crm-orange', text: 'text-crm-orange-dark', btn: 'bg-crm-orange hover:bg-crm-orange-dark' },
  navy: { bar: 'bg-app-navy', text: 'text-app-navy', btn: 'bg-app-navy hover:bg-crm-brand-dark' },
  purple: { bar: 'bg-violet-600', text: 'text-violet-700', btn: 'bg-violet-600 hover:bg-violet-700' },
};

/** Proactive alerts (deck slide 40): emerging access issue · drop-off risk · possible adverse event. */
function Alerts() {
  const { open, setOpen, ref } = usePopover();
  const { data } = useAlerts();
  const { qs } = useFilters();
  const navigate = useNavigate();
  const n = data?.count ?? 0;
  return (
    <div ref={ref} className="relative shrink-0">
      <button type="button" onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 rounded-lg bg-crm-orange px-3.5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-crm-orange-dark">
        <Bell className="h-4 w-4" /> Alerts
        <span className="grid h-5 min-w-5 place-items-center rounded-full bg-white px-1 text-[11px] font-bold text-crm-orange-dark">{n}</span>
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-[30rem] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
            <div>
              <div className="text-sm font-semibold text-app-navy">Proactive alerts</div>
              <div className="text-xs text-slate-500">Compared daily with normal · thresholds and routing set by Ipsen</div>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="rounded p-1 text-slate-400 hover:bg-slate-100"><X className="h-4 w-4" /></button>
          </div>
          <div className="max-h-[70vh] space-y-3 overflow-y-auto bg-slate-50 p-4">
            {n === 0 && <p className="py-6 text-center text-sm text-slate-500">Nothing above threshold.</p>}
            {data?.alerts.map((a: any, i: number) => {
              const t = TONE[a.tone] ?? TONE.navy;
              return (
                <div key={i} className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                  <div className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white ${t.bar}`}>● {a.type}</div>
                  <div className="space-y-2 px-4 py-3 text-[13px]">
                    <div className={`font-semibold ${t.text}`}>{a.title}</div>
                    <Field label="Trigger">{a.trigger}</Field>
                    <Field label="Evidence">{a.evidence}</Field>
                    <Field label="Suggested owner">{a.owner}</Field>
                    <button type="button" onClick={() => { setOpen(false); navigate(`${a.to}${a.to.startsWith('/journey') ? '' : qs}`); }}
                      className={`mt-1 w-full rounded-lg py-1.5 text-xs font-semibold text-white ${t.btn}`}>Open evidence ›</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-2">
      <span className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">{label}</span>
      <span className="text-slate-700">{children}</span>
    </div>
  );
}

/** The weekly insight brief (deck slide 21). */
function Brief() {
  const [open, setOpen] = useState(false);
  const { data } = useBrief();
  const { f } = useFilters();
  const navigate = useNavigate();
  const bar: Record<string, string> = { orange: 'bg-crm-orange', navy: 'bg-app-navy', green: 'bg-emerald-600' };
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-lg border-2 border-app-navy px-3.5 py-1.5 text-[13px] font-semibold text-app-navy transition hover:bg-app-navy hover:text-white">
        <FileText className="h-4 w-4" /> Weekly brief
      </button>
      {open && data && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button type="button" aria-label="Close" onClick={() => setOpen(false)} className="absolute inset-0 bg-slate-900/25" />
          <aside className="relative flex h-full w-full max-w-[40rem] flex-col bg-white shadow-2xl animate-[slidein_.18s_ease-out]">
            <header className="bg-app-navy px-7 py-6 text-white">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-[11px] font-semibold tracking-widest text-white/60 uppercase">Every Monday · 7 am</div>
                  <h2 className="mt-1 text-xl font-semibold">Weekly insight brief</h2>
                  <p className="mt-1 text-sm text-white/75">
                    All programs · week of {fmtDate(data.week_of)} · {data.conversations.toLocaleString()} conversations
                  </p>
                </div>
                <button type="button" onClick={() => setOpen(false)} className="rounded-md p-1 text-white/70 hover:bg-white/10"><X className="h-5 w-5" /></button>
              </div>
            </header>
            <div className="flex-1 space-y-3 overflow-y-auto p-6">
              {data.sections.map((s: any, i: number) => (
                <button key={s.title} type="button" onClick={() => { setOpen(false); navigate(`${s.to}${toQuery(f)}`); }}
                  className="flex w-full overflow-hidden rounded-xl border border-slate-200 bg-white text-left shadow-sm transition hover:shadow-md">
                  <span className={`w-1.5 shrink-0 ${bar[s.tone] ?? bar.navy}`} />
                  <span className="px-5 py-4">
                    <span className={`block text-[15px] font-semibold ${s.tone === 'orange' ? 'text-crm-orange-dark' : s.tone === 'green' ? 'text-emerald-700' : 'text-app-navy'}`}>
                      {i + 1}&nbsp;&nbsp;{s.title}
                    </span>
                    <span className="mt-1 block text-sm leading-relaxed text-slate-700">{s.text}</span>
                  </span>
                </button>
              ))}
              <p className="pt-2 text-xs text-slate-500">
                Every line opens the screen and the conversations behind it. Suggested owners only – routing is set by Ipsen.
                Marketing receives a de-identified version. {data.baseline_note}.
              </p>
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
