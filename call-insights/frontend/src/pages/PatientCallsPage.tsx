/* eslint-disable @typescript-eslint/no-explicit-any */
import { BadgeCheck, Brain, ChevronDown, Clock, Download, History, LineChart, MessageSquare, Phone, Smile, User } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { ErrorBox, Loading } from '../components/ui';
import { usePatientCalls } from '../lib/api';
import { fmtDay } from '../lib/format';

/** Qualivio's agent dashboard, organised by patient (call insights is patient-centred). Scores are mock values. */
export const AREAS: { key: string; label: string; short: string; icon: ReactNode; tone: string }[] = [
  { key: 'process_adherence', label: 'Process adherence', short: 'Process adherence', icon: <BadgeCheck className="h-5 w-5" />, tone: 'bg-violet-50 text-violet-600' },
  { key: 'behavioral', label: 'Behavioral', short: 'Behaviour', icon: <Brain className="h-5 w-5" />, tone: 'bg-crm-brand-light text-crm-brand' },
  { key: 'sentiment', label: 'Sentiment', short: 'Sentiment', icon: <Smile className="h-5 w-5" />, tone: 'bg-teal-50 text-crm-teal' },
  { key: 'communication', label: 'Communication', short: 'Communication', icon: <MessageSquare className="h-5 w-5" />, tone: 'bg-emerald-50 text-ok' },
  { key: 'compliance', label: 'Compliance', short: 'Compliance', icon: <BadgeCheck className="h-5 w-5" />, tone: 'bg-fuchsia-50 text-fuchsia-600' },
];

export const scoreTone = (v: number | null | undefined) =>
  v === null || v === undefined ? 'text-slate-400' : v >= 95 ? 'text-ok' : v >= 90 ? 'text-[#c98a0b]' : 'text-bad';

export const hms = (s: number) => {
  const t = Math.round(s), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return h ? `${h}h ${m}m` : `${m}m ${sec}s`;
};

export function ScoreLegend() {
  return (
    <span className="inline-flex items-center gap-3 rounded-lg bg-white px-3 py-1.5 text-[12px] text-slate-600 ring-1 ring-slate-200">
      <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-ok" />≥95%</span>
      <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-warn" />90–94%</span>
      <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-bad" />&lt;90%</span>
    </span>
  );
}

export default function PatientCallsPage() {
  const [patient, setPatient] = useState('');
  const { data, error } = usePatientCalls(patient);
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;

  const download = () => {
    const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const head = ['#', 'Patient', 'Case ID', 'Call', 'Date', 'With', 'Duration', 'Signals', ...AREAS.map((a) => `AI ${a.label}`)];
    const lines = [head.map(esc).join(',')];
    data.calls.forEach((c: any, i: number) => lines.push([i + 1, c.patient_name, c.case_id, c.external_call_id, c.date, c.party,
      hms(c.duration_s), c.signals, ...AREAS.map((a) => c.scores[a.key])].map(esc).join(',')));
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
    Object.assign(document.createElement('a'), { href: url, download: 'patient-calls.csv' }).click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4 px-8 pt-7 pb-5">
        <div>
          <h1 className="flex items-center gap-2.5 text-[26px] leading-tight font-bold tracking-tight text-app-navy">
            <User className="h-6 w-6 text-crm-orange" /> Conversation analysis
          </h1>
          <p className="mt-1.5 text-[15px] text-slate-600">{patient ? 'One patient' : 'All patients'} · call performance overview</p>
        </div>
        <label className="relative inline-flex items-center gap-2 rounded-lg bg-white px-3.5 py-2 text-[13px] font-semibold text-app-navy shadow-sm ring-1 ring-slate-200">
          {patient ? data.patients.find((p: any) => p.patient_id === patient)?.patient_name : 'All patients'}
          <ChevronDown className="h-4 w-4 opacity-60" />
          <select value={patient} onChange={(e) => setPatient(e.target.value)} className="absolute inset-0 cursor-pointer opacity-0">
            <option value="">All patients</option>
            {data.patients.map((p: any) => <option key={p.patient_id} value={p.patient_id}>{p.patient_name} · case {p.case_id}</option>)}
          </select>
        </label>
      </div>

      <div className="space-y-5 px-8 pb-8">
        <div className="grid gap-4 md:grid-cols-3">
          <Stat label="No of calls" value={data.count} sub="Total calls" icon={<Phone className="h-5 w-5" />} tone="bg-crm-orange-light text-crm-orange-dark" />
          <Stat label="Total duration" value={hms(data.total_seconds)} sub="Cumulative time" icon={<Clock className="h-5 w-5" />} tone="bg-crm-brand-light text-app-navy" />
          <Stat label="Avg duration" value={hms(data.avg_seconds)} sub="Per call average" icon={<Clock className="h-5 w-5" />} tone="bg-teal-50 text-crm-teal" />
        </div>

        <section className="card px-5 pt-5 pb-5">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-crm-brand-light text-crm-brand"><LineChart className="h-5 w-5" /></span>
            <div>
              <h2 className="text-[15px] font-bold tracking-wide text-app-navy uppercase">AI insights overview</h2>
              <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Automated performance assessment · demo scores</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
            {AREAS.map((a) => (
              <div key={a.key} className="relative overflow-hidden rounded-xl border border-slate-200 bg-white px-4 py-4">
                <span className="absolute -top-6 -right-6 h-16 w-16 rounded-full bg-crm-brand-light/60" />
                <div className="relative flex items-start justify-between">
                  <span className={`grid h-9 w-9 place-items-center rounded-lg ${a.tone}`}>{a.icon}</span>
                  <span className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">Score</span>
                </div>
                <div className="relative mt-3 text-[12px] font-bold tracking-wide text-slate-600 uppercase">{a.label}</div>
                <div className={`relative mt-1 text-[24px] font-bold tabular-nums ${scoreTone(data.scores[a.key])}`}>
                  {data.scores[a.key] ?? '—'}{data.scores[a.key] !== null && '%'}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="card overflow-hidden">
          <header className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <h2 className="flex items-center gap-2 text-[17px] font-bold text-app-navy"><History className="h-5 w-5" /> Call history</h2>
            <div className="flex items-center gap-4">
              <ScoreLegend />
              <span className="text-[13px] font-semibold text-slate-600">{data.count} calls</span>
              <button type="button" onClick={download} className="flex flex-col items-center text-[11px] font-semibold text-ok hover:opacity-80">
                <Download className="h-4 w-4" /> Download as CSV
              </button>
            </div>
          </header>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1080px] text-[13px]">
              <thead className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                <tr className="border-y border-slate-200">
                  {['#', 'Patient', 'Case ID', 'Action', 'Duration'].map((h) => <th key={h} rowSpan={2} className="px-3 py-3 text-left align-bottom">{h}</th>)}
                  <th colSpan={5} className="bg-crm-brand-light/70 px-4 py-2.5 text-center text-slate-600">AI feedback</th>
                  <th colSpan={5} className="bg-violet-50/70 px-4 py-2.5 text-center text-slate-600">QA feedback</th>
                </tr>
                <tr className="border-b border-slate-200">
                  {AREAS.map((a) => <th key={`ai-${a.key}`} className="bg-crm-brand-light/70 px-1.5 py-2.5 text-left">{a.short}</th>)}
                  {AREAS.map((a) => <th key={`qa-${a.key}`} className="bg-violet-50/70 px-1.5 py-2.5 text-left">{a.short}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.calls.map((c: any, i: number) => (
                  <tr key={c.call_id} className="hover:bg-slate-50">
                    <td className="px-3 py-3 text-slate-500 tabular-nums">{i + 1}</td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div className="font-semibold text-slate-800">{c.patient_name}</div>
                      <div className="text-[11px] text-slate-400">{c.external_call_id} · {fmtDay(c.date)} · {c.party.replace('Physician ', '').toLowerCase()}</div>
                    </td>
                    <td className="px-3 py-3 text-slate-600 tabular-nums">{c.case_id ?? '—'}</td>
                    <td className="px-3 py-3">
                      <Link to={`/conversation?callId=${c.call_id}`} className="font-bold tracking-wide text-crm-orange-dark hover:underline">VIEW</Link>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap text-slate-700 tabular-nums">{hms(c.duration_s)}</td>
                    {AREAS.map((a) => <td key={a.key} className={`bg-crm-brand-light/25 px-1.5 py-3 font-semibold tabular-nums ${scoreTone(c.scores[a.key])}`}>{c.scores[a.key]}%</td>)}
                    {AREAS.map((a) => <td key={a.key} className="bg-violet-50/30 px-1.5 py-3 text-slate-400">--</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-slate-100 px-5 py-2.5 text-[11.5px] text-slate-400 italic">
            AI feedback scores are demo values for this screen; QA feedback appears once a reviewer scores the call.
          </p>
        </section>
      </div>
    </>
  );
}

function Stat({ label, value, sub, icon, tone }: { label: string; value: ReactNode; sub: string; icon: ReactNode; tone: string }) {
  return (
    <div className="card flex items-start justify-between px-5 py-4">
      <div>
        <div className="text-[14px] text-slate-600">{label}</div>
        <div className="mt-1.5 text-[26px] leading-none font-bold text-app-navy tabular-nums">{value}</div>
        <div className="mt-2 text-[12px] text-slate-500">{sub}</div>
      </div>
      <span className={`grid h-10 w-10 place-items-center rounded-lg ${tone}`}>{icon}</span>
    </div>
  );
}
