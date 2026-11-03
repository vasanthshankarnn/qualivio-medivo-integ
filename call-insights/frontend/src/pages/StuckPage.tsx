/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEvidence } from '../components/evidence';
import { BarList, SectionTitle, Stat, useParam } from '../components/kit';
import { ErrorBox, Loading, ScreenHeader, SourceNote } from '../components/ui';
import { useStuck } from '../lib/api';
import { useFilters } from '../lib/filters';
import { lowerFirst, pctText, periodWord, plural } from '../lib/format';

/** Tab 2 · Where patients get stuck: for every journey stage, how much friction is heard on calls, why, and with whom. */
const CHEVRON: Record<string, string> = { green: 'bg-ok', amber: 'bg-warn', red: 'bg-bad', none: 'bg-slate-300' };
const CARD: Record<string, string> = {
  green: 'bg-[#eaf6ee] ring-[#cfe9d7]', amber: 'bg-[#fdf3e0] ring-[#f3dfb4]', red: 'bg-[#fbe9e7] ring-[#f1c4be]', none: 'bg-slate-50 ring-slate-200',
};
const STATUS_WORD: Record<string, string> = { green: 'Moving', amber: 'Some friction', red: 'Slowest stage', none: 'No calls' };
const PARTY_TONE: Record<string, string> = {
  'Physician office': 'bg-app-navy', Payer: 'bg-crm-orange', Patient: 'bg-crm-teal', 'Hub process': 'bg-slate-500', 'Specialty pharmacy': 'bg-violet-600',
};

export default function StuckPage() {
  const { data, error } = useStuck();
  const [focus, setFocus] = useParam('focus');
  const { f } = useFilters();
  const open = useEvidence();
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const stages = data.stages;
  const sel = stages.find((s: any) => s.slug === focus) ?? stages.find((s: any) => s.stage === data.slowest)
    ?? [...stages].sort((a: any, b: any) => b.friction - a.friction)[0];
  // the clearest line per reason: the longest of its latest excerpts
  const quotes = sel.reasons.flatMap((r: any) => {
    const best = [...r.evidence].filter((e: any) => e.quote).sort((a: any, b: any) => b.quote.length - a.quote.length)[0];
    return best ? [{ ...best, reason: r.name }] : [];
  }).filter((q: any, i: number, all: any[]) => all.findIndex((x: any) => x.quote === q.quote) === i).slice(0, 4);
  const partyMax = Math.max(1, ...sel.parties.map((p: any) => p.count));

  return (
    <>
      <ScreenHeader title="Where patients get stuck"
        subtitle="Where patients wait, why, and with whom – from the calls." />
      <div className="space-y-5 px-8 pb-6">
        <section>
          <div className="grid grid-cols-7 gap-0">
            {stages.map((s: any, i: number) => (
              <button key={s.stage} type="button" onClick={() => setFocus(s.slug)}
                className={`relative flex h-11 items-center justify-center text-[13px] font-bold text-white transition hover:brightness-110 ${CHEVRON[s.status]}`}
                style={{ clipPath: i === 0 ? 'polygon(0 0, 93% 0, 100% 50%, 93% 100%, 0 100%)' : 'polygon(0 0, 93% 0, 100% 50%, 93% 100%, 0 100%, 7% 50%)' }}>
                <span className="px-4 text-center leading-tight">{s.title}</span>
              </button>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-7 gap-3">
            {stages.map((s: any) => {
              const on = s.slug === sel.slug;
              return (
                <button key={s.stage} type="button" onClick={() => setFocus(s.slug)}
                  className={`flex flex-col items-center rounded-xl px-2.5 py-3.5 text-center ring-1 transition hover:-translate-y-0.5 hover:shadow-md ${CARD[s.status]} ${on ? 'shadow-md ring-2 !ring-app-navy' : ''}`}>
                  <span className="text-[30px] leading-none font-bold text-app-navy tabular-nums">{s.patients}</span>
                  <span className="mt-1 text-[12px] text-slate-600">{s.patients === 1 ? 'patient' : 'patients'} · {plural(s.calls, 'call')}</span>
                  <span className="mt-2 text-[13.5px] font-bold text-slate-700">
                    {s.ongoing ? 'ongoing' : s.avg_days !== null ? `avg ${s.avg_days} days` : '—'}
                  </span>
                  {!s.ongoing && (
                    <span className={`text-[12px] font-semibold ${s.waiting ? 'text-bad' : 'text-ok'}`}>
                      {s.waiting ? `${s.waiting} waiting ${data.wait_days}+ days` : 'none waiting'}
                    </span>
                  )}
                  <span className="mt-2.5 text-[11px] text-slate-500">Top reason</span>
                  <span className="line-clamp-2 text-[12px] leading-snug text-slate-700 italic">{s.reasons[0] ? lowerFirst(s.reasons[0].name) : '—'}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="card overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/70 px-5 py-3.5">
            <div className="flex items-center gap-3">
              <span className={`h-3 w-3 rounded-full ${CHEVRON[sel.status]}`} />
              <h2 className="text-[18px] font-semibold text-app-navy">{sel.title}: why they wait</h2>
              <span className="rounded-full bg-white px-2.5 py-0.5 text-[12px] font-semibold text-slate-600 ring-1 ring-slate-200">{STATUS_WORD[sel.status]}</span>
            </div>
            <span className="text-[12.5px] text-slate-500">Click a stage to switch</span>
          </div>
          <div className="grid grid-cols-2 gap-3 px-5 pt-4 md:grid-cols-3 xl:grid-cols-6">
            <Stat value={sel.patients} label={`patients ${periodWord(f.days)}`} />
            <Stat value={sel.ongoing ? '—' : sel.waiting} label={`waiting ${data.wait_days}+ days`} bar={sel.waiting ? 'bg-bad' : 'bg-ok'}
              tone={sel.waiting ? 'text-bad' : 'text-app-navy'} sub={sel.longest_days ? `longest ${sel.longest_days} days` : undefined}
              onClick={sel.evidence_waiting.length ? () => open(`${sel.title}: waiting over ${data.wait_days} days`, sel.evidence_waiting) : undefined} />
            <Stat value={sel.ongoing ? 'ongoing' : sel.avg_days !== null ? `${sel.avg_days} d` : '—'} label="avg days in stage" bar="bg-warn" />
            <Stat value={sel.calls.toLocaleString()} label={`calls ${periodWord(f.days)}`} bar="bg-slate-500" />
            <Stat value={pctText(sel.unresolved)} label="left unresolved" bar={(sel.unresolved ?? 0) > data.overall.unresolved + 5 ? 'bg-bad' : 'bg-slate-500'}
              sub={`hub avg ${data.overall.unresolved}%`} />
            <Stat value={pctText(sel.repeat)} label="repeat calls (7 days)" bar="bg-slate-500" />
          </div>
          <div className="grid gap-6 px-5 pt-5 pb-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)_minmax(0,1fr)]">
            <div>
              <SectionTitle sub="Mentions on these calls · share">Why they wait</SectionTitle>
              <BarList items={sel.reasons} labelWidth="15rem" suffix={(r: any) => <span>{r.count}<span className="ml-1.5 font-normal text-slate-400">{r.share}%</span></span>}
                onClick={(r: any) => open(`${sel.title}: ${r.name}`, r.evidence)} />
            </div>
            <div>
              <SectionTitle>Who it is with</SectionTitle>
              <div className="space-y-2.5">
                {sel.parties.map((p: any) => (
                  <div key={p.name} className="grid grid-cols-[8.5rem_1fr_2.5rem] items-center gap-3">
                    <span className="truncate text-[13.5px] text-slate-700">{p.name}</span>
                    <span className="h-3.5 rounded-sm bg-slate-100">
                      <span className={`block h-3.5 rounded-sm ${PARTY_TONE[p.name] ?? 'bg-slate-500'}`} style={{ width: `${(100 * p.count) / partyMax}%` }} />
                    </span>
                    <span className="text-right text-[12.5px] font-semibold text-app-navy tabular-nums">{p.share}%</span>
                  </div>
                ))}
                {sel.parties.length === 0 && <p className="text-sm text-slate-500">No friction heard at this stage.</p>}
              </div>
            </div>
            <div>
              <SectionTitle sub="Named most">Where it comes from</SectionTitle>
              <ul className="divide-y divide-slate-100">
                {sel.entities.map((e: any) => (
                  <li key={e.kind + e.name} className="flex items-center justify-between gap-3 py-2">
                    <span className="min-w-0">
                      <span className="block truncate text-[13.5px] font-medium text-slate-800">{e.name}</span>
                      <span className="text-[11.5px] text-slate-500">{e.kind}</span>
                    </span>
                    <span className="text-[13px] font-semibold text-app-navy tabular-nums">{plural(e.count, 'mention')}</span>
                  </li>
                ))}
                {sel.entities.length === 0 && <li className="py-2 text-sm text-slate-500">—</li>}
              </ul>
            </div>
          </div>
          {quotes.length > 0 && (
            <div className="border-t border-slate-100 bg-slate-50/50 px-5 py-4">
              <div className="mb-2.5 text-[12px] font-bold tracking-wider text-slate-400 uppercase">In their words</div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {quotes.map((q: any) => (
                  <button key={q.call_id + q.reason} type="button" onClick={() => open(`${sel.title}: ${q.reason}`, sel.reasons.find((r: any) => r.name === q.reason)?.evidence ?? [q])}
                    className="rounded-lg border-l-[3px] border-crm-orange/70 bg-white px-3.5 py-2.5 text-left shadow-sm ring-1 ring-slate-100 hover:ring-slate-300">
                    <span className="block text-[11px] font-semibold tracking-wide text-crm-orange-dark uppercase">{q.reason}</span>
                    <span className="mt-1 block text-[13px] text-slate-700 italic">“{q.quote}”</span>
                    <span className="mt-1.5 block text-[11.5px] text-slate-500">{q.patient_name ?? 'Patient'}{q.practice_name ? ` · ${q.practice_name}` : ''}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="card px-5 pt-4 pb-5">
          <SectionTitle sub="By stage and type · darker = more">Friction map</SectionTitle>
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-1 text-[12.5px]">
              <thead>
                <tr>
                  <th className="w-36" />
                  {data.heat_types.map((t: string) => <th key={t} className="px-2 pb-1 text-left font-semibold text-slate-500">{t}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.heat.map((r: any) => {
                  const st = stages.find((s: any) => s.title === r.stage);
                  return (
                    <tr key={r.stage}>
                      <td className="pr-2 font-semibold whitespace-nowrap text-slate-700">
                        <button type="button" onClick={() => st && setFocus(st.slug)} className="hover:text-app-navy hover:underline">{r.stage}</button>
                      </td>
                      {r.cells.map((c: any) => {
                        const a = c.count / data.heat_max;
                        return (
                          <td key={c.type} title={`${r.stage} · ${c.type}: ${c.count}`}
                            className="h-9 rounded-md text-center font-semibold tabular-nums"
                            style={{ background: c.count ? `rgba(1,52,118,${0.08 + 0.82 * a})` : '#f4f6f9', color: a > 0.45 ? '#fff' : '#364154' }}>
                            {c.count || ''}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>
      <SourceNote><b>Source:</b> stage and friction heard on each call.</SourceNote>
    </>
  );
}
