/* eslint-disable @typescript-eslint/no-explicit-any */
import { ArrowLeft, ChevronRight, Lightbulb, Quote, UserRound } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { useEvidence } from '../components/evidence';
import { BarList, Crumbs, SectionTitle, Stat, StatusTag, vsArrow, vsTone } from '../components/kit';
import { ErrorBox, Loading, SourceNote } from '../components/ui';
import { useAccessIssue } from '../lib/api';
import { useFilters } from '../lib/filters';
import { fmtDate, pctText } from '../lib/format';
import { CATEGORY_TONE } from './IssuesPage';

/** Tab 3 drill-down: one emerging issue – why it was flagged, where it comes from, who it affects, in their words. */
export default function IssueDetailPage() {
  const { key } = useParams();
  const { data, error, isLoading } = useAccessIssue(key);
  const { qs } = useFilters();
  const open = useEvidence();
  if (isLoading) return <Loading />;
  if (!data) return (
    <div className="space-y-4 px-8 py-8">
      <ErrorBox error={error ?? 'Issue not found'} />
      <Link to={`/access-issues${qs}`} className="inline-flex items-center gap-1 text-sm font-semibold text-crm-orange-dark hover:underline">
        <ArrowLeft className="h-4 w-4" /> Back to all issues
      </Link>
    </div>
  );
  const b = data.breakdowns;
  const curWeeks = Math.max(1, Math.round(data.cur_days / 7));
  const chart = data.weeks.map((w: string, i: number) => ({ week: w, mentions: data.series[i], normal: data.normal_per_week }));
  // the fourth breakdown depends on what the issue is about
  const where = data.entity_kind === 'office'
    ? { title: 'Payers involved', items: b.payer }
    : data.entity_kind === 'pharmacy' ? { title: 'Payers of these patients', items: b.payer } : { title: 'Offices involved', items: b.office };

  return (
    <>
      <div className="pt-6"><Crumbs items={[{ label: 'Executive summary', to: `/${qs}` }, { label: 'Emerging access issues', to: `/access-issues${qs}` }, { label: data.title }]} /></div>
      <div className="space-y-5 px-8 pb-6">
        <section className="card overflow-hidden">
          <div className="h-1.5" style={{ background: CATEGORY_TONE[data.category] }} />
          <div className="flex flex-wrap items-start justify-between gap-5 px-6 py-5">
            <div className="min-w-0 max-w-3xl">
              <div className="flex flex-wrap items-center gap-2.5">
                <StatusTag status={data.status} />
                <span className="text-[12.5px] font-semibold text-slate-500">{data.category}</span>
                {data.programs.length > 0 && <span className="text-[12.5px] text-slate-400">· {data.programs.join(', ')}</span>}
              </div>
              <h1 className="mt-2 text-[26px] leading-tight font-semibold tracking-tight text-app-navy">{data.title}</h1>
              <p className="mt-2 text-[15px] text-slate-700"><b className="text-app-navy">Why flagged: </b>{data.why}</p>
              <p className="mt-1 text-[14px] text-slate-600 italic">{data.meaning}.</p>
            </div>
            <div className="w-full max-w-sm rounded-xl bg-crm-orange-light/60 px-4 py-3.5 ring-1 ring-orange-100">
              <div className="flex items-center gap-2 text-[12px] font-bold tracking-wider text-crm-orange-dark uppercase">
                <Lightbulb className="h-4 w-4" /> Suggested next step
              </div>
              <p className="mt-1.5 text-[14px] text-slate-800">{data.action}</p>
              <p className="mt-1.5 text-[12.5px] text-slate-500">Suggested owner: <b className="text-slate-700">{data.owner}</b></p>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          <Stat value={data.mentions} label={`mentions · ${data.window}`} bar="bg-crm-orange" tone="text-crm-orange"
            onClick={() => open(data.title, data.evidence)} />
          <Stat value={<span className={vsTone(data.vs)}>{vsArrow(data.vs)}{data.vs}</span>} label="vs normal"
            sub={`normally ~${data.normal_per_week} a week`} bar="bg-bad" />
          <Stat value={data.patients} label="patients affected" bar="bg-crm-teal" />
          <Stat value={pctText(data.unresolved_pct)} label="left unresolved" bar="bg-slate-500" />
          <Stat value={data.first_heard ? fmtDate(data.first_heard) : '—'} label="first heard" bar="bg-slate-500" />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <section className="card px-5 pt-4 pb-3">
            <SectionTitle sub="Per week · dashed = normal · shaded = period">Trend</SectionTitle>
            <div className="h-56">
              <ResponsiveContainer>
                <ComposedChart data={chart} margin={{ top: 6, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#eef2f6" />
                  <XAxis dataKey="week" tick={{ fontSize: 11, fill: '#677284' }} tickLine={false} axisLine={false} interval={1} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#677284' }} tickLine={false} axisLine={false} />
                  <ReferenceArea x1={chart[chart.length - curWeeks]?.week} x2={chart[chart.length - 1]?.week} fill="#fe602f" fillOpacity={0.07} />
                  <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                  <Bar dataKey="mentions" name="Mentions" isAnimationActive={false} fill={CATEGORY_TONE[data.category] ?? '#013476'} radius={[3, 3, 0, 0]} />
                  <Line dataKey="normal" name="Normal" isAnimationActive={false} stroke="#c0392b" strokeDasharray="5 4" dot={false} strokeWidth={1.5} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="card px-5 pt-4 pb-4">
            <SectionTitle
              right={<button type="button" onClick={() => open(data.title, data.evidence)} className="text-[13px] font-semibold text-crm-orange-dark hover:underline">All excerpts ›</button>}>
              In their words
            </SectionTitle>
            <ul className="space-y-2.5">
              {data.evidence.filter((e: any, i: number, all: any[]) => e.quote && all.findIndex((x: any) => x.quote === e.quote) === i).slice(0, 4).map((e: any) => (
                <li key={e.call_id} className="rounded-lg bg-slate-50 px-3.5 py-2.5">
                  <p className="flex gap-2 text-[13.5px] text-slate-700 italic"><Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-crm-orange" />{e.quote}</p>
                  <p className="mt-1 text-[11.5px] text-slate-500">{fmtDate(e.date)} · {e.party}{e.patient_name ? ` · ${e.patient_name}` : ''}</p>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {[{ title: 'By program', items: b.program }, { title: 'By journey stage', items: b.stage }, where, { title: 'Who raised it', items: b.who }].map((x) => (
            <section key={x.title} className="card px-5 pt-4 pb-4">
              <SectionTitle>{x.title}</SectionTitle>
              <BarList items={x.items} labelWidth="8.5rem" suffix={(i: any) => `${i.share}%`} />
            </section>
          ))}
        </div>

        <section className="card">
          <div className="px-5 pt-4"><SectionTitle sub="Click a patient for the journey">Patients affected</SectionTitle></div>
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="border-y border-slate-200 bg-slate-50/60 text-left text-[11.5px] font-bold tracking-wider text-slate-400 uppercase">
                <th className="px-5 py-2.5">Patient</th><th className="px-3 py-2.5">Program</th><th className="px-3 py-2.5">Stage</th>
                <th className="px-3 py-2.5">Office</th><th className="px-3 py-2.5">Last heard</th><th className="px-3 py-2.5">What they said</th><th />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.patients_list.map((p: any) => (
                <tr key={p.patient_id} className="hover:bg-slate-50">
                  <td className="px-5 py-3 whitespace-nowrap">
                    <Link to={`/journey/${p.patient_id}`} className="inline-flex items-center gap-2 font-semibold text-slate-800 hover:text-app-navy hover:underline">
                      <UserRound className="h-4 w-4 text-slate-400" />{p.patient_name}
                    </Link>
                    <span className="ml-1.5 text-[12px] text-slate-500">case {p.case_id}</span>
                  </td>
                  <td className="px-3 py-3">{p.drug}</td>
                  <td className="px-3 py-3 whitespace-nowrap">{p.stage}</td>
                  <td className="px-3 py-3 text-slate-600">{p.office}</td>
                  <td className="px-3 py-3 whitespace-nowrap text-slate-600">{fmtDate(p.last_heard)}</td>
                  <td className="max-w-md px-3 py-3 text-slate-700 italic">{p.quote ? `“${p.quote}”` : '—'}</td>
                  <td className="pr-4"><Link to={`/journey/${p.patient_id}`}><ChevronRight className="h-4 w-4 text-slate-300" /></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {data.related.length > 0 && (
          <section className="card px-5 pt-4 pb-4">
            <SectionTitle>Also heard about {data.entity}</SectionTitle>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {data.related.map((r: any) => (
                <Link key={r.key} to={`/access-issues/${encodeURIComponent(r.key)}${qs}`}
                  className="rounded-lg px-3.5 py-3 ring-1 ring-slate-200 transition hover:ring-app-navy/40">
                  <div className="flex items-center justify-between gap-2"><StatusTag status={r.status} />
                    <span className={`text-[12.5px] font-semibold ${vsTone(r.vs)}`}>{vsArrow(r.vs)}{r.vs}</span></div>
                  <div className="mt-2 text-[13.5px] font-semibold text-slate-800">{r.title}</div>
                  <div className="text-[12px] text-slate-500">{r.mentions} mentions · {r.category}</div>
                </Link>
              ))}
            </div>
          </section>
        )}
      </div>
      <SourceNote><b>Source:</b> every mention of this issue in the period.</SourceNote>
    </>
  );
}
