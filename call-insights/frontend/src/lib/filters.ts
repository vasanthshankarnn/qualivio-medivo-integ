import { useSearchParams } from 'react-router-dom';

/** The filter bar (program · stage · payer · specialty pharmacy · period), kept in the URL so every link and refresh keeps it. */
export type Filters = { program: string; stage: string; payer: string; sp: string; days: number };

export const DEFAULT_DAYS = 7;
export const PERIODS = [
  { days: 7, label: 'This week' },
  { days: 14, label: 'Last 14 days' },
  { days: 30, label: 'Last 30 days' },
  { days: 90, label: 'Last 90 days' },
  { days: 0, label: 'All analysed calls' },
];

const readDays = (v: string | null) => (v === 'all' ? 0 : Number(v) || DEFAULT_DAYS);

export function useFilters() {
  const [params, setParams] = useSearchParams();
  const f: Filters = {
    program: params.get('program') ?? '',
    stage: params.get('stage') ?? '',
    payer: params.get('payer') ?? '',
    sp: params.get('sp') ?? '',
    days: readDays(params.get('days')),
  };
  const set = (patch: Partial<Filters>) => {
    const next = new URLSearchParams(params);
    Object.entries(patch).forEach(([k, v]) => {
      if (k === 'days') {
        if (v === DEFAULT_DAYS) next.delete('days');
        else next.set('days', v === 0 ? 'all' : String(v));
      } else if (v) next.set(k, String(v));
      else next.delete(k);
    });
    setParams(next, { replace: true });
  };
  const qs = toQuery(f);
  return { f, set, qs, active: !!(f.program || f.stage || f.payer || f.sp || f.days !== DEFAULT_DAYS) };
}

export function toQuery(f: Filters) {
  const p = new URLSearchParams();
  if (f.program) p.set('program', f.program);
  if (f.stage) p.set('stage', f.stage);
  if (f.payer) p.set('payer', f.payer);
  if (f.sp) p.set('sp', f.sp);
  if (f.days !== DEFAULT_DAYS) p.set('days', f.days === 0 ? 'all' : String(f.days));
  const s = p.toString();
  return s ? `?${s}` : '';
}

/** Add tab-level parameters to a filter query string. */
export function withParams(qs: string, extra: Record<string, string | undefined>) {
  const p = new URLSearchParams(qs);
  Object.entries(extra).forEach(([k, v]) => v && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : '';
}
