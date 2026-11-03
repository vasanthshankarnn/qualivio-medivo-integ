/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEvidence } from '../components/evidence';
import { ErrorBox, HubSwitch, Loading, ScreenHeader, SourceNote } from '../components/ui';
import { useHubQuality } from '../lib/api';

/** v2 deck · Screen 5 Hub quality & safety: the operational focus areas, each with one number, the reason and the fix. */
const TONE: Record<string, { bar: string; value: string; chip: string }> = {
  green: { bar: 'bg-ok', value: 'text-ok', chip: 'bg-[#eaf6ee] text-ok' },
  amber: { bar: 'bg-warn', value: 'text-[#c98a0b]', chip: 'bg-[#fdf3e0] text-[#c98a0b]' },
};

export default function HubQualityPage() {
  const { data, error } = useHubQuality();
  const open = useEvidence();
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  return (
    <>
      <ScreenHeader title="Hub quality & safety"
        subtitle="How the hub runs: one number, the cause and the fix."
        actions={<HubSwitch />} />
      <div className="grid gap-5 px-8 pb-6 md:grid-cols-2 xl:grid-cols-4">
        {data.cards.map((c: any) => {
          const t = TONE[c.tone];
          return (
            <button key={c.key} type="button" disabled={!c.evidence.length} onClick={() => open(c.title, c.evidence)}
              className={`card flex flex-col overflow-hidden text-left ${c.evidence.length ? 'hover:-translate-y-0.5 hover:shadow-md' : 'cursor-default'}`}>
              <span className={`h-1.5 w-full ${t.bar}`} />
              <span className="flex flex-1 flex-col px-5 pt-4 pb-5">
                <span className="text-[16px] font-semibold text-app-navy">{c.title}</span>
                <span className="mt-4 flex items-baseline gap-2">
                  <span className={`text-[34px] leading-none font-bold tabular-nums ${t.value}`}>{c.value}</span>
                  <span className="text-[14px] text-slate-500">{c.unit}</span>
                </span>
                <span className={`mt-3 w-28 rounded-full py-1 text-center text-[12px] font-bold ${t.chip}`}>{c.status}</span>
                <span className="mt-4 text-[13.5px] leading-snug text-slate-700"><b className="text-app-navy">Why:</b> {c.why}</span>
                <span className="mt-auto pt-4 text-[13.5px] leading-snug text-slate-700"><b className="text-crm-orange-dark">Fix:</b> {c.fix}</span>
              </span>
            </button>
          );
        })}
      </div>
      <SourceNote><b>Source:</b> call recordings, grouped by process, not by agent.</SourceNote>
    </>
  );
}
