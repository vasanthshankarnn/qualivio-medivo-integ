/* Shared pieces for the tabs: breadcrumbs, tab-level filter chips, stat tiles, status tags, sparklines, bar lists. */
import { ChevronRight, Search } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

/** A filter that belongs to one tab (category, status, level ...): kept in the URL, not sent to other screens. */
export function useParam(name: string, fallback = ''): [string, (v: string) => void] {
  const [params, setParams] = useSearchParams();
  const value = params.get(name) ?? fallback;
  const set = (v: string) => {
    const next = new URLSearchParams(params);
    if (v && v !== fallback) next.set(name, v);
    else next.delete(name);
    setParams(next, { replace: true });
  };
  return [value, set];
}

export function Crumbs({ items }: { items: { label: string; to?: string }[] }) {
  return (
    <div className="flex items-center gap-1.5 px-8 pb-3 text-[13px] text-slate-500">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-slate-300" />}
          {it.to ? <Link to={it.to} className="hover:text-app-navy hover:underline">{it.label}</Link>
            : <span className="font-semibold text-app-navy">{it.label}</span>}
        </span>
      ))}
    </div>
  );
}

export function Objective({ n, label, tone }: { n: number; label: string; tone: 'navy' | 'orange' | 'teal' }) {
  const c = { navy: 'bg-app-navy', orange: 'bg-crm-orange', teal: 'bg-crm-teal' }[tone];
  return <span className={`rounded-full px-3.5 py-1 text-[11.5px] font-bold whitespace-nowrap text-white ${c}`}>Objective {n} · {label}</span>;
}

/** Segmented chips with counts: the slice-and-dice filters inside a tab. */
export function Chips({ label, value, onChange, options }: {
  label?: string; value: string; onChange: (v: string) => void; options: { value: string; label: string; count?: number; tone?: string }[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {label && <span className="mr-1 text-[11px] font-bold tracking-wider text-slate-400 uppercase">{label}</span>}
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={o.value || 'all'} type="button" onClick={() => onChange(o.value)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition ${
              on ? 'bg-app-navy text-white shadow-sm' : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:text-app-navy hover:ring-app-navy/30'}`}>
            {o.tone && <span className={`h-2 w-2 rounded-full ${o.tone}`} />}
            {o.label}
            {o.count !== undefined && <span className={`tabular-nums ${on ? 'text-white/70' : 'text-slate-400'}`}>{o.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <label className="relative block w-64">
      <Search className="pointer-events-none absolute top-2.5 left-3 h-4 w-4 text-slate-400" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="w-full rounded-lg border border-slate-200 bg-white py-2 pr-3 pl-9 text-[13px] outline-none focus:border-crm-brand focus:ring-2 focus:ring-crm-brand/15" />
    </label>
  );
}

/** KPI tile with a coloured edge (Summary style). */
export function Stat({ value, label, sub, bar = 'bg-app-navy', tone = 'text-app-navy', onClick }: {
  value: ReactNode; label: string; sub?: ReactNode; bar?: string; tone?: string; onClick?: () => void;
}) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick}
      className={`flex overflow-hidden rounded-xl border border-slate-200 bg-white text-left shadow-[0_1px_2px_rgba(1,52,118,.04),0_6px_18px_-10px_rgba(1,52,118,.12)] transition ${onClick ? 'hover:-translate-y-px hover:shadow-md' : 'cursor-default'}`}>
      <span className={`w-1.5 shrink-0 ${bar}`} />
      <span className="min-w-0 px-4 py-3.5">
        <span className={`block text-[28px] leading-none font-semibold tabular-nums ${tone}`}>{value}</span>
        <span className="mt-1.5 block text-[13.5px] text-slate-700">{label}</span>
        {sub && <span className="mt-0.5 block text-[12px] text-slate-500">{sub}</span>}
      </span>
    </button>
  );
}

export const ISSUE_STATUS: Record<string, { chip: string; dot: string; text: string }> = {
  New: { chip: 'bg-crm-orange text-white', dot: 'bg-crm-orange', text: 'text-crm-orange-dark' },
  Rising: { chip: 'bg-[#fbe9e7] text-bad ring-1 ring-[#f3c9c3]', dot: 'bg-bad', text: 'text-bad' },
  Steady: { chip: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200', dot: 'bg-slate-400', text: 'text-slate-600' },
  Easing: { chip: 'bg-[#eaf6ee] text-ok ring-1 ring-[#cfe9d7]', dot: 'bg-ok', text: 'text-ok' },
};

export function StatusTag({ status }: { status: string }) {
  const s = ISSUE_STATUS[status] ?? ISSUE_STATUS.Steady;
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[11.5px] font-bold whitespace-nowrap ${s.chip}`}>{status}</span>;
}

export const LEVEL: Record<string, { chip: string; text: string; dot: string }> = {
  High: { chip: 'bg-[#fbe9e7] text-bad ring-1 ring-[#f3c9c3]', text: 'text-bad', dot: 'bg-bad' },
  Medium: { chip: 'bg-[#fdf3e0] text-[#b47b06] ring-1 ring-[#f3dfb4]', text: 'text-[#b47b06]', dot: 'bg-warn' },
  Low: { chip: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200', text: 'text-slate-500', dot: 'bg-slate-300' },
};

export function LevelPill({ level }: { level: string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[11.5px] font-bold ${LEVEL[level]?.chip}`}>{level}</span>;
}

/** Tiny weekly trend: the last weeks (period) drawn darker. */
export function Spark({ values, recent = 4, tone = '#013476', hot = '#fe602f', width = 112, height = 28 }: {
  values: number[]; recent?: number; tone?: string; hot?: string; width?: number; height?: number;
}) {
  const max = Math.max(1, ...values);
  const w = width / values.length;
  return (
    <svg width={width} height={height} className="block" aria-hidden>
      {values.map((v, i) => {
        const h = Math.max(v ? 2 : 1, (height - 2) * (v / max));
        const isRecent = i >= values.length - recent;
        return <rect key={i} x={i * w + 0.75} y={height - h} width={Math.max(1, w - 1.5)} height={h} rx={1}
          fill={isRecent ? hot : tone} opacity={isRecent ? 0.95 : 0.28} />;
      })}
    </svg>
  );
}

/** Ranked horizontal bars (name · bar · count). */
export function BarList({ items, tone = 'bg-app-navy', first = 'bg-crm-orange', suffix, onClick, max: maxIn, labelWidth = '12rem' }: {
  items: { name: string; count: number; share?: number; extra?: ReactNode }[]; tone?: string; first?: string; suffix?: (i: any) => ReactNode;
  onClick?: (i: any) => void; max?: number; labelWidth?: string;
}) {
  const max = maxIn ?? Math.max(1, ...items.map((i) => i.count));
  return (
    <div className="space-y-2">
      {items.map((it, n) => (
        <button key={it.name} type="button" disabled={!onClick} onClick={() => onClick?.(it)}
          className={`grid w-full items-center gap-3 text-left ${onClick ? 'hover:opacity-80' : 'cursor-default'}`}
          style={{ gridTemplateColumns: `${labelWidth} 1fr auto` }}>
          <span className="truncate text-[13.5px] text-slate-700" title={it.name}>{it.name}</span>
          <span className="h-3.5 rounded-sm bg-slate-100">
            <span className={`block h-3.5 rounded-sm ${n === 0 ? first : tone}`} style={{ width: `${Math.max(3, (100 * it.count) / max)}%` }} />
          </span>
          <span className="min-w-[2.5rem] text-right text-[12.5px] font-semibold text-app-navy tabular-nums">
            {suffix ? suffix(it) : it.count}
          </span>
        </button>
      ))}
      {items.length === 0 && <p className="text-sm text-slate-500">Nothing heard in this selection.</p>}
    </div>
  );
}

export function SectionTitle({ children, right, sub }: { children: ReactNode; right?: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-[17px] font-semibold text-app-navy">{children}</h2>
        {sub && <p className="mt-0.5 text-[12.5px] text-slate-500">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function vsTone(vs: string) {
  if (!vs || vs === '–' || vs === 'same') return 'text-slate-500';
  if (vs === 'new') return 'text-crm-orange-dark';
  return vs.startsWith('−') ? 'text-ok' : 'text-bad';
}

export function vsArrow(vs: string) {
  if (!vs || vs === '–' || vs === 'same' || vs === 'new') return '';
  return vs.startsWith('−') ? '▼ ' : '▲ ';
}
