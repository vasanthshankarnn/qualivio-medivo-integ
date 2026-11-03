/* eslint-disable @typescript-eslint/no-explicit-any */
import { AlertCircle, ChevronRight, Star } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { useEvidence } from '../components/evidence';
import { Badge, Callout, Card, ErrorBox, KpiTile, Loading, ScreenHeader, SourceNote, HubSwitch } from '../components/ui';
import { useFollowThrough } from '../lib/api';
import { fmtDay, pctText, plural } from '../lib/format';

const SPLIT = [
  { key: 'talking', label: 'Talking', cls: 'bg-app-navy', dot: 'bg-app-navy' },
  { key: 'hold', label: 'Hold', cls: 'bg-crm-orange', dot: 'bg-crm-orange' },
  { key: 'silence', label: 'Silence', cls: 'bg-slate-300 text-slate-700', dot: 'bg-slate-300' },
  { key: 'transfer', label: 'Transfer', cls: 'bg-slate-600', dot: 'bg-slate-600' },
];
const STATUS_TONE: Record<string, string> = {
  kept: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  missed: 'bg-rose-50 text-rose-700 ring-rose-200',
  open: 'bg-sky-50 text-sky-700 ring-sky-200',
};

export default function FollowThroughPage() {
  const { data, error } = useFollowThrough();
  const open = useEvidence();
  const [reason, setReason] = useState<string | null>(null);
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const k = data.kpis;
  const withTime = data.by_reason.filter((r: any) => r.time.calls);
  const current = withTime.find((r: any) => r.reason === reason) ?? withTime[0];
  const split = current ? current.time : data.time_all;
  const comparison = Object.entries(data.close_comparison).map(([close, v]: [string, any]) => ({ close, days: v.avg_days_to_decision, calls: v.calls }));

  return (
    <>
      <ScreenHeader title="Follow-through & quality"
        subtitle="Why contacts repeat, where call time goes and where answers differ – measured by stage and process, not by agent." actions={<HubSwitch />} />
      <div className="space-y-5 px-8 pb-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          <KpiTile value={pctText(k.fcr.value)} label="first-contact resolution" vs={k.fcr.vs} invert accent />
          <KpiTile value={pctText(k.repeat.value)} label="contacts repeat ≤ 7 days" vs={k.repeat.vs} accent />
          <KpiTile value={pctText(k.promises.value)} label="promises kept" vs={k.promises.vs} invert accent partial
            sub={`${k.promises.kept} kept · ${k.promises.missed} missed`} />
          <KpiTile value={k.handoffs.of ? pctText(k.handoffs.value) : '—'} label="handoffs confirmed" vs={k.handoffs.of ? k.handoffs.vs : undefined}
            invert accent partial sub={k.handoffs.of ? plural(k.handoffs.of, 'handoff') : 'no handoffs in these calls'} />
          <KpiTile value={k.checks_missed.value} label="required checks missed" accent
            evidence={data.checks.flatMap((c: any) => c.evidence)} evidenceTitle="Required checks missed" />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <Card title="Why contacts repeat – by reason" subtitle="First-contact resolution and repeat contacts per contact reason · click a row for the calls" pad={false}>
            <div className="px-5 pb-4">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="bg-app-navy text-left text-white">
                    {['Contact reason', 'Calls', 'First contact', 'Repeat ≤7d', 'Root cause heard'].map((h) => (
                      <th key={h} className="px-3.5 py-2.5 text-xs font-semibold first:rounded-l-lg last:rounded-r-lg">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.by_reason.map((r: any, i: number) => (
                    <tr key={r.reason} onClick={() => { open(`Contact reason: ${r.reason}`, r.evidence); setReason(r.reason); }}
                      className={`cursor-pointer align-top hover:bg-slate-50 ${i === 0 ? 'bg-crm-orange-light/30' : ''}`}>
                      <td className={`px-3.5 py-3 font-semibold ${i === 0 ? 'text-crm-orange-dark' : 'text-app-navy'}`}>{r.reason}</td>
                      <td className="px-3.5 py-3 tabular-nums">{r.calls}</td>
                      <td className="px-3.5 py-3 tabular-nums">
                        <span className={i === 0 ? 'font-semibold text-crm-orange-dark' : ''}>{pctText(r.fcr)}</span>
                        {r.fcr_normal && r.fcr !== null && <span className="ml-1.5 text-[11px] text-slate-400">vs {r.fcr_normal}%</span>}
                      </td>
                      <td className="px-3.5 py-3 tabular-nums">
                        <span className={i === 0 ? 'font-semibold text-crm-orange-dark' : ''}>{pctText(r.repeat)}</span>
                        {r.repeat_normal && r.repeat !== null && <span className="ml-1.5 text-[11px] text-slate-400">vs {r.repeat_normal}%</span>}
                      </td>
                      <td className="max-w-[16rem] px-3.5 py-3 text-slate-600">{r.root_cause ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title={`Where call time goes${current ? ` · ${current.reason.toLowerCase()}` : ''}`}
            subtitle={`${split.minutes} min across ${plural(split.calls, 'live call')} · measured from the recording`}>
            <div className="flex h-11 overflow-hidden rounded-lg">
              {SPLIT.map((s) => split[s.key] > 0 && (
                <div key={s.key} className={`flex items-center justify-center text-[13px] font-bold text-white ${s.cls}`}
                  style={{ width: `${split[s.key]}%` }} title={`${s.label} ${split[s.key]}%`}>
                  {split[s.key] >= 6 ? `${split[s.key]}%` : ''}
                </div>
              ))}
            </div>
            <div className="mt-2.5 flex flex-wrap gap-4 text-xs text-slate-600">
              {SPLIT.map((s) => (
                <span key={s.key} className="inline-flex items-center gap-1.5">
                  <span className={`h-2.5 w-2.5 rounded-sm ${s.dot}`} />{s.label} {split[s.key]}%
                </span>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {withTime.map((r: any) => (
                <button key={r.reason} type="button" onClick={() => setReason(r.reason)}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium ring-1 transition ${current?.reason === r.reason ? 'bg-app-navy text-white ring-app-navy' : 'text-slate-600 ring-slate-200 hover:bg-slate-50'}`}>
                  {r.reason}
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500 italic">
              Hold and transfer are found from the conversation; silence is the time nobody is speaking. After-call work needs phone-system data.
            </p>
          </Card>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <section className="card overflow-hidden">
            <header className="bg-crm-orange-light/70 px-5 py-3.5">
              <div className="text-[15px] font-semibold text-crm-orange-dark">Flagged for follow-through (all patients)</div>
              <div className="text-xs text-slate-500">Loops left open after a contact · opens the patient journey</div>
            </header>
            <div className="divide-y divide-slate-100">
              {data.flagged.length === 0 && <p className="px-5 py-4 text-sm text-slate-500">Nothing left open.</p>}
              {data.flagged.map((f: any, i: number) => (
                <Link key={i} to={f.patient_id ? `/journey/${f.patient_id}` : `/calls/${f.call_id}`}
                  className="grid grid-cols-[9.5rem_10rem_1fr_1rem] items-start gap-3 px-5 py-3 text-[13px] transition hover:bg-slate-50">
                  <span className="font-semibold text-app-navy">
                    {f.kind === 'Drop-off risk' && <Star className="mr-1 mb-0.5 inline h-3.5 w-3.5 fill-crm-orange text-crm-orange" />}{f.kind}
                  </span>
                  <span className="text-slate-600">
                    <span className="font-medium text-slate-800">{f.patient_name ?? '—'}</span>
                    <span className="block text-xs text-slate-400">{f.external_call_id} · {fmtDay(f.date)}</span>
                  </span>
                  <span className="text-slate-700">{f.text}</span>
                  <ChevronRight className="mt-0.5 h-4 w-4 text-slate-300" />
                </Link>
              ))}
              <div className="px-5 py-3 text-xs text-slate-400">Unanswered texts and emails · Phase 2</div>
            </div>
          </section>

          <Card title="Consistency & compliance">
            <div className="space-y-4 text-[13px]">
              <div>
                <div className="font-semibold text-crm-orange-dark">Same question, different answers</div>
                {data.same_question.length === 0 ? <p className="mt-1 text-slate-500">No differences between what payers require and what offices were told.</p> :
                  data.same_question.map((s: any) => (
                    <button key={s.subject_id} type="button" onClick={() => open(`Asked vs told · case ${s.subject_id}`, s.evidence)}
                      className="mt-1.5 block w-full rounded-lg bg-slate-50 px-3 py-2 text-left text-slate-700 hover:bg-slate-100">
                      <span className="font-semibold text-app-navy">{s.patient?.patient_name ?? `Case ${s.subject_id}`}</span>
                      {s.band && <Badge tone="ml-1.5 bg-amber-50 text-amber-700 ring-amber-200">{s.band}</Badge>}
                      <span className="mt-0.5 block text-slate-600">{s.detail}</span>
                    </button>
                  ))}
                <p className="mt-1.5 text-xs text-slate-500">→ update the payer guide / knowledge article the hub answers from</p>
              </div>
              <div>
                <div className="font-semibold text-app-navy">Required checks</div>
                <div className="mt-1 space-y-1">
                  {data.checks.map((c: any) => (
                    <button key={c.label} type="button" disabled={!c.count} onClick={() => open(c.label, c.evidence)}
                      className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left ${c.count ? 'hover:bg-slate-50' : ''}`}>
                      <span className={c.count ? 'text-slate-700' : 'text-slate-400'}>{c.label}</span>
                      <span className={`font-bold tabular-nums ${c.count ? 'text-crm-orange-dark' : 'text-slate-300'}`}>{c.count}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="font-semibold text-app-navy">Risk-based QA</div>
                <p className="text-xs text-slate-500">Review sample weighted to high-risk calls</p>
                <div className="mt-1.5 space-y-1">
                  {data.qa_sample.map((q: any) => (
                    <Link key={q.call_id} to={`/calls/${q.call_id}`} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-50">
                      <span className="w-12 font-mono text-xs text-slate-500">{q.external_call_id}</span>
                      <span className="w-28 truncate font-medium text-slate-800">{q.patient_name}</span>
                      <span className="flex-1 truncate text-xs text-slate-500">{q.why.join(' · ')}</span>
                      <AlertCircle className={`h-3.5 w-3.5 ${q.score >= 5 ? 'text-crm-orange' : 'text-slate-300'}`} />
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <Card title="How the PA call ends → time to decision" subtitle={data.milestones_note}>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={comparison} margin={{ left: -12, right: 12, top: 8 }}>
                  <CartesianGrid stroke="#eef2f6" vertical={false} />
                  <XAxis dataKey="close" tick={{ fontSize: 12, fill: '#677284' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 12, fill: '#677284' }} unit="d" tickLine={false} axisLine={false} />
                  <Tooltip formatter={(v) => [`${v} days`, 'Avg. call → PA decision']} />
                  <Bar dataKey="days" radius={[5, 5, 0, 0]} maxBarSize={70} isAnimationActive={false}>
                    {comparison.map((c) => <Cell key={c.close} fill={c.close === 'Generic' ? '#fe602f' : '#013476'} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-1 text-xs text-slate-500">Recap of the exact documents + a confirmed date vs “let us know if you need anything”.</p>
          </Card>
          <Card title="Promises made on calls" subtitle="Rule R6: kept if a matching contact on the same case happens by the promised date" pad={false}>
            <div className="scroll-quiet max-h-72 overflow-y-auto px-5 pb-4">
              <table className="w-full text-[13px]">
                <thead className="sticky top-0 bg-white text-left text-xs text-slate-500">
                  <tr>{['Call', 'Patient', 'Promise', 'Due', 'Status'].map((h) => <th key={h} className="py-2 pr-3 font-semibold">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.promises.map((p: any) => (
                    <tr key={`${p.call_id}-${p.quote}`} className="align-top">
                      <td className="py-2 pr-3"><Link to={`/calls/${p.call_id}`} className="link font-mono text-xs">{p.external_call_id}</Link></td>
                      <td className="py-2 pr-3 whitespace-nowrap">{p.patient_name}</td>
                      <td className="py-2 pr-3 text-slate-700">{p.action}</td>
                      <td className="py-2 pr-3 whitespace-nowrap text-slate-500">{p.due_text ?? (p.due_date ? fmtDay(p.due_date) : '—')}</td>
                      <td className="py-2"><Badge tone={STATUS_TONE[p.status]}>{p.status}{p.kept_by ? ` · ${p.kept_by}` : ''}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        <Callout tone="slate">
          <b className="text-app-navy">Guardrail:</b> no agent scorecards or coaching workflows. Findings are grouped by stage, reason and process so
          Ipsen can fix the process; every row opens its evidence.
        </Callout>
      </div>
      <SourceNote><b>From calls today:</b> first-contact resolution, repeat reasons, call-time split, consistency and compliance checks.</SourceNote>
    </>
  );
}
