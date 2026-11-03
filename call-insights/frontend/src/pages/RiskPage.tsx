/* eslint-disable @typescript-eslint/no-explicit-any */
import { ChevronRight } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useEvidence } from '../components/evidence';
import { BarList, Chips, LEVEL, LevelPill, SearchBox, SectionTitle, Stat, useParam } from '../components/kit';
import { ErrorBox, Loading, ScreenHeader, SourceNote } from '../components/ui';
import { useAtRisk } from '../lib/api';

/** Tab 4 · Patients at risk of dropping off: every patient whose calls carry drop-off signals, grouped by what was heard. */
const PAGE = 25;
const PHASES = [{ value: '', label: 'All patients' }, { value: 'before', label: 'Before first shipment' }, { value: 'on', label: 'On therapy (after first shipment)' }];

export default function RiskPage() {
  const { data, error } = useAtRisk();
  const navigate = useNavigate();
  const open = useEvidence();
  const [cat, setCat] = useParam('cat');
  const [level, setLevel] = useParam('level', 'flagged');
  const [phase, setPhase] = useParam('phase');
  const [q, setQ] = useState('');
  const [all, setAll] = useState(false);
  const rows = useMemo(() => (data?.patients ?? []).filter((p: any) =>
    (!cat || p.category_keys.includes(cat))
    && (level === 'any' || (level === 'flagged' ? p.level !== 'Low' : p.level === level))
    && (!phase || (phase === 'on' ? p.phase === 'On therapy' : p.phase !== 'On therapy'))
    && (!q || `${p.patient_name} ${p.case_id} ${p.payer ?? ''} ${p.office ?? ''}`.toLowerCase().includes(q.toLowerCase()))), [data, cat, level, phase, q]);
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const k = data.kpis;
  const levelCount = (l: string) => data.patients.filter((p: any) => (!cat || p.category_keys.includes(cat)) && (l === 'any' || (l === 'flagged' ? p.level !== 'Low' : p.level === l))).length;
  const shown = all ? rows : rows.slice(0, PAGE);
  const catLabel = data.categories.find((c: any) => c.key === cat)?.label;

  return (
    <>
      <ScreenHeader title="Patients at risk of dropping off"
        subtitle="Patients whose calls signal drop-off risk, grouped by what we heard, with the next step." />
      <div className="space-y-5 px-8 pb-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          <Stat value={k.flagged} label="patients at risk" bar="bg-crm-teal" tone="text-crm-teal" sub="high or medium" onClick={() => setLevel('flagged')} />
          <Stat value={k.high} label="high risk" bar="bg-bad" tone="text-bad" sub="act this week" onClick={() => setLevel('High')} />
          <Stat value={k.new_this_week} label="new this week" bar="bg-crm-orange" tone="text-crm-orange" sub="first signal this week" />
          <Stat value={k.on_therapy} label="on therapy" bar="bg-app-navy" sub="after first shipment" onClick={() => setPhase('on')} />
          <Stat value={k.before_start} label="not yet started" bar="bg-slate-500" sub="before first shipment" onClick={() => setPhase('before')} />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
          <section>
            <SectionTitle sub="Click to filter">What we are hearing</SectionTitle>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {data.categories.map((c: any) => {
                const on = cat === c.key;
                const diff = c.patients - c.before;  // everyone heard now vs the period before
                return (
                  <button key={c.key} type="button" onClick={() => setCat(on ? '' : c.key)}
                    className={`card flex flex-col px-4 py-3.5 text-left transition hover:-translate-y-0.5 hover:shadow-md ${on ? '!ring-2 !ring-crm-teal' : ''}`}>
                    <span className="text-[14px] font-semibold text-slate-800">{c.label}</span>
                    <span className="mt-2 flex items-baseline gap-2">
                      <span className="text-[30px] leading-none font-bold text-crm-teal tabular-nums">{c.flagged}</span>
                      <span className="text-[12.5px] text-slate-500">at risk · {c.patients} heard</span>
                      <span className={`ml-auto text-[12px] font-semibold ${diff > 0 ? 'text-bad' : diff < 0 ? 'text-ok' : 'text-slate-500'}`}
                        title="Patients who raised it now vs in the period before">
                        {diff > 0 ? '▲' : diff < 0 ? '▼' : '■'} {c.before} before
                      </span>
                    </span>
                    <span className="mt-2 text-[12px] leading-snug text-slate-500">{c.next_step}</span>
                    <span role="link" tabIndex={0} onClick={(e) => { e.stopPropagation(); open(`At risk: ${c.label}`, c.evidence); }}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); open(`At risk: ${c.label}`, c.evidence); } }}
                      className="mt-2 self-start text-[12px] font-semibold text-crm-orange-dark hover:underline">What they said ›</span>
                  </button>
                );
              })}
            </div>
          </section>
          <div className="space-y-5">
            <section className="card px-5 pt-4 pb-4">
              <SectionTitle>Where they are now</SectionTitle>
              <BarList items={data.by_stage} labelWidth="7.5rem" tone="bg-crm-teal" first="bg-crm-teal" />
            </section>
            <section className="card grid grid-cols-2 gap-5 px-5 pt-4 pb-4">
              <div><SectionTitle>By program</SectionTitle><BarList items={data.by_program} labelWidth="4.5rem" /></div>
              <div><SectionTitle>By payer</SectionTitle><BarList items={data.by_payer.slice(0, 5)} labelWidth="6.5rem" /></div>
            </section>
          </div>
        </div>

        <section className="card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
            <div className="flex flex-wrap items-center gap-4">
              <Chips label="Risk" value={level} onChange={setLevel} options={[
                { value: 'flagged', label: 'High + medium', count: levelCount('flagged') },
                ...['High', 'Medium', 'Low'].map((l) => ({ value: l, label: l, count: levelCount(l), tone: LEVEL[l].dot })),
                { value: 'any', label: 'Everyone heard', count: levelCount('any') }]} />
              <Chips label="Phase" value={phase} onChange={setPhase} options={PHASES} />
              {catLabel && (
                <button type="button" onClick={() => setCat('')} className="rounded-full bg-crm-teal px-3 py-1.5 text-[12.5px] font-semibold text-white">
                  {catLabel} ✕
                </button>
              )}
            </div>
            <SearchBox value={q} onChange={setQ} placeholder="Search patient, case, payer, office" />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13.5px]">
              <thead>
                <tr className="border-b border-slate-200 text-left text-[11.5px] font-bold tracking-wider text-slate-400 uppercase">
                  <th className="px-5 py-2.5">Patient</th><th className="px-3 py-2.5">Risk</th><th className="px-3 py-2.5">What we heard</th>
                  <th className="px-3 py-2.5">Latest words</th><th className="px-3 py-2.5">Stage now</th><th className="px-3 py-2.5">Last heard</th>
                  <th className="px-3 py-2.5">Suggested next step</th><th />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((p: any) => (
                  <tr key={p.patient_id} onClick={() => navigate(`/journey/${p.patient_id}`)} className="cursor-pointer align-top transition hover:bg-slate-50">
                    <td className="px-5 py-3 whitespace-nowrap">
                      <div className="font-semibold text-slate-800">{p.patient_name}</div>
                      <div className="text-[12px] text-slate-500">{p.drug} · case {p.case_id}{p.new_this_week && <span className="ml-1.5 font-semibold text-crm-orange-dark">· new</span>}</div>
                    </td>
                    <td className="px-3 py-3"><LevelPill level={p.level} /></td>
                    <td className="px-3 py-3">
                      <div className="flex max-w-[16rem] flex-wrap gap-1">
                        {p.categories.map((c: string) => <span key={c} className="rounded-md bg-teal-50 px-2 py-0.5 text-[11.5px] font-semibold text-crm-teal">{c}</span>)}
                      </div>
                    </td>
                    <td className="max-w-sm px-3 py-3 text-[13px] text-slate-700 italic">{p.quote ? `“${p.quote}”` : '—'}</td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <div>{p.stage_title}</div><div className="text-[11.5px] text-slate-500">{p.phase}</div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap text-slate-600">{p.last_heard_days === 0 ? 'today' : `${p.last_heard_days} d ago`}</td>
                    <td className="max-w-[15rem] px-3 py-3 text-[13px] text-slate-700">{p.next_step}</td>
                    <td className="pt-4 pr-4"><ChevronRight className="h-4 w-4 text-slate-300" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="px-5 py-8 text-center text-sm text-slate-500">No patients match this selection.</p>}
          </div>
          {rows.length > PAGE && (
            <div className="border-t border-slate-100 px-5 py-3 text-center">
              <button type="button" onClick={() => setAll(!all)} className="text-[13px] font-semibold text-crm-orange-dark hover:underline">
                {all ? 'Show fewer' : `Show all ${rows.length} patients`}
              </button>
            </div>
          )}
        </section>
      </div>
      <SourceNote><b>Source:</b> drop-off signals on each call. More worries = higher risk; support offered lowers it.</SourceNote>
    </>
  );
}
