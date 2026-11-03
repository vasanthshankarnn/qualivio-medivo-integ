/* eslint-disable @typescript-eslint/no-explicit-any */
import { ChevronDown, ChevronRight, Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { useEvidence } from '../components/evidence';
import { BandBadge, ErrorBox, Loading, OwnerMenu, ScreenHeader, SourceNote, StatusMenu, Useful } from '../components/ui';
import { Crumbs, Objective } from '../components/kit';
import { useJourney, usePatients } from '../lib/api';

/** v2 deck · Screen 4 Patient journey: one patient, every conversation in order – what happened, what they said, what to do next. */
const BAND_TONE: Record<string, string> = {
  green: 'bg-[#1e8e3e] text-white', amber: 'bg-[#e8a317] text-white', red: 'bg-[#c0392b] text-white', teal: 'bg-[#0f7c80] text-white',
  done: 'bg-[#1e8e3e] text-white', next: 'bg-slate-200 text-slate-500',
};

/** Deck band layout: stages heard on calls take width by days, stages with no calls a fixed slot. */
function useBandLayout(band: any[], todayDay: number) {
  const fixed = band.filter((b) => b.kind !== 'heard');
  const heard = band.filter((b) => b.kind === 'heard');
  const fixedEach = fixed.length ? Math.min(8, 45 / fixed.length) : 0;
  const heardTotal = 100 - fixedEach * fixed.length;
  const heardDays = heard.reduce((n, b) => n + Math.max(1, b.to - b.from), 0) || 1;
  let left = 0;
  const segs = band.map((b) => {
    const width = b.kind === 'heard' ? (heardTotal * Math.max(1, b.to - b.from)) / heardDays : fixedEach;
    const seg = { ...b, left, width };
    left += width;
    return seg;
  });
  const hs = segs.filter((s) => s.kind === 'heard');
  const x = (day: number) => {
    // a day on a boundary belongs to the stage that starts that day
    const s = hs.find((h) => day >= h.from && day < h.to) ?? hs.find((h) => day >= h.from && day <= h.to)
      ?? (day < (hs[0]?.from ?? 0) ? hs[0] : hs[hs.length - 1]);
    if (!s) return 0;
    const span = Math.max(1, s.to - s.from);
    return s.left + (Math.min(Math.max(day, s.from), s.to) - s.from) / span * s.width;
  };
  const ticks: { day: number; x: number }[] = [];
  for (let d = 0; d <= todayDay; d += 10) if (todayDay - d > 3 || d === 0) ticks.push({ day: d, x: x(d) });
  ticks.push({ day: todayDay, x: x(todayDay) });
  return { segs, x, ticks: ticks.filter((t, i, all) => i === 0 || t.x - all[i - 1].x > 4) };
}
const MOMENT_TONE: Record<string, { border: string; text: string; dot: string }> = {
  navy: { border: 'border-app-navy', text: 'text-app-navy', dot: 'border-app-navy' },
  orange: { border: 'border-crm-orange', text: 'text-crm-orange-dark', dot: 'border-crm-orange' },
  red: { border: 'border-bad', text: 'text-bad', dot: 'border-bad' },
};
const RISK_PILL: Record<string, string> = { red: 'bg-bad', amber: 'bg-warn', green: 'bg-ok' };

export default function JourneyPage() {
  const { patientId } = useParams();
  const patients = usePatients();
  const selected = patientId ?? patients.data?.[0]?.patient_id;
  const journey = useJourney(selected);

  return (
    <>
      <ScreenHeader title="Patient journey"
        subtitle="One patient, every conversation in order – what happened, what they said, and what to do next." />
      {journey.data && (
        <Crumbs items={[{ label: 'Executive summary', to: '/' }, { label: 'Patients at risk of dropping off', to: '/at-risk' },
          { label: journey.data.patient.drug?.toUpperCase() ?? 'No program' }, { label: journey.data.patient.patient_name }]} />
      )}
      <div className="space-y-5 px-8 pb-6">
        <PatientPicker patients={patients.data ?? []} selected={selected} />
        {(journey.isLoading || patients.isLoading) && <Loading />}
        {journey.error && <ErrorBox error={journey.error} />}
        {journey.data && <Journey key={selected} data={journey.data} />}
      </div>
      <SourceNote>Reached from Summary, the at-risk list, an emerging issue, alerts, or patient / case search. Texts, emails and faxes join the same timeline in Phase 2.</SourceNote>
    </>
  );
}

function PatientPicker({ patients, selected }: { patients: any[]; selected?: string }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  const list = patients.filter((x) => `${x.patient_name} ${x.case_id}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div ref={ref} className="relative inline-block">
      <button type="button" onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-2 rounded-lg bg-white px-3.5 py-2 text-[13px] font-semibold text-app-navy shadow-sm ring-1 ring-slate-200 hover:ring-app-navy/40">
        Change patient <ChevronDown className="h-4 w-4 opacity-60" />
        <span className="font-normal text-slate-400">· {patients.length} patients, highest risk first</span>
      </button>
      {open && (
        <div className="absolute z-40 mt-2 w-[36rem] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl">
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5">
            <Search className="h-4 w-4 text-slate-400" />
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search patient or case ID"
              className="w-full text-sm outline-none placeholder:text-slate-400" />
          </div>
          <div className="max-h-96 overflow-y-auto py-1">
            {list.map((x) => (
              <button key={x.patient_id} type="button" onClick={() => { navigate(`/journey/${x.patient_id}`); setOpen(false); }}
                className={`flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-slate-50 ${x.patient_id === selected ? 'bg-crm-brand-light/50' : ''}`}>
                <span>
                  <span className="text-sm font-semibold text-app-navy">{x.patient_name}</span>
                  <span className="block text-xs text-slate-500">case {x.case_id} · {x.drug ?? 'no program'} · {x.stage} · {x.calls} calls</span>
                </span>
                <span className="flex items-center gap-2">
                  {x.open_items > 0 && <span className="text-xs font-semibold text-crm-orange-dark">{x.open_items} open</span>}
                  {x.risk_band !== 'low' && <BandBadge band={x.risk_band} />}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Journey({ data }: { data: any }) {
  const p = data.patient;
  const open = useEvidence();
  const lay = useBandLayout(data.band, p.today_day);
  const next = data.next;
  const evidence = (callId: string, quote?: string, label?: string) => [{
    call_id: callId, external_call_id: data.timeline.find((t: any) => t.call_id === callId)?.external_call_id,
    date: data.timeline.find((t: any) => t.call_id === callId)?.date, patient_id: p.patient_id, patient_name: p.patient_name, quote, label }];

  return (
    <>
      <section className="card flex flex-wrap items-center gap-x-4 gap-y-2 px-6 py-4">
        <h2 className="text-[24px] font-semibold text-app-navy">{p.patient_name}</h2>
        <span className="text-[15px] text-slate-600">
          {[p.age, p.drug?.toUpperCase(), p.payer_name ?? 'payer not stated', [p.prescriber_name, p.practice_name].filter((v: any) => v && !String(v).startsWith('(')).join(', '),
            `case ${p.case_id}`, `Day ${p.today_day}`].filter((v) => v !== null && v !== undefined && v !== '').join(' · ')}
        </span>
        <span className={`ml-auto rounded-lg px-6 py-2.5 text-[15px] font-semibold text-white shadow-sm ${RISK_PILL[data.risk.tone]}`}>{data.risk.label}</span>
      </section>

      <section>
        <h2 className="mb-3 text-[18px] font-semibold text-app-navy">Their journey</h2>
        <div className="card px-6 pt-6 pb-5">
          <div className="relative h-12">
            {lay.segs.map((b: any) => (
              <div key={`${b.stage}-${b.from}-${b.kind}`}
                title={b.kind === 'heard' ? `${b.stage}: Day ${b.from}–${b.to}` : b.kind === 'passed' ? `${b.stage}: completed – no calls at this stage` : `${b.stage}: not reached yet`}
                className={`absolute top-0 flex h-12 items-center justify-center overflow-hidden border-r-2 border-white text-[13px] font-semibold ${BAND_TONE[b.tone]}`}
                style={{ left: `${b.left}%`, width: `${b.width}%` }}>
                <span className="truncate px-2">{b.title}{b.current ? ' – now' : ''}</span>
              </div>
            ))}
            {data.moments.map((m: any) => (
              <span key={m.call_id} className={`absolute -bottom-2 z-10 h-5 w-5 -translate-x-1/2 rounded-full border-[3px] bg-white ${MOMENT_TONE[m.tone].dot}`}
                style={{ left: `${lay.x(m.day)}%` }} />
            ))}
          </div>
          <div className="relative mt-3 h-5 text-[12px] text-slate-500">
            {lay.ticks.map((t: any) => <span key={t.day} className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${t.x}%` }}>Day {t.day}</span>)}
          </div>

          {data.moments.length > 0 && (
            <svg className="h-10 w-full" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden>
              {data.moments.map((m: any, i: number) => (
                <line key={m.call_id} x1={lay.x(m.day)} y1={0} x2={((i + 0.5) * 100) / data.moments.length} y2={10}
                  stroke={m.tone === 'navy' ? '#013476' : m.tone === 'red' ? '#c0392b' : '#fe602f'} strokeWidth={0.25} vectorEffect="non-scaling-stroke"
                  style={{ strokeWidth: 2 }} />
              ))}
            </svg>
          )}
          <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${Math.max(1, data.moments.length)}, minmax(0, 1fr))` }}>
            {data.moments.map((m: any) => {
              const t = MOMENT_TONE[m.tone];
              return (
                <Link key={m.call_id} to={`/conversation?callId=${m.call_id}`}
                  className={`block rounded-xl border-2 bg-white px-4 py-3 transition hover:-translate-y-0.5 hover:shadow-md ${t.border}`}>
                  <div className={`text-[14px] font-bold ${t.text}`}>Day {m.day} · {m.kind}</div>
                  {m.quote && <p className="mt-1 text-[14px] leading-snug text-slate-700 italic">“{m.quote}”</p>}
                  <div className="mt-1.5 text-[13px] font-bold text-app-navy">{m.tag}</div>
                </Link>
              );
            })}
            {data.moments.length === 0 && <p className="text-sm text-slate-500">Nothing stood out on this patient's calls.</p>}
          </div>
          <div className="mt-4 flex flex-wrap gap-4 text-[11.5px] text-slate-500">
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-[#1e8e3e]" />moving / completed</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-[#e8a317]" />friction heard</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-[#c0392b]" />stuck / denied</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-[#0f7c80]" />on therapy</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-slate-200" />not reached yet</span>
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className="card flex flex-col px-5 pt-4 pb-4">
          <h2 className="text-[17px] font-semibold text-app-navy">What to do next</h2>
          {next ? (
            <div className="mt-3 flex-1 space-y-3 text-[14px]">
              <p className="text-slate-700"><b className="text-crm-teal">Suggested:</b> {next.action}</p>
              <p className="text-[13px] text-slate-500">{next.detail}</p>
              <div className="flex flex-wrap items-center gap-x-1 gap-y-1 text-slate-600">
                <b className="text-app-navy">Owner:</b> <OwnerMenu insightKey={next.insight_key} owner={next.owner} />
                <span className="mx-2" />
                <b className="text-app-navy">Status:</b> <StatusMenu insightKey={next.insight_key} status={next.status} />
              </div>
              <Useful insightKey={next.insight_key} useful={next.useful} />
            </div>
          ) : data.risk_next ? (
            <div className="mt-3 flex-1 space-y-3 text-[14px]">
              <p className="text-slate-700"><b className="text-crm-teal">Suggested:</b> {data.risk_next.action}</p>
              <p className="text-[13px] text-slate-500">{data.risk_next.detail}</p>
              <p className="text-slate-600"><b className="text-app-navy">Owner:</b> {data.risk_next.owner}</p>
            </div>
          ) : <p className="mt-3 flex-1 text-[14px] text-slate-600">No open gap for this patient – nothing to do right now.</p>}
          <div className="mt-3 flex justify-end"><Objective n={3} label="Patients at risk" tone="teal" /></div>
        </section>

        <section className="card px-5 pt-4 pb-4">
          <h2 className="text-[17px] font-semibold text-app-navy">What the conversations show</h2>
          <ul className="mt-3 space-y-1.5">
            {data.show.map((s: any) => (
              <li key={s.text}>
                <button type="button" onClick={() => open(s.text, evidence(s.call_id, undefined, s.text))}
                  className="flex gap-2.5 text-left text-[14px] text-slate-700 hover:text-app-navy">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-500" />{s.text}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[13px] text-slate-500 italic">Every line links to the call behind it.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {data.timeline.map((t: any) => (
              <Link key={t.call_id} to={`/conversation?callId=${t.call_id}`}
                className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-600 hover:bg-crm-brand-light hover:text-app-navy">
                Day {t.day} · {t.external_call_id} <ChevronRight className="h-3 w-3" />
              </Link>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
