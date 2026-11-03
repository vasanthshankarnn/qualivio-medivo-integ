import { ChevronDown, Info } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { useUpdateAction, type Evidence, type Insight, type Vs } from '../lib/api';
import { BAND_STYLE, INSIGHT_STYLE, OWNERS, RULE_LABEL, STATUS, fmtDate } from '../lib/format';
import { useEvidence } from './evidence';

/* ------------------------------------------------------------------ page chrome */

/** Header used by the insight-workspace screens: title, one-line subtitle, actions. */
export function ScreenHeader({ title, subtitle, actions }: { title: string; subtitle: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 px-8 pt-7 pb-5">
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight text-app-navy">{title}</h1>
        </div>
        <p className="mt-2 max-w-4xl text-[15px] text-slate-600 italic">{subtitle}</p>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** The deck's footer strip: where the numbers come from today, and what Phase 2 completes. */
export function SourceNote({ children }: { children: ReactNode }) {
  return (
    <div className="mx-8 mb-8 rounded-xl bg-crm-orange-light/70 px-5 py-3 text-[13px] text-slate-700 ring-1 ring-orange-100">
      {children}
      <span className="ml-1 text-slate-500 italic">Normal = prior 13 weeks.</span>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 px-8 pt-7 pb-5">
      <div>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight text-app-navy">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-3xl text-[15px] text-slate-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, subtitle, children, className = '', right, pad = true, info }: {
  title?: ReactNode; subtitle?: ReactNode; children: ReactNode; className?: string; right?: ReactNode; pad?: boolean; info?: string;
}) {
  return (
    <section className={`card flex flex-col ${className}`}>
      {(title || right) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
          <div className="min-w-0">
            {title && (
              <h2 className="flex items-center gap-1.5 text-[15px] font-semibold text-app-navy">
                {title}
                {info && <span title={info}><Info className="h-3.5 w-3.5 text-slate-400" /></span>}
              </h2>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      <div className={`min-h-0 flex-1 ${pad ? 'px-5 pb-5' : ''} ${!title && !right && pad ? 'pt-5' : ''}`}>{children}</div>
    </section>
  );
}

export function Callout({ tone = 'orange', title, children, dashed }: { tone?: 'orange' | 'navy' | 'slate'; title?: ReactNode; children: ReactNode; dashed?: boolean }) {
  const t = {
    orange: 'bg-crm-orange-light/60 ring-orange-200 [&_.callout-title]:text-crm-orange-dark',
    navy: 'bg-crm-brand-light/70 ring-blue-200 [&_.callout-title]:text-app-navy',
    slate: 'bg-white ring-slate-200 [&_.callout-title]:text-app-navy',
  }[tone];
  return (
    <div className={`rounded-xl px-5 py-4 text-sm text-slate-700 ring-1 ${t} ${dashed ? 'ring-0 border-2 border-dashed border-crm-orange/60' : ''}`}>
      {title && <div className="callout-title mb-1 font-semibold">{title}</div>}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ numbers */

export function DeltaChip({ vs, unit = '%', invert = false }: { vs: Vs; unit?: string; invert?: boolean }) {
  if (!vs) return null;
  const bad = invert ? vs.direction === 'down' : vs.direction === 'up';
  const arrow = vs.direction === 'up' ? '▲' : vs.direction === 'down' ? '▼' : '•';
  const tone = vs.direction === 'flat' ? 'text-slate-500' : bad ? 'text-crm-orange-dark' : 'text-emerald-600';
  return (
    <span className={`text-xs font-semibold whitespace-nowrap ${tone}`} title="Compared with the 13-week baseline">
      {arrow} vs {vs.normal}{unit}
    </span>
  );
}

/** KPI tile (deck style: big number, short label, comparison with normal). Click opens the evidence behind it. */
export function KpiTile({ value, label, sub, vs, invert, partial, evidence, evidenceTitle, accent = false, small }: {
  value: ReactNode; label: string; sub?: ReactNode; vs?: Vs; invert?: boolean; partial?: boolean; evidence?: Evidence[];
  evidenceTitle?: string; accent?: boolean; small?: boolean;
}) {
  const open = useEvidence();
  const clickable = !!evidence?.length;
  return (
    <button
      type="button"
      disabled={!clickable}
      onClick={() => clickable && open(evidenceTitle ?? label, evidence!)}
      className={`group relative flex h-full w-full flex-col justify-between rounded-xl bg-white px-4 py-3.5 text-left transition
        ${partial ? 'border-2 border-dashed border-crm-orange/55' : 'border border-slate-200 shadow-[0_1px_2px_rgba(1,52,118,.04),0_6px_18px_-10px_rgba(1,52,118,.12)]'}
        ${clickable ? 'cursor-pointer hover:-translate-y-px hover:shadow-md hover:ring-2 hover:ring-crm-brand/15' : 'cursor-default'}`}
    >
      <div className="flex items-baseline gap-2">
        <span className={`${small ? 'text-[26px]' : 'text-[32px]'} leading-none font-semibold tracking-tight tabular-nums ${accent ? 'text-crm-orange' : 'text-app-navy'}`}>
          {value}
        </span>
        {vs !== undefined && <DeltaChip vs={vs} invert={invert} />}
      </div>
      <div className="mt-2 text-[13px] leading-snug font-medium text-slate-600">{label}</div>
      {(sub || partial) && (
        <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
          {sub}
          {partial && <span className="font-semibold text-crm-orange-dark">· partial</span>}
        </div>
      )}
    </button>
  );
}

/** Horizontal share bar with a "normal" marker (deck slide 16: "% · │ = normal"). */
export function NormalBar({ label, value, normal, max, highlight, onClick, suffix = '%' }: {
  label: string; value: number; normal?: number | null; max: number; highlight?: boolean; onClick?: () => void; suffix?: string;
}) {
  const w = (v: number) => `${Math.min(100, (100 * v) / max)}%`;
  return (
    <button type="button" onClick={onClick}
      className="group grid w-full grid-cols-[11.5rem_1fr_4.2rem] items-center gap-3 rounded-lg px-1 py-1.5 text-left hover:bg-slate-50">
      <span className={`truncate text-[13px] ${highlight ? 'font-semibold text-app-navy' : 'text-slate-700'}`}>{label}</span>
      <span className="relative h-5 rounded bg-slate-100">
        <span className={`absolute inset-y-0 left-0 rounded ${highlight ? 'bg-crm-orange' : 'bg-app-navy/85'} transition-all`} style={{ width: w(value) }} />
        {normal !== null && normal !== undefined && (
          <span className="absolute -inset-y-1 w-0.5 rounded bg-slate-700" style={{ left: w(normal) }} title={`Normal ${normal}${suffix}`} />
        )}
      </span>
      <span className={`text-right text-[13px] tabular-nums ${highlight ? 'font-semibold text-crm-orange-dark' : 'text-slate-600'}`}>
        {value}{suffix}{highlight && ' ▲'}
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ status, owner, feedback */

export function StatusPill({ status }: { status: string }) {
  const s = STATUS[status] ?? STATUS.open;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[13px] font-medium whitespace-nowrap ${s.tone}`}>
      <span>{s.icon}</span>
      {s.label}
    </span>
  );
}

function useOutside(ref: React.RefObject<HTMLElement | null>, close: () => void) {
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && close();
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [ref, close]);
}

/** Status dropdown that writes back (deck: "Status ▾"). */
export function StatusMenu({ insightKey, status, align = 'left' }: { insightKey: string; status: string; align?: 'left' | 'right' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const update = useUpdateAction();
  useOutside(ref, () => setOpen(false));
  return (
    <div ref={ref} className="relative inline-block">
      <button type="button" onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}
        className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-slate-100">
        <StatusPill status={status} />
        <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
      </button>
      {open && (
        <div className={`absolute z-40 mt-1 w-60 rounded-lg border border-slate-200 bg-white p-1 shadow-xl ${align === 'right' ? 'right-0' : 'left-0'}`}>
          {Object.keys(STATUS).map((k) => (
            <button key={k} type="button" disabled={update.isPending}
              onClick={(e) => { e.stopPropagation(); update.mutate({ insight_key: insightKey, status: k }); setOpen(false); }}
              className={`flex w-full items-center rounded-md px-2.5 py-1.5 text-left hover:bg-slate-50 ${k === status ? 'bg-slate-50' : ''}`}>
              <StatusPill status={k} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function OwnerMenu({ insightKey, owner, light }: { insightKey: string; owner: string; light?: boolean }) {
  const update = useUpdateAction();
  return (
    <label className={`relative inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[13px] font-medium ${light ? 'text-white hover:bg-white/15' : 'text-slate-700 hover:bg-slate-100'}`}>
      <span>{owner}</span>
      <ChevronDown className="h-3.5 w-3.5 opacity-70" />
      <select value={owner} onChange={(e) => update.mutate({ insight_key: insightKey, owner: e.target.value })}
        className="absolute inset-0 cursor-pointer opacity-0">
        {[...new Set([owner, ...OWNERS])].map((o) => <option key={o}>{o}</option>)}
      </select>
    </label>
  );
}

export function Useful({ insightKey, useful, light }: { insightKey: string; useful: boolean | null; light?: boolean }) {
  const update = useUpdateAction();
  const btn = (v: boolean, label: string) => (
    <button type="button" onClick={() => update.mutate({ insight_key: insightKey, useful: useful === v ? null : v })}
      className={`rounded px-1.5 font-semibold ${useful === v ? (light ? 'bg-white text-crm-orange-dark' : 'bg-app-navy text-white') : light ? 'text-white/90 hover:bg-white/15' : 'text-slate-600 hover:bg-slate-100'}`}>
      {label}
    </button>
  );
  return (
    <span className={`inline-flex items-center gap-1 text-[13px] ${light ? 'text-white/90' : 'text-slate-500'}`}>
      Was this useful? {btn(true, 'Yes')} · {btn(false, 'No')}
      {useful !== null && <span className="ml-1 text-xs italic">feedback recorded</span>}
    </span>
  );
}

/* ------------------------------------------------------------------ small pieces (also used by the call screens) */

export function Badge({ children, tone = 'bg-slate-100 text-slate-700 ring-slate-200' }: { children: ReactNode; tone?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset ${tone}`}>
      {children}
    </span>
  );
}

export function BandBadge({ band }: { band?: string | null }) {
  if (!band) return null;
  return <Badge tone={BAND_STYLE[band] ?? undefined}>{band.charAt(0).toUpperCase() + band.slice(1)}</Badge>;
}

export function SignalChip({ id, name, type, quote }: { id: string; name: string; type?: string; quote?: string }) {
  return (
    <span title={quote ? `“${quote}”` : undefined}
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs ring-1 ring-inset ${INSIGHT_STYLE[type ?? ''] ?? 'bg-slate-50 text-slate-700 ring-slate-200'}`}>
      <span className="font-semibold">{id}</span>
      {name}
    </span>
  );
}

export function Kpi({ label, value, hint, tone = 'text-app-navy' }: { label: string; value: ReactNode; hint?: string; tone?: string }) {
  return (
    <div className="card px-4 py-3">
      <div className={`text-2xl font-semibold tabular-nums ${tone}`}>{value}</div>
      <div className="mt-0.5 text-sm font-medium text-slate-700">{label}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/50 px-6 py-10 text-center">
      {icon && <div className="mb-3 flex justify-center text-slate-400">{icon}</div>}
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-xl text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function Loading() {
  return (
    <div className="space-y-4 p-8">
      <div className="h-8 w-80 animate-pulse rounded-lg bg-slate-200/70" />
      <div className="h-4 w-[34rem] animate-pulse rounded bg-slate-200/60" />
      <div className="grid grid-cols-3 gap-4 pt-4">
        {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-slate-200/50" />)}
      </div>
      <div className="h-72 animate-pulse rounded-xl bg-slate-200/40" />
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  return (
    <div className="m-8 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      Could not load data: {String((error as Error)?.message ?? error)}
    </div>
  );
}

export function EvidenceLinks({ evidence }: { evidence: Insight['evidence'] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {evidence.map((e, i) => (
        <Link key={`${e.call_id}-${i}`} to={`/calls/${e.call_id}`} className="link text-xs" title={e.quote ?? undefined}>
          {e.external_call_id} · {fmtDate(e.date)}
        </Link>
      ))}
    </div>
  );
}

/** Insight with its deterministic next-best action (one rule -> one action). */
export function InsightCard({ insight, subjectLabel }: { insight: Insight; subjectLabel?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="bg-crm-brand-light text-crm-brand-dark ring-blue-200">{RULE_LABEL[insight.rule_id] ?? insight.rule_id}</Badge>
        <span className="text-sm font-semibold text-slate-900">{insight.title}</span>
        {subjectLabel && <span className="text-sm text-slate-500">· {subjectLabel}</span>}
        <BandBadge band={insight.band} />
      </div>
      <p className="mt-2 text-sm text-slate-700">{insight.detail}</p>
      <div className="mt-3 rounded-md border-l-4 border-crm-orange bg-crm-orange-light px-3 py-2">
        <div className="text-xs font-semibold tracking-wide text-crm-orange-dark uppercase">Next best action · {insight.owner_team}</div>
        <div className="mt-0.5 text-sm text-slate-800">{insight.action}</div>
      </div>
      {insight.evidence?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs font-medium text-slate-500">Evidence</div>
          <EvidenceLinks evidence={insight.evidence} />
        </div>
      )}
    </div>
  );
}

export function Table({ head, children, empty, dense, navy }: { head: ReactNode[]; children: ReactNode; empty?: string; dense?: boolean; navy?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className={navy ? 'bg-app-navy text-white' : 'border-b border-slate-200 text-slate-500'}>
            {head.map((h, i) => (
              <th key={i} className={`${dense ? 'px-3 py-2' : 'px-3 py-2.5'} text-xs font-semibold ${navy ? 'first:rounded-l-lg last:rounded-r-lg' : 'tracking-wide uppercase'}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
      {empty && <div className="px-3 py-6 text-center text-sm text-slate-500">{empty}</div>}
    </div>
  );
}

/** Hub quality (tab 6) holds two v1 screens as detail views: switch between them. */
export function HubSwitch() {
  const { pathname, search } = useLocation();
  const views = [{ to: '/hub', label: 'Overview' }, { to: '/follow-through', label: 'Follow-through details' }, { to: '/safety', label: 'Safety queue' }];
  return (
    <div className="inline-flex rounded-lg bg-slate-100 p-1 ring-1 ring-slate-200">
      {views.map((v) => (
        <Link key={v.to} to={{ pathname: v.to, search }}
          className={`rounded-md px-3.5 py-1.5 text-[13px] font-semibold transition ${pathname.startsWith(v.to) ? 'bg-white text-app-navy shadow-sm' : 'text-slate-500 hover:text-app-navy'}`}>
          {v.label}
        </Link>
      ))}
    </div>
  );
}
