import { ArrowUpRight, PhoneCall, Route, X } from 'lucide-react';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import type { Evidence } from '../lib/api';
import { fmtDate, plural } from '../lib/format';

type Open = (title: string, items: Evidence[], subtitle?: string) => void;
const Ctx = createContext<Open>(() => undefined);

/** "Click any number or row → evidence drawer → patient timeline" (deck slide 38). */
export function useEvidence() {
  return useContext(Ctx);
}

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ title: string; subtitle?: string; items: Evidence[] } | null>(null);
  const open = useCallback<Open>((title, items, subtitle) => setState({ title, items, subtitle }), []);
  const close = () => setState(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setState(null);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const calls = state ? groupByCall(state.items) : [];
  return (
    <Ctx.Provider value={open}>
      {children}
      {state && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button type="button" aria-label="Close" onClick={close} className="absolute inset-0 bg-slate-900/25 backdrop-blur-[1px]" />
          <aside className="relative flex h-full w-full max-w-[34rem] flex-col bg-white shadow-2xl animate-[slidein_.18s_ease-out]">
            <header className="border-b border-slate-200 bg-app-navy px-6 py-5 text-white">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] font-semibold tracking-widest text-white/60 uppercase">Evidence</div>
                  <h2 className="mt-1 text-lg leading-snug font-semibold">{state.title}</h2>
                  <p className="mt-1 text-sm text-white/70">
                    {state.subtitle ?? `${plural(state.items.length, 'excerpt')} from ${plural(calls.length, 'conversation')}${state.items.length >= 15 ? ' · most recent shown' : ''}`}
                  </p>
                </div>
                <button type="button" onClick={close} className="rounded-md p-1 text-white/70 hover:bg-white/10 hover:text-white">
                  <X className="h-5 w-5" />
                </button>
              </div>
            </header>
            <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-5">
              {calls.length === 0 && <p className="text-sm text-slate-500">No conversations behind this number.</p>}
              {calls.map(({ call, quotes }) => (
                <article key={call.call_id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                    <span className="font-semibold text-app-navy">{fmtDate(call.date)}</span>
                    <span>·</span>
                    <span className="font-mono">{call.external_call_id}</span>
                    {call.party && <><span>·</span><span>Hub ↔ {call.party}</span></>}
                    {call.stage && <><span>·</span><span>{call.stage}</span></>}
                  </div>
                  <div className="mt-1 text-sm font-semibold text-slate-800">
                    {call.patient_name ?? 'Patient not identified'}
                    <span className="font-normal text-slate-500">
                      {call.practice_name ? ` · ${call.practice_name}` : ''}{call.payer_name ? ` · ${call.payer_name}` : ''}{call.pharmacy ? ` · ${call.pharmacy}` : ''}
                    </span>
                  </div>
                  <div className="mt-2.5 space-y-2">
                    {quotes.map((q, i) => (
                      <div key={i} className="border-l-[3px] border-crm-orange/70 pl-3">
                        {q.label && <div className="text-[11px] font-semibold tracking-wide text-crm-orange-dark uppercase">{q.label}</div>}
                        {q.quote && <p className="text-sm text-slate-700 italic">“{q.quote}”</p>}
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 flex gap-2">
                    {!call.mock && (
                      <Link to={`/calls/${call.call_id}`} onClick={close}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-app-navy hover:bg-slate-50">
                        <PhoneCall className="h-3.5 w-3.5" /> Open call <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    )}
                    {call.patient_id && (
                      <Link to={`/journey/${call.patient_id}`} onClick={close}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-app-navy hover:bg-slate-50">
                        <Route className="h-3.5 w-3.5" /> Patient journey <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </aside>
        </div>
      )}
    </Ctx.Provider>
  );
}

function groupByCall(items: Evidence[]) {
  const map = new Map<string, { call: Evidence; quotes: { quote?: string | null; label?: string | null }[] }>();
  for (const e of items) {
    const g = map.get(e.call_id) ?? { call: e, quotes: [] };
    if (e.quote || e.label) {
      if (!g.quotes.some((q) => q.quote === e.quote && q.label === e.label)) g.quotes.push({ quote: e.quote, label: e.label });
    }
    map.set(e.call_id, g);
  }
  return [...map.values()].sort((a, b) => b.call.date.localeCompare(a.call.date));
}
