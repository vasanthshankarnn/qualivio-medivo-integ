/* eslint-disable @typescript-eslint/no-explicit-any */
import { ChevronRight } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Legend, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Chips, ISSUE_STATUS, SearchBox, SectionTitle, Spark, Stat, StatusTag, useParam, vsArrow, vsTone } from '../components/kit';
import { ErrorBox, Loading, ScreenHeader, SourceNote } from '../components/ui';
import { useAccessIssues } from '../lib/api';
import { useFilters } from '../lib/filters';
import { plural } from '../lib/format';

/** Tab 3 · Emerging access issues: every access issue heard on calls, grouped by signal and compared with its own normal. */
export const CATEGORY_TONE: Record<string, string> = {
  'Payer & authorization': '#013476', Affordability: '#fe602f', 'Pharmacy & dispensing': '#7c3aed',
  'Paperwork & offices': '#0f7c80', 'Hub service': '#97a1b0',
};
const KIND_LABEL: Record<string, string> = { payer: 'Payer', pharmacy: 'Pharmacy', office: 'Office' };
const PAGE = 25;

export default function IssuesPage() {
  const { data, error } = useAccessIssues();
  const { qs } = useFilters();
  const navigate = useNavigate();
  const [cat, setCat] = useParam('category');
  const [status, setStatus] = useParam('status');
  const [kind, setKind] = useParam('kind');
  const [q, setQ] = useState('');
  const [all, setAll] = useState(false);
  const rows = useMemo(() => (data?.rows ?? []).filter((r: any) =>
    (!cat || r.category === cat) && (!status || (status === 'hot' ? ['New', 'Rising'].includes(r.status) : r.status === status))
    && (!kind || r.entity_kind === kind) && (!q || r.title.toLowerCase().includes(q.toLowerCase()))), [data, cat, status, kind, q]);
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const k = data.kpis;
  const count = (pred: (r: any) => boolean) => data.rows.filter((r: any) => (!cat || r.category === cat) && pred(r)).length;
  const shown = all ? rows : rows.slice(0, PAGE);
  const curWeeks = Math.max(1, Math.round(data.cur_days / 7));
  const weeks = data.weekly.map((w: any) => w.week);

  return (
    <>
      <ScreenHeader title="Emerging access issues"
        subtitle="Access issues heard on calls, against their normal. Click one for the detail." />
      <div className="space-y-5 px-8 pb-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          <Stat value={k.new} label="new this period" bar="bg-crm-orange" tone="text-crm-orange" sub="none in prior 13 weeks"
            onClick={() => setStatus('New')} />
          <Stat value={k.rising} label="rising above normal" bar="bg-bad" tone="text-bad" sub="well above normal" onClick={() => setStatus('Rising')} />
          <Stat value={k.patients} label="patients affected" bar="bg-crm-teal" sub="in new and rising issues" />
          <Stat value={k.payers + k.pharmacies + k.offices} label="payers, pharmacies, offices"
            sub={`${plural(k.payers, 'payer')} · ${plural(k.pharmacies, 'pharmacy', 'pharmacies')} · ${plural(k.offices, 'office')}`} />
          <Stat value={k.tracked} label="issues tracked" bar="bg-slate-500" sub={`${k.mentions.toLocaleString()} mentions · ${data.window}`}
            onClick={() => { setStatus(''); setCat(''); }} />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
          <section className="card px-5 pt-4 pb-3">
            <SectionTitle sub="By category · shaded = selected period">Mentions per week</SectionTitle>
            <div className="h-60">
              <ResponsiveContainer>
                <BarChart data={data.weekly} margin={{ top: 4, right: 8, left: -18, bottom: 0 }} barCategoryGap="22%">
                  <CartesianGrid vertical={false} stroke="#eef2f6" />
                  <XAxis dataKey="week" tick={{ fontSize: 11, fill: '#677284' }} tickLine={false} axisLine={false} interval={1} />
                  <YAxis tick={{ fontSize: 11, fill: '#677284' }} tickLine={false} axisLine={false} />
                  <ReferenceArea x1={weeks[weeks.length - curWeeks]} x2={weeks[weeks.length - 1]} fill="#fe602f" fillOpacity={0.06} />
                  <Tooltip cursor={{ fill: 'rgba(1,52,118,.05)' }} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  {Object.entries(CATEGORY_TONE).map(([c, color], i, arr) => (
                    <Bar key={c} dataKey={c} stackId="a" fill={color} opacity={cat && cat !== c ? 0.18 : 1} isAnimationActive={false}
                      radius={i === arr.length - 1 ? [3, 3, 0, 0] : 0} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="card px-5 pt-4 pb-4">
            <SectionTitle sub="Click to filter">By category</SectionTitle>
            <div className="space-y-2">
              {data.categories.map((c: any) => {
                const on = cat === c.category;
                return (
                  <button key={c.category} type="button" onClick={() => setCat(on ? '' : c.category)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left ring-1 transition ${on ? 'bg-app-navy/5 ring-app-navy' : 'ring-slate-200 hover:ring-app-navy/40'}`}>
                    <span className="h-8 w-1.5 rounded-full" style={{ background: CATEGORY_TONE[c.category] }} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[14px] font-semibold text-slate-800">{c.category}</span>
                      <span className="text-[12px] text-slate-500">{plural(c.issues, 'issue')} · {c.mentions.toLocaleString()} mentions</span>
                    </span>
                    {c.hot > 0 && <span className="rounded-full bg-[#fbe9e7] px-2.5 py-0.5 text-[12px] font-bold text-bad">{c.hot} emerging</span>}
                  </button>
                );
              })}
            </div>
          </section>
        </div>

        <section className="card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
            <div className="flex flex-wrap items-center gap-4">
              <Chips label="Status" value={status} onChange={setStatus} options={[
                { value: '', label: 'All', count: count(() => true) },
                { value: 'hot', label: 'Emerging', count: count((r) => ['New', 'Rising'].includes(r.status)) },
                ...['New', 'Rising', 'Steady', 'Easing'].map((s) => ({ value: s, label: s, count: count((r) => r.status === s), tone: ISSUE_STATUS[s].dot })),
              ]} />
              <Chips label="About" value={kind} onChange={setKind} options={[
                { value: '', label: 'Anyone' }, ...Object.entries(KIND_LABEL).map(([v, l]) => ({ value: v, label: l }))]} />
            </div>
            <SearchBox value={q} onChange={setQ} placeholder="Search payer, pharmacy, office, issue" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13.5px]">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11.5px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-2.5">Issue</th><th className="px-3 py-2.5">Status</th><th className="px-3 py-2.5 text-right">Mentions</th>
                  <th className="px-3 py-2.5">vs normal</th><th className="px-3 py-2.5">17-week trend</th><th className="px-3 py-2.5 text-right">Patients</th>
                  <th className="px-3 py-2.5">Programs</th><th className="px-3 py-2.5">Stage</th><th className="px-3 py-2.5">Suggested owner</th><th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((r: any) => (
                  <tr key={r.key} onClick={() => navigate(`/access-issues/${encodeURIComponent(r.key)}${qs}`)}
                    className="cursor-pointer transition hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <span className="h-7 w-1 rounded-full" style={{ background: CATEGORY_TONE[r.category] }} />
                        <div className="min-w-0">
                          <div className="font-semibold text-slate-800">{r.title}</div>
                          <div className="text-[11.5px] text-slate-500">{r.category}{r.entity_kind ? ` · ${KIND_LABEL[r.entity_kind]}` : ''}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3"><StatusTag status={r.status} /></td>
                    <td className="px-3 py-3 text-right font-semibold text-app-navy tabular-nums">{r.mentions}</td>
                    <td className={`px-3 py-3 font-semibold whitespace-nowrap ${vsTone(r.vs)}`}>{vsArrow(r.vs)}{r.vs}</td>
                    <td className="px-3 py-3"><Spark values={r.series} recent={curWeeks} /></td>
                    <td className="px-3 py-3 text-right tabular-nums">{r.patients}</td>
                    <td className="px-3 py-3 text-slate-600">{r.programs.join(', ')}</td>
                    <td className="px-3 py-3 whitespace-nowrap text-slate-600">{r.stage}</td>
                    <td className="px-3 py-3 whitespace-nowrap text-slate-600">{r.owner}</td>
                    <td className="pr-4"><ChevronRight className="h-4 w-4 text-slate-300" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="px-5 py-8 text-center text-sm text-slate-500">No issues match this selection.</p>}
          </div>
          {rows.length > PAGE && (
            <div className="border-t border-slate-100 px-5 py-3 text-center">
              <button type="button" onClick={() => setAll(!all)} className="text-[13px] font-semibold text-crm-orange-dark hover:underline">
                {all ? 'Show fewer' : `Show all ${rows.length} issues`}
              </button>
            </div>
          )}
        </section>
      </div>
      <SourceNote><b>Source:</b> access signals on each call. New = none in prior 13 weeks; rising = well above normal.</SourceNote>
    </>
  );
}
