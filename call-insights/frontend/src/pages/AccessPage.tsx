/* eslint-disable @typescript-eslint/no-explicit-any */
import { CalendarClock, Database, Download, MessageSquareQuote, ShieldCheck, TrendingUp } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { useEvidence } from '../components/evidence';
import { Callout, Card, EmptyState, ErrorBox, Loading, ScreenHeader, SourceNote, StatusMenu, StatusPill } from '../components/ui';
import { useAccess, useUpdateAction } from '../lib/api';
import { PARTY_COLOR, fmtDay, plural } from '../lib/format';

export default function AccessPage({ focus }: { focus?: 'stages' }) {
  const { data, error } = useAccess();
  const loaded = !!data;
  useEffect(() => {  // the Stages tab opens this screen at its stage heat map
    if (focus !== 'stages' || !loaded) return;
    const id = window.setTimeout(() => document.getElementById('stages')?.scrollIntoView({ block: 'start' }), 60);
    return () => window.clearTimeout(id);
  }, [focus, loaded]);
  const open = useEvidence();
  const [selected, setSelected] = useState<string | null>(null);
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const rows: any[] = data.rows;
  const chartRow = rows.find((r) => r.key === selected) ?? rows.find((r) => r.kind === 'practice' || r.kind === 'payer') ?? rows[0];

  return (
    <>
      <ScreenHeader title="Access & friction"
        subtitle="Emerging access issues spotted early: where and why patients and physician offices get stuck, compared with each payer's and office's normal – and whether the fix worked."
        actions={<><ExportButton rows={rows} /><InfoButton icon={<CalendarClock className="h-4 w-4" />} label="Schedule"
          text="Email this view (or the weekly brief) every Monday at 7 am to the owners Ipsen chooses. Recipients and thresholds are set with Ipsen during implementation." />
          <InfoButton icon={<Database className="h-4 w-4" />} label="Data feed"
            text="Daily feed of signals, insights and statuses to Ipsen's data platform (file drop, Snowflake share or API). Configured in implementation; CRM write-back is Phase 2." /></>} />

      <div className="space-y-5 px-8 pb-6">
        <Card title="Signals in conversations → what they often mean"
          subtitle="Compared with the 13-week baseline · click a row to chart it · status is shared with the team"
          right={<span className="text-xs text-slate-400">{plural(rows.length, 'pattern')}</span>} pad={false}>
          {rows.length === 0 ? <div className="p-5"><EmptyState title="No access patterns above normal" /></div> : (
            <div className="overflow-x-auto px-5 pb-4">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="bg-app-navy text-left text-white">
                    {['Signal heard', 'vs normal', 'What it often means', 'Suggested owner', 'Status', ''].map((h, i) => (
                      <th key={i} className="px-3.5 py-2.5 text-xs font-semibold first:rounded-l-lg last:rounded-r-lg">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rows.map((r) => {
                    const isSel = chartRow?.key === r.key;
                    return (
                      <tr key={r.key} onClick={() => setSelected(r.key)}
                        className={`cursor-pointer align-top transition ${isSel ? 'bg-crm-brand-light/60' : 'hover:bg-slate-50'}`}>
                        <td className="max-w-[26rem] px-3.5 py-3">
                          <div className="font-semibold text-app-navy">{r.heard}</div>
                          {r.entity && <div className="text-slate-600">{r.entity}</div>}
                        </td>
                        <td className="px-3.5 py-3 whitespace-nowrap" title={r.vs.detail}>
                          <span className={`text-[14px] font-bold tabular-nums ${r.vs.direction === 'up' ? 'text-crm-orange-dark' : 'text-slate-600'}`}>{r.vs.text}</span>
                          <div className="text-[11px] text-slate-400">{r.patients ? plural(r.patients, 'patient') : ''}</div>
                        </td>
                        <td className="max-w-[22rem] px-3.5 py-3 text-slate-700">{r.meaning}</td>
                        <td className="px-3.5 py-3 text-slate-600">{r.suggested_owner}</td>
                        <td className="px-3.5 py-3" onClick={(e) => e.stopPropagation()}><StatusMenu insightKey={r.key} status={r.status} /></td>
                        <td className="px-3.5 py-3 text-right">
                          <button type="button" onClick={(e) => { e.stopPropagation(); open(r.signal, r.evidence); }}
                            className="rounded-md border border-slate-200 px-2 py-1 text-xs font-semibold whitespace-nowrap text-crm-brand hover:bg-white hover:shadow-sm">
                            {plural(new Set(r.evidence.map((e: any) => e.call_id)).size, 'call')}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div id="stages" className="grid scroll-mt-20 gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <Card title="Friction heard in conversations – by stage"
            subtitle={`${plural(data.friction_total, 'mention')} · ${fmtDay(data.period_start)} – ${fmtDay(data.as_of)} · click a cell to see the calls`}>
            <HeatMap data={data} onOpen={open} />
          </Card>
          <Card title="Why prior authorization is slow"
            subtitle={`% of delayed PA cases (${data.pa_slow.delayed_cases} of ${data.pa_slow.pa_cases}) where each reason was heard`}>
            {data.pa_slow.reasons.length === 0 ? <EmptyState title="No delayed prior authorizations in this period" /> : (
              <div className="space-y-2.5 pt-1">
                {data.pa_slow.reasons.map((r: any, i: number) => (
                  <button key={r.reason} type="button" onClick={() => open(`Why PA is slow: ${r.reason}`, r.evidence)}
                    className="grid w-full grid-cols-[12.5rem_1fr_2.8rem] items-center gap-3 rounded-lg px-1 py-1 text-left hover:bg-slate-50">
                    <span className="text-right text-[13px] text-app-navy">{r.reason}</span>
                    <span className="h-7 rounded bg-slate-100">
                      <span className={`block h-7 rounded ${i === 0 ? 'bg-crm-orange' : 'bg-app-navy'}`} style={{ width: `${r.share}%` }} />
                    </span>
                    <span className="text-[13px] font-semibold text-slate-600 tabular-nums">{r.share}%</span>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <Card title="Friction is with…" subtitle="Who the friction heard on calls is with, and what people say" pad={false}>
            <div className="px-5 pb-4">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="bg-app-navy text-left text-white">
                    {['Friction is with…', 'Count', 'Most often', 'What people say (example)'].map((h) => (
                      <th key={h} className="px-3.5 py-2.5 text-xs font-semibold first:rounded-l-lg last:rounded-r-lg">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.parties.map((p: any) => (
                    <tr key={p.party} onClick={() => open(`Friction is with: ${p.party}`, p.evidence)} className="cursor-pointer align-top hover:bg-slate-50">
                      <td className="px-3.5 py-3">
                        <span className="inline-flex items-center gap-2 font-semibold text-app-navy">
                          <span className="h-2.5 w-2.5 rounded-full" style={{ background: PARTY_COLOR[p.party] }} />{p.party}
                        </span>
                      </td>
                      <td className="px-3.5 py-3">
                        <span className="text-[15px] font-bold text-slate-800 tabular-nums">{p.count}</span>
                        <span className="ml-1.5 text-xs text-slate-400">{p.share}%</span>
                      </td>
                      <td className="px-3.5 py-3 text-slate-600">{(p.party === 'Hub process' ? p.types : p.entities).slice(0, 2).map((e: any) => `${e[0]} (${e[1]})`).join(', ')}</td>
                      <td className="max-w-[24rem] px-3.5 py-3 text-slate-700 italic">
                        {p.example.quote ? `“${p.example.quote}”` : '—'}
                        <span className="ml-1 text-xs text-slate-400 not-italic">{p.example.entity !== 'Hub' ? `– ${p.example.entity}` : ''}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <div className="space-y-4">
            {data.emerging ? (
              <button type="button" onClick={() => open(data.emerging.title, data.emerging.evidence)}
                className="w-full rounded-xl border-2 border-crm-orange/70 bg-crm-orange-light/40 px-5 py-4 text-left transition hover:bg-crm-orange-light/70">
                <div className="flex items-center gap-2 text-sm font-semibold text-crm-orange-dark"><TrendingUp className="h-4 w-4" /> Emerging access issue</div>
                <div className="mt-1.5 text-[14px] font-semibold text-app-navy">{data.emerging.title}</div>
                <p className="mt-1 text-[13px] leading-relaxed text-slate-700">{data.emerging.text}</p>
                <div className="mt-2 text-xs font-semibold text-crm-orange-dark">
                  Suggested owner: {data.emerging.owner} · counts and approval rates: hub / CRM data (Phase 2)
                </div>
              </button>
            ) : <Callout tone="slate" title="Emerging access issue">Nothing above normal in this period.</Callout>}
            <div className="flex items-start gap-2.5 rounded-xl bg-white px-4 py-3 text-[13px] text-slate-500 italic ring-1 ring-slate-200">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
              Field Access view: own offices only – for access support, never for sales targeting.
            </div>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <Card title={chartRow ? `${chartRow.heard}${chartRow.entity ? ` · ${chartRow.entity}` : ''}` : 'Mentions per week'}
            subtitle="Mentions per week · select a row above to change the chart">
            {chartRow ? <TrendChart row={chartRow} /> : <EmptyState title="Nothing to chart" />}
          </Card>
          <Card title="Actions taken – did the fix work?" subtitle="Mentions per week before → after the action, against normal">
            <Tracked items={data.tracked} rows={rows} />
          </Card>
        </div>

        {data.payers.length > 0 && (
          <Card title="Payer requirements heard" subtitle="Requirement and denial language by payer, as said on the calls">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {data.payers.map((p: any) => (
                <div key={p.payer_id} className="rounded-lg border border-slate-200 p-3.5">
                  <div className="flex items-baseline justify-between">
                    <span className="font-semibold text-app-navy">{p.payer_name}</span>
                    <span className="text-xs text-slate-400">{plural(p.calls, 'call')}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {p.signals.map(([n, c]: [string, number]) => (
                      <span key={n} className="rounded-full bg-violet-50 px-2.5 py-0.5 text-xs text-violet-800 ring-1 ring-violet-200">{n} × {c}</span>
                    ))}
                    {p.signals.length === 0 && <span className="text-xs text-slate-400">No requirement language</span>}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Callout tone="slate">
          <b className="text-app-navy">Boundary:</b> approval rates and turnaround come from hub / CRM data (Phase 2). This screen shows{' '}
          <b className="text-crm-orange-dark">what people are saying</b> – early, before it reaches the numbers – from both sides of each conversation.
        </Callout>
      </div>
      <SourceNote><b>From calls today:</b> signals by payer, office, pharmacy and stage, compared with normal; heat map → reason → who it is with → the conversations; action tracking.</SourceNote>
    </>
  );
}

function HeatMap({ data, onOpen }: { data: any; onOpen: (t: string, e: any[]) => void }) {
  const max = data.heat_max || 1;
  const shade = (n: number) => (n ? `rgba(255, 92, 53, ${0.12 + 0.78 * (n / max)})` : '#fff');
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-1 text-[13px]">
        <thead>
          <tr>
            <th />
            {data.types.map((t: string) => (
              <th key={t} className="rounded-md bg-app-navy px-2 py-2 text-center text-[11.5px] leading-tight font-semibold text-white">{t}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.heat.map((r: any) => (
            <tr key={r.stage}>
              <td className="rounded-md bg-crm-brand-light/70 px-2.5 py-2 text-[12.5px] font-semibold whitespace-nowrap text-app-navy">{r.stage}</td>
              {r.cells.map((c: any) => (
                <td key={c.type}>
                  <button type="button" disabled={!c.count} onClick={() => onOpen(`${r.stage} · ${c.type}`, c.evidence)}
                    style={{ background: shade(c.count) }}
                    className={`h-10 w-full rounded-md text-center text-[14px] tabular-nums ring-1 ring-slate-200 transition ${c.count ? 'cursor-pointer font-bold hover:ring-2 hover:ring-app-navy/40' : 'text-slate-300'} ${c.count / max > 0.55 ? 'text-white' : 'text-slate-800'}`}>
                    {c.count}
                  </button>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrendChart({ row }: { row: any }) {
  const data = row.series.map((s: any) => ({ ...s, over: row.threshold ? s.count > row.threshold : false }));
  const top = Math.max(2, ...data.map((d: any) => d.count), (row.threshold ?? 0) + 0.5);
  return (
    <>
      <div className="mb-2 flex flex-wrap gap-4 text-xs text-slate-500">
        {row.threshold && <span className="font-semibold text-crm-orange-dark">- - alert threshold {row.threshold}</span>}
        {row.normal_per_week && <span>- - normal {row.normal_per_week} / week</span>}
        <span className="ml-auto">{row.vs.detail}</span>
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: -18, right: 8, top: 8 }}>
            <CartesianGrid stroke="#eef2f6" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#677284' }} tickLine={false} axisLine={{ stroke: '#e3e7ee' }} />
            <YAxis allowDecimals={false} domain={[0, Math.ceil(top)]} tick={{ fontSize: 12, fill: '#677284' }} tickLine={false} axisLine={false} />
            <Tooltip cursor={{ fill: '#eef2f6' }} formatter={(v) => [v, 'Mentions']} labelFormatter={(l) => `Week of ${l}`} />
            {row.normal_per_week && <ReferenceLine y={row.normal_per_week} stroke="#4f5a6b" strokeDasharray="5 4" />}
            {row.threshold && <ReferenceLine y={row.threshold} stroke="#e2481a" strokeDasharray="5 4" />}
            <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={46} isAnimationActive={false}>
              {data.map((d: any, i: number) => <Cell key={i} fill={d.over ? '#fe602f' : '#013476'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

function Tracked({ items, rows }: { items: any[]; rows: any[] }) {
  const update = useUpdateAction();
  const candidates = rows.filter((r) => r.status === 'new' || r.status === 'open').slice(0, 3);
  if (!items.length) {
    return (
      <div className="space-y-3">
        <p className="text-[13px] text-slate-600">
          No actions tracked yet. Mark a pattern <StatusPill status="watching" /> and the platform follows its mentions until they return to normal.
        </p>
        {candidates.map((r) => (
          <div key={r.key} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3.5 py-2.5">
            <div className="min-w-0">
              <div className="truncate text-[13px] font-semibold text-app-navy">{r.heard}{r.entity ? ` – ${r.entity}` : ''}</div>
              <div className="truncate text-xs text-slate-500">{r.action}</div>
            </div>
            <button type="button" disabled={update.isPending} onClick={() => update.mutate({ insight_key: r.key, status: 'watching' })}
              className="shrink-0 rounded-lg bg-app-navy px-3 py-1.5 text-xs font-semibold text-white hover:bg-crm-brand-dark">Action taken</button>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {items.map((t) => (
        <div key={t.key} className="rounded-lg border border-slate-200 px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[13.5px] font-semibold text-app-navy">{t.signal}</div>
              <div className="mt-0.5 text-xs text-slate-500">{t.action} · {t.owner}</div>
            </div>
            <StatusMenu insightKey={t.key} status={t.status} align="right" />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
            <span className={`font-semibold ${/normal|Fixed|Improving/.test(t.verdict) ? 'text-emerald-600' : 'text-slate-700'}`}>{t.verdict}</span>
            <span className="text-slate-600 tabular-nums">{t.before} → {t.after ?? '…'} mentions / week</span>
            <ActionDate t={t} />
          </div>
        </div>
      ))}
    </div>
  );
}

function ActionDate({ t }: { t: any }) {
  const update = useUpdateAction();
  return (
    <label className="ml-auto inline-flex items-center gap-1.5 text-xs text-slate-500">
      action taken
      <input type="date" value={t.action_date ?? ''} onChange={(e) => update.mutate({ insight_key: t.key, action_date: e.target.value })}
        className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-700" />
    </label>
  );
}

function ExportButton({ rows }: { rows: any[] }) {
  const download = () => {
    const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const lines = [['Signal heard', 'Who / where', 'vs normal', 'Detail', 'What it often means', 'Suggested owner', 'Status', 'Calls'].map(esc).join(',')];
    rows.forEach((r) => lines.push([r.heard, r.entity, r.vs.text, r.vs.detail, r.meaning, r.suggested_owner, r.status,
      new Set(r.evidence.map((e: any) => e.call_id)).size].map(esc).join(',')));
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: 'access-and-friction.csv' });
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <button type="button" onClick={download}
      className="inline-flex items-center gap-1.5 rounded-lg border-2 border-app-navy bg-white px-3 py-1.5 text-[13px] font-semibold text-app-navy hover:bg-app-navy hover:text-white">
      <Download className="h-4 w-4" /> Export
    </button>
  );
}

function InfoButton({ icon, label, text }: { icon: ReactNode; label: string; text: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 rounded-lg border-2 border-app-navy bg-white px-3 py-1.5 text-[13px] font-semibold text-app-navy hover:bg-app-navy hover:text-white">
        {icon} {label}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-4 text-[13px] text-slate-600 shadow-xl">
          <div className="mb-1 flex items-center gap-2 font-semibold text-app-navy"><MessageSquareQuote className="h-4 w-4" />{label}</div>
          {text}
        </div>
      )}
    </div>
  );
}
