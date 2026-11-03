/* eslint-disable @typescript-eslint/no-explicit-any */
import { Quote } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { useEvidence } from '../components/evidence';
import { BarList, Chips, SectionTitle, Stat, useParam, vsArrow, vsTone } from '../components/kit';
import { ErrorBox, Loading, ScreenHeader, SourceNote } from '../components/ui';
import { useCallSummary } from '../lib/api';
import { fmtDate, lowerFirst, pctText } from '../lib/format';

/** Tab 5 · Call summary: every conversation categorised by why the patient or office called, and what sits behind it. */
const PARTIES = ['Patients & caregivers', 'Offices', 'Payers', 'Pharmacies'];

export default function CallSummaryPage() {
  const [direction, setDirection] = useParam('direction');
  const [party, setParty] = useParam('party');
  const [reason, setReason] = useParam('reason');
  const { data, error } = useCallSummary(direction, party);
  const open = useEvidence();
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const k = data.kpis;
  const sel = data.reasons.find((r: any) => r.reason === reason) ?? data.reasons[0];
  const maxShare = Math.max(1, ...data.reasons.map((r: any) => r.share));
  const chart = data.weeks.map((w: string, i: number) => ({ week: w, calls: sel?.series[i] ?? 0 }));
  const fcrBelow = k.fcr !== null && k.fcr_target && k.fcr < k.fcr_target;

  return (
    <>
      <ScreenHeader title="Call summary"
        subtitle="Why patients and offices call, and what's behind each reason." />
      <div className="space-y-5 px-8 pb-6">
        <div className="flex flex-wrap items-center gap-5 rounded-xl bg-white px-4 py-2.5 ring-1 ring-slate-200">
          <Chips label="Direction" value={direction} onChange={setDirection} options={[{ value: '', label: 'All calls' }, { value: 'inbound', label: 'Inbound' }, { value: 'outbound', label: 'Outbound' }]} />
          <Chips label="With" value={party} onChange={setParty} options={[{ value: '', label: 'Everyone' }, ...PARTIES.map((p) => ({ value: p, label: p }))]} />
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          <Stat value={k.calls.toLocaleString()} label="calls" sub={k.change_pct !== null ? `${k.change_pct >= 0 ? '▲' : '▼'} ${Math.abs(k.change_pct)}% vs previous period` : `${k.patients.toLocaleString()} patients`} />
          <Stat value={pctText(k.inbound)} label="inbound" bar="bg-crm-brand" />
          <Stat value={pctText(k.fcr)} label="first-call resolution" bar={fcrBelow ? 'bg-warn' : 'bg-ok'}
            tone={fcrBelow ? 'text-[#b47b06]' : 'text-app-navy'} sub={k.fcr_target ? `target ${k.fcr_target}% · normal ${k.fcr_normal}%` : undefined} />
          <Stat value={`${k.minutes} min`} label="average call" bar="bg-slate-500" />
          <Stat value={pctText(k.repeat)} label="repeat calls (7 days)" bar="bg-slate-500" sub={k.repeat_normal !== null ? `normal ${k.repeat_normal}%` : undefined} />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.45fr)]">
          <section className="card px-5 pt-4 pb-4">
            <SectionTitle sub="Share of calls · ▲▼ vs normal">Why they called</SectionTitle>
            <ul className="space-y-1">
              {data.reasons.map((r: any) => {
                const on = r.reason === sel?.reason;
                return (
                  <li key={r.reason}>
                    <button type="button" onClick={() => setReason(r.reason)}
                      className={`w-full rounded-lg px-3 py-2.5 text-left transition ${on ? 'bg-app-navy/[.06] ring-1 ring-app-navy/30' : 'hover:bg-slate-50'}`}>
                      <span className="flex items-baseline justify-between gap-3">
                        <span className={`text-[14px] ${on ? 'font-semibold text-app-navy' : 'text-slate-800'}`}>{r.reason}</span>
                        <span className="text-[13px] font-semibold text-app-navy tabular-nums">{r.calls.toLocaleString()}</span>
                      </span>
                      <span className="mt-1.5 flex items-center gap-3">
                        <span className="h-2.5 flex-1 rounded-full bg-slate-100">
                          <span className={`block h-2.5 rounded-full ${on ? 'bg-crm-orange' : 'bg-app-navy'}`} style={{ width: `${(100 * r.share) / maxShare}%` }} />
                        </span>
                        <span className="w-10 text-right text-[12px] text-slate-600 tabular-nums">{r.share}%</span>
                        <span className={`w-14 text-right text-[12px] font-semibold tabular-nums ${r.delta >= 3 ? 'text-bad' : r.delta <= -3 ? 'text-ok' : 'text-slate-400'}`}>
                          {r.delta === null ? '' : r.delta >= 1 ? `▲ ${r.delta} pt` : r.delta <= -1 ? `▼ ${Math.abs(r.delta)} pt` : '■'}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="mt-4 border-t border-slate-100 pt-3">
              <div className="mb-2 text-[11.5px] font-bold tracking-wider text-slate-400 uppercase">Who the calls were with</div>
              <div className="flex flex-wrap gap-2">
                {data.parties.map((p: any) => (
                  <span key={p.name} className="rounded-md bg-slate-50 px-2.5 py-1 text-[12.5px] text-slate-700 ring-1 ring-slate-200">
                    {p.name} <b className="text-app-navy tabular-nums">{p.calls.toLocaleString()}</b>
                  </span>
                ))}
              </div>
            </div>
          </section>

          {sel && (
            <section className="card overflow-hidden">
              <div className="border-b border-slate-100 bg-slate-50/70 px-5 py-3.5">
                <h2 className="text-[18px] font-semibold text-app-navy">{sel.reason}</h2>
                <p className="mt-0.5 text-[13px] text-slate-600">
                  {sel.calls.toLocaleString()} calls · {sel.share}% of conversations{sel.normal !== null ? ` (normal ${sel.normal}%)` : ''} · {pctText(sel.inbound)} inbound ·
                  {' '}{pctText(sel.fcr)} solved first time · {sel.minutes} min average
                </p>
              </div>
              <div className="px-5 pt-3">
                <div className="h-36">
                  <ResponsiveContainer>
                    <AreaChart data={chart} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
                      <defs>
                        <linearGradient id="reasonFill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#fe602f" stopOpacity={0.35} /><stop offset="100%" stopColor="#fe602f" stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid vertical={false} stroke="#eef2f6" />
                      <XAxis dataKey="week" tick={{ fontSize: 10.5, fill: '#677284' }} tickLine={false} axisLine={false} interval={2} />
                      <YAxis tick={{ fontSize: 10.5, fill: '#677284' }} tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                      <Area dataKey="calls" name="Calls per week" isAnimationActive={false} stroke="#fe602f" strokeWidth={2} fill="url(#reasonFill)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="grid gap-6 px-5 pt-3 pb-4 lg:grid-cols-2">
                <div>
                  <SectionTitle>Inside {lowerFirst(sel.reason)}</SectionTitle>
                  <BarList items={sel.subs.map((s: any) => ({ ...s, count: s.calls }))} labelWidth="11.5rem"
                    suffix={(s: any) => <span>{s.share}%<span className="ml-1.5 font-normal text-slate-400">{s.fcr !== null ? `FCR ${s.fcr}%` : ''}</span></span>} />
                </div>
                <div>
                  <SectionTitle sub="Share · vs normal">By {sel.entity_label.toLowerCase()}</SectionTitle>
                  <table className="w-full text-[13px]">
                    <tbody className="divide-y divide-slate-100">
                      {sel.entities.map((e: any) => (
                        <tr key={e.name}>
                          <td className="py-2 pr-2 text-slate-800">{e.name}</td>
                          <td className="py-2 text-right font-semibold text-app-navy tabular-nums">{e.calls}</td>
                          <td className="py-2 pl-3 text-right text-slate-500 tabular-nums">{e.share}%</td>
                          <td className={`py-2 pl-3 text-right font-semibold whitespace-nowrap ${vsTone(e.vs)}`}>{vsArrow(e.vs)}{e.vs}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              {sel.issues.length > 0 && (
                <div className="border-t border-slate-100 px-5 py-3.5">
                  <div className="mb-2 text-[11.5px] font-bold tracking-wider text-slate-400 uppercase">Signals heard on these calls</div>
                  <div className="flex flex-wrap gap-2">
                    {sel.issues.map((i: any) => (
                      <span key={i.name} className="rounded-full bg-crm-orange-light px-3 py-1 text-[12.5px] font-semibold text-crm-orange-dark">{i.name} · {i.count}</span>
                    ))}
                  </div>
                </div>
              )}
              <div className="border-t border-slate-100 bg-slate-50/50 px-5 py-4">
                <div className="mb-2.5 flex items-center justify-between">
                  <span className="text-[11.5px] font-bold tracking-wider text-slate-400 uppercase">Sample calls</span>
                  <button type="button" onClick={() => open(`Why they called: ${sel.reason}`, sel.evidence)} className="text-[13px] font-semibold text-crm-orange-dark hover:underline">All excerpts ›</button>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {sel.evidence.filter((e: any, i: number, all: any[]) => all.findIndex((x: any) => x.quote === e.quote) === i).slice(0, 4).map((e: any) => (
                    <div key={e.call_id} className="rounded-lg bg-white px-3.5 py-2.5 shadow-sm ring-1 ring-slate-100">
                      <span className="block text-[11px] font-semibold tracking-wide text-crm-orange-dark uppercase">{e.label}</span>
                      <p className="mt-1 flex gap-2 text-[13px] text-slate-700"><Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-300" />{e.quote}</p>
                      <span className="mt-1 block text-[11.5px] text-slate-500">{fmtDate(e.date)} · {e.party}{e.patient_name ? ` · ${e.patient_name}` : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
      <SourceNote><b>Source:</b> reason, outcome and length of each call.</SourceNote>
    </>
  );
}
