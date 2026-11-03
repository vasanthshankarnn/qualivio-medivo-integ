/* eslint-disable @typescript-eslint/no-explicit-any */
import { ChevronDown, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useEvidence } from '../components/evidence';
import { Callout, Card, EmptyState, ErrorBox, KpiTile, Loading, ScreenHeader, SourceNote, HubSwitch } from '../components/ui';
import { useReviewSafety, useSafety } from '../lib/api';
import { fmtClock, fmtDay } from '../lib/format';

const ROUTES: Record<string, { label: string; tone: string }> = {
  awaiting: { label: 'Awaiting review', tone: 'text-amber-600' },
  pharmacovigilance: { label: 'Sent to Pharmacovigilance', tone: 'text-violet-700' },
  medical_information: { label: 'Sent to Medical Information', tone: 'text-crm-brand' },
  quality_complaint: { label: 'Quality complaint – sent', tone: 'text-crm-orange-dark' },
  not_safety: { label: 'Reviewed – not a safety event', tone: 'text-slate-500' },
};

export default function SafetyPage() {
  const { data, error } = useSafety();
  const open = useEvidence();
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const c = data.counts;
  const maxTopic = Math.max(1, ...data.topics.map((t: any) => t.count));

  return (
    <>
      <ScreenHeader title="Safety & Medical Information"
        subtitle="Possible adverse events, quality complaints and off-label questions – found on every channel, each reviewed by a person." actions={<HubSwitch />} />
      <div className="space-y-5 px-8 pb-6">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
          <KpiTile value={c.adverse_events} label="possible adverse events" accent sub="incl. dosing mistakes" />
          <KpiTile value={c.quality} label="quality complaints" accent />
          <KpiTile value={c.medical} label="Medical Information questions" accent />
          <KpiTile value={c.awaiting} label="awaiting review" accent={c.awaiting > 0} />
          <KpiTile value={c.avg_hours !== null ? `${c.avg_hours} h` : '—'} label="average time to review"
            sub={`target ≤ ${c.target_hours ?? 24} h · ${c.reviewed} reviewed`} />
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <Card title="Safety review queue" subtitle="Every flag goes to a person · status and review time are recorded" pad={false}>
            {data.queue.length === 0 ? (
              <div className="px-5 pb-5">
                <EmptyState icon={<ShieldCheck className="h-8 w-8" />} title="No possible adverse events, quality complaints or medical questions in the analysed conversations">
                  The current demo calls are about access and paperwork, so none contains a symptom, a product complaint or a question about
                  the medicine. When a call with one is analysed it appears here within minutes, with the patient's own words, a link to the
                  recording and a suggested route – Pharmacovigilance, Medical Information or Quality.
                </EmptyState>
              </div>
            ) : (
              <div className="px-5 pb-4">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="bg-app-navy text-left text-white">
                      {['Source', 'Mention', 'Product', 'Status'].map((h) => (
                        <th key={h} className="px-3.5 py-2.5 text-xs font-semibold first:rounded-l-lg last:rounded-r-lg">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.queue.map((q: any) => (
                      <tr key={q.safety_key} className={`align-top ${q.status === 'awaiting' && q.kind === 'adverse_event' ? 'bg-crm-orange-light/40' : ''}`}>
                        <td className="px-3.5 py-3">
                          <div className="font-semibold text-app-navy">{q.source} · {q.patient_name ?? 'unknown'}</div>
                          <div className="text-xs text-slate-500">
                            <Link to={`/calls/${q.call_id}`} className="link">{q.evidence.external_call_id}</Link> · {fmtDay(q.evidence.date)} · {fmtClock(q.timestamp_s)}
                          </div>
                        </td>
                        <td className="max-w-[18rem] px-3.5 py-3">
                          <button type="button" onClick={() => open(q.kind_label, [q.evidence])} className="text-left">
                            <div className="text-[11px] font-semibold tracking-wide text-crm-orange-dark uppercase">{q.kind_label}{q.topic ? ` · ${q.topic}` : ''}</div>
                            <div className="text-slate-800">{q.mention}</div>
                            {q.quote && q.quote !== q.mention && <div className="mt-0.5 text-xs text-slate-500 italic">“{q.quote}”</div>}
                          </button>
                        </td>
                        <td className="px-3.5 py-3 text-slate-700">{q.product}</td>
                        <td className="px-3.5 py-3"><ReviewMenu q={q} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="space-y-5">
            <Card title="Medical Information questions" subtitle="Questions about the medicine, by topic · this period">
              <div className="space-y-2">
                {data.topics.map((t: any, i: number) => (
                  <button key={t.topic} type="button" disabled={!t.count} onClick={() => open(`Medical questions: ${t.topic}`, t.evidence)}
                    className="grid w-full grid-cols-[9.5rem_1fr_2rem] items-center gap-3 rounded-lg px-1 py-1 text-left hover:bg-slate-50 disabled:hover:bg-transparent">
                    <span className="text-right text-[13px] text-app-navy">{t.topic}</span>
                    <span className="h-6 rounded bg-slate-100">
                      {t.count > 0 && <span className={`block h-6 rounded ${i === 0 ? 'bg-crm-orange' : 'bg-app-navy'}`} style={{ width: `${(100 * t.count) / maxTopic}%` }} />}
                    </span>
                    <span className="text-[13px] font-semibold text-slate-500 tabular-nums">{t.count}</span>
                  </button>
                ))}
              </div>
            </Card>
            <Callout tone="navy" title="Top question">
              {data.top_question
                ? <>“{data.top_question.mention}” ({data.top_question.topic}) – feeds hub training and Medical Information content.</>
                : 'No questions about the medicine in this period. The most-asked question will show here, to feed hub training and Medical Information content.'}
            </Callout>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-2">
          <Callout tone="orange" title="Rule">{data.rule}</Callout>
          <Callout tone="slate">
            <b className="text-app-navy">All patients.</b> Review status and time are recorded for every flag; reconciliation with events the hub
            already reported uses Ipsen safety data. Near-real-time processing for safety flags is a Phase 2 option.
          </Callout>
        </div>
      </div>
      <SourceNote>Human review always – the platform never contacts patients and never reports on its own.</SourceNote>
    </>
  );
}

function ReviewMenu({ q }: { q: any }) {
  const review = useReviewSafety();
  const r = ROUTES[q.status] ?? ROUTES.awaiting;
  return (
    <div>
      <label className={`relative inline-flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 font-semibold hover:bg-slate-100 ${r.tone}`}>
        {r.label}
        <ChevronDown className="h-3.5 w-3.5 opacity-60" />
        <select value={q.status} onChange={(e) => review.mutate({ safety_key: q.safety_key, status: e.target.value })}
          className="absolute inset-0 cursor-pointer opacity-0">
          {Object.entries(ROUTES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </label>
      <div className="px-1.5 text-[11px] text-slate-400">
        {q.status === 'awaiting' ? `suggested: ${ROUTES[q.suggested_route]?.label.replace('Sent to ', '').replace(' – sent', '')}` : q.hours_to_review !== null ? `reviewed in ${q.hours_to_review} h` : ''}
      </div>
    </div>
  );
}
