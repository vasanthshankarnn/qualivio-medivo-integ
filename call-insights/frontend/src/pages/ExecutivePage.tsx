/* eslint-disable @typescript-eslint/no-explicit-any */
import { ArrowDownLeft, ArrowUpRight, ChevronDown, ChevronUp, Clock, Phone, Split, Users } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';

import { useEvidence } from '../components/evidence';
import { ErrorBox, Loading, SourceNote } from '../components/ui';
import { useExecutive } from '../lib/api';

/** Call analysis (tab 7): the Qualivio executive component (volume, duration, call types by direction) on call-insights data. */
const hms = (s: number) => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}h ${m}m` : `${m}m ${sec}s`;
};

const TONE = {
  in: { icon: 'bg-crm-brand text-white', soft: 'bg-crm-brand-light text-crm-brand', text: 'text-crm-brand', line: '#1a56a8', bar: 'bg-crm-brand' },
  out: { icon: 'bg-crm-teal text-white', soft: 'bg-teal-50 text-crm-teal', text: 'text-crm-teal', line: '#0f7c80', bar: 'bg-crm-teal' },
};

export default function ExecutivePage() {
  const { data, error } = useExecutive();
  const open = useEvidence();
  const [expanded, setExpanded] = useState(true);
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4 px-8 pt-7 pb-5">
        <div>
          <h1 className="flex items-center gap-2.5 text-[26px] leading-tight font-bold tracking-tight text-app-navy">
            <Users className="h-6 w-6 text-crm-orange" /> Call analysis
          </h1>
          <p className="mt-1.5 text-[15px] text-slate-600">Hub call volume, duration and what the calls were about</p>
        </div>
      </div>

      <div className="space-y-5 px-8 pb-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <DirectionCard tone={TONE.in} icon={<ArrowDownLeft className="h-5 w-5" />} label="Inbound calls" side={data.inbound}
            onClick={() => data.inbound.count && open('Inbound calls', data.inbound.evidence)} />
          <DirectionCard tone={TONE.out} icon={<ArrowUpRight className="h-5 w-5" />} label="Outbound calls" side={data.outbound}
            onClick={() => data.outbound.count && open('Outbound calls', data.outbound.evidence)} />
          <StatCard label="Total analysed calls" value={data.total.toLocaleString()} sub={`Across ${data.agents} agents`}
            icon={<Phone className="h-5 w-5" />} iconTone="bg-slate-100 text-app-navy" onClick={() => open('Analysed calls', data.evidence)} />
          <StatCard label="Total duration" value={hms(data.total_seconds)} sub="Total call duration"
            icon={<Clock className="h-5 w-5" />} iconTone="bg-violet-50 text-violet-600" />
          <StatCard label="Avg duration" value={hms(data.avg_seconds)} sub="Average call"
            icon={<Clock className="h-5 w-5" />} iconTone="bg-violet-50 text-violet-600" />
        </div>

        <section className="card overflow-hidden">
          <header className="flex items-center justify-between gap-4 px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-slate-100 text-app-navy"><Split className="h-5 w-5" /></span>
              <div>
                <h2 className="text-[17px] font-bold text-app-navy">Types of calls</h2>
                <p className="text-[12px] font-semibold tracking-wide text-slate-400 uppercase">Analysed call distribution</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">Total</div>
                <div className="text-[22px] leading-none font-bold text-app-navy tabular-nums">{data.total}</div>
              </div>
              <button type="button" onClick={() => setExpanded(!expanded)} aria-label={expanded ? 'Collapse' : 'Expand'}
                className="grid h-8 w-8 place-items-center rounded-lg text-slate-500 ring-1 ring-slate-200 hover:bg-slate-50">
                {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </button>
            </div>
          </header>
          {expanded && (
            <div className="grid gap-4 px-5 pb-5 lg:grid-cols-2">
              <Breakdown tone={TONE.in} icon={<ArrowDownLeft className="h-5 w-5" />} title="Inbound call breakdown" side={data.inbound}
                pctLabel="% of inbound" empty="No inbound calls in this period – the demo calls are all hub-initiated." onOpen={open} />
              <Breakdown tone={TONE.out} icon={<ArrowUpRight className="h-5 w-5" />} title="Outbound call breakdown" side={data.outbound}
                pctLabel="% of outbound" empty="No outbound calls in this period." onOpen={open} />
            </div>
          )}
        </section>
      </div>
      <SourceNote><b>Source:</b> phone system (direction, length) and the reason heard on each call. Trend lines: last 13 weeks.</SourceNote>
    </>
  );
}

function DirectionCard({ tone, icon, label, side, onClick }: { tone: any; icon: ReactNode; label: string; side: any; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className="card flex items-center gap-3 px-4 py-4 text-left hover:-translate-y-px hover:shadow-md">
      <span className={`grid h-10 w-10 shrink-0 place-items-center self-start rounded-lg ${tone.icon}`}>{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-[14px] font-bold whitespace-nowrap text-app-navy">{label}</span>
        <span className="mt-1 block text-[26px] leading-none font-bold text-app-navy tabular-nums">{side.count}</span>
        <span className="mt-2 block text-[12.5px] whitespace-nowrap text-slate-500">{side.share}% of total</span>
      </span>
      <span className="h-10 w-16 shrink-0 self-center">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={side.weekly} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
            <defs>
              <linearGradient id={`spark-${tone.line.slice(1)}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={tone.line} stopOpacity={0.25} />
                <stop offset="100%" stopColor={tone.line} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="count" stroke={tone.line} strokeWidth={1.6} fill={`url(#spark-${tone.line.slice(1)})`} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </span>
    </button>
  );
}

function StatCard({ label, value, sub, icon, iconTone, onClick }: {
  label: string; value: ReactNode; sub: string; icon: ReactNode; iconTone: string; onClick?: () => void;
}) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick}
      className={`card flex items-start justify-between gap-3 px-4 py-4 text-left ${onClick ? 'hover:-translate-y-px hover:shadow-md' : 'cursor-default'}`}>
      <span>
        <span className="block text-[14px] text-slate-600">{label}</span>
        <span className="mt-1.5 block text-[26px] leading-none font-bold text-app-navy tabular-nums">{value}</span>
        <span className="mt-2 block text-[12.5px] text-slate-500">{sub}</span>
      </span>
      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg ${iconTone}`}>{icon}</span>
    </button>
  );
}

function Breakdown({ tone, icon, title, side, pctLabel, empty, onOpen }: {
  tone: any; icon: ReactNode; title: string; side: any; pctLabel: string; empty: string; onOpen: (t: string, e: any[]) => void;
}) {
  const max = Math.max(1, ...side.types.map((t: any) => t.count));
  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
        <span className={`grid h-10 w-10 place-items-center rounded-lg ${tone.soft}`}>{icon}</span>
        <div>
          <div className={`text-[13px] font-bold tracking-wide uppercase ${tone.text}`}>{title}</div>
          <div className="flex items-baseline gap-2">
            <span className="text-[22px] font-bold text-app-navy tabular-nums">{side.count}</span>
            <span className="text-[12.5px] text-slate-500">{side.share}% of total</span>
          </div>
        </div>
      </div>
      <div className="px-5 py-3">
        {side.types.length === 0 ? <p className="py-6 text-center text-[13px] text-slate-500">{empty}</p> : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-slate-100 text-left text-[12px] font-semibold text-slate-600">
                <th className="py-2 font-semibold">Call type</th>
                <th className="w-[38%] py-2" />
                <th className="w-14 py-2 text-right font-semibold">Count</th>
                <th className="w-24 py-2 text-right font-semibold">{pctLabel}</th>
              </tr>
            </thead>
          </table>
        )}
        {side.types.length > 0 && (
          <div>
            <table className="w-full text-[13px]">
              <tbody className="divide-y divide-slate-100">
                {side.types.map((t: any) => (
                  <tr key={t.type} onClick={() => onOpen(`${title}: ${t.type}`, t.evidence)} className="cursor-pointer hover:bg-slate-50">
                    <td className="py-3 text-slate-800">{t.type}</td>
                    <td className="w-[38%] py-3 pr-2">
                      <span className="block h-1.5 rounded-full bg-slate-100">
                        <span className={`block h-1.5 rounded-full ${tone.bar}`} style={{ width: `${(100 * t.count) / max}%` }} />
                      </span>
                    </td>
                    <td className="w-14 py-3 text-right font-bold text-app-navy tabular-nums">{t.count}</td>
                    <td className="w-24 py-3 text-right text-slate-600 tabular-nums">{t.share}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
