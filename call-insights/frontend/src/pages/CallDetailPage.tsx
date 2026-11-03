/* eslint-disable @typescript-eslint/no-explicit-any */
import { useRef } from 'react';
import { Link, useParams } from 'react-router-dom';

import { Badge, Card, ErrorBox, Loading, PageHeader, SignalChip, Table } from '../components/ui';
import { audioUrl, useCall, useMaster, usePatients } from '../lib/api';
import { PARTY_LABEL, fmtClock, fmtDateTime } from '../lib/format';
import { SpeakerTag, isMono, personas, speakerKey } from '../lib/speakers';

const DOC_LABEL: Record<string, string> = {
  payer_required: 'Payer requires',
  requested_from_office: 'Asked of the office',
  missing_item: 'Missing',
  confirmed_sent: 'Confirmed sent',
};

/** Where each label came from. Flagged ones need a person to check (deck: every insight is traceable). */
const LABEL_HOW: Record<string, { text: string; tone: string; flag?: boolean }> = {
  metadata: { text: 'Case ID', tone: 'text-emerald-700' },
  metadata_name_mismatch: { text: 'Case ID · name on call differs', tone: 'font-semibold text-crm-orange-dark', flag: true },
  case_record: { text: 'Case record', tone: 'text-emerald-700' },
  case_record_mismatch: { text: '⚠ Call names a different one – record kept', tone: 'font-semibold text-crm-orange-dark', flag: true },
  case_record_unrecognised: { text: 'Case record (name on call not recognised)', tone: 'text-slate-500' },
  from_call_exact: { text: '✨ From the call (AI) – check', tone: 'font-semibold text-violet-700', flag: true },
  from_call_alias: { text: '✨ From the call (AI) – check', tone: 'font-semibold text-violet-700', flag: true },
  from_call_fuzzy: { text: '✨ From the call, close spelling – check', tone: 'font-semibold text-violet-700', flag: true },
  auto_registered: { text: '✨ New – registered from the call – check', tone: 'font-semibold text-violet-700', flag: true },
  'name+dob': { text: '✨ From the call: name + date of birth – check', tone: 'font-semibold text-violet-700', flag: true },
  name: { text: '✨ From the call: name only – check', tone: 'font-semibold text-violet-700', flag: true },
  heard_only: { text: 'Heard only', tone: 'text-slate-400' },
  none: { text: 'Not on the call or the record', tone: 'text-slate-400' },
};

export default function CallDetailPage() {
  const { callId } = useParams();
  const { data, isLoading, error } = useCall(callId);
  const master = useMaster();
  const patients = usePatients();
  const labelName = (e: any) => {
    if (!e.resolved_id) return null;
    const m = master.data;
    const find = (list: any[] | undefined, key: string, name: string) => list?.find((x) => x[key] === e.resolved_id)?.[name];
    return ({
      patient: patients.data?.find((p: any) => p.patient_id === e.resolved_id)?.patient_name,
      practice: find(m?.practices, 'practice_id', 'practice_name'),
      payer: find(m?.payers, 'payer_id', 'payer_name'),
      program: find(m?.programs, 'program_id', 'drug'),
      prescriber: undefined,
    } as Record<string, string | undefined>)[e.entity_type] ?? e.resolved_id;
  };
  const audio = useRef<HTMLAudioElement>(null);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const c = data.call;
  const x = data.extraction;
  const seek = (s: number | null) => {
    if (audio.current && s !== null) {
      audio.current.currentTime = Number(s);
      void audio.current.play();
    }
  };
  const who = personas(x);
  const mono = isMono(data.segments);
  const isStaff = (seg: any) => who[speakerKey(seg.speaker_label)]?.hub ?? seg.channel === 0;

  return (
    <>
      <PageHeader
        title={`Call ${c.external_call_id ?? c.call_id.slice(0, 8)}`}
        subtitle={`${fmtDateTime(c.call_datetime)} · ${c.direction ?? ''} · ${PARTY_LABEL[c.other_party_type] ?? 'other party'} · ${c.journey_stage ?? ''}`}
        actions={c.patient_id && <Link to={`/journey/${c.patient_id}`} className="link text-sm">Patient journey</Link>}
      />
      <div className="grid gap-5 px-8 pb-8 xl:grid-cols-[1fr_24rem]">
        <div className="min-w-0 space-y-5">
          {c.status !== 'completed' && (
            <div className="rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
              Status: <b>{c.status}</b>{c.error ? ` - ${c.error}` : ' (refreshing automatically)'}
            </div>
          )}
          <Card title="Recording" subtitle={c.transcript_source !== 'azure' ? 'Transcript supplied with the call'
            : mono ? 'Mono recording: transcribed from the audio; who is speaking is identified by AI from the conversation'
              : 'Stereo recording: transcribed one channel per party'}>
            <audio ref={audio} controls preload="metadata" src={audioUrl(c.call_id)} className="w-full" />
          </Card>
          {x && (
            <Card title="Summary">
              <p className="text-sm text-slate-700">{x.summary}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs">
                <Badge>Sentiment: {x.sentiment}</Badge>
                <Badge tone={x.identity_verified ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-rose-50 text-rose-700 ring-rose-200'}>
                  Identity {x.identity_verified ? 'confirmed' : 'not confirmed'}
                </Badge>
              </div>
              {x.sentiment_reason && <p className="mt-2 text-xs text-slate-500">{x.sentiment_reason}</p>}
            </Card>
          )}
          <Card title="Transcript"
            subtitle={<>Click a line to play from there · {mono
              ? <><b className="text-violet-600">AI</b> = speaker identified by AI (mono recording)</>
              : <><b>CH</b> = speaker from the recording channel</>}</>}>
            <div className="space-y-1.5">
              {data.segments.map((s: any) => (
                <button key={s.seq} type="button" onClick={() => seek(s.start_s)}
                  className={`flex w-full gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-crm-row-hover ${isStaff(s) ? '' : 'bg-slate-50'}`}>
                  <span className="w-12 shrink-0 pt-0.5 font-mono text-xs text-slate-400">{fmtClock(s.start_s)}</span>
                  <SpeakerTag seg={s} map={who} />
                  <span className="text-slate-800">{s.text}</span>
                </button>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Signals heard" subtitle="Library S01-S38, with the exact words">
            <div className="space-y-2">
              {data.signals.map((s: any) => (
                <button key={s.id} type="button" onClick={() => seek(s.timestamp_s)} className="block w-full rounded-md p-1.5 text-left hover:bg-crm-row-hover">
                  <SignalChip id={s.signal_id} name={s.signal_name} type={s.insight_type} />
                  {s.quote && <div className="mt-1 text-xs text-slate-600">“{s.quote}” <span className="text-slate-400">{fmtClock(s.timestamp_s)}</span></div>}
                </button>
              ))}
              {data.signals.length === 0 && <p className="text-sm text-slate-500">No signals.</p>}
            </div>
          </Card>
          <Card title="Labels" subtitle="Case record first; the names heard on the call fill gaps only (no AI in the matching)">
            {(() => {
              const check = data.entities.filter((e: any) => LABEL_HOW[e.match_method]?.flag);
              return check.length > 0 && (
                <div className="mb-3 rounded-lg bg-violet-50 px-3 py-2 text-xs text-violet-800 ring-1 ring-violet-200">
                  <b>Please check:</b> {check.map((e: any) => e.entity_type).join(', ')} – {check.some((e: any) => e.match_method === 'case_record_mismatch')
                    ? 'the call names something different from the case record' : 'taken from the call, not from a case record'}.
                </div>
              );
            })()}
            <Table head={['Type', 'Heard on call', 'Label', 'Source']}>
              {data.entities.map((e: any) => {
                const how = LABEL_HOW[e.match_method] ?? { text: e.match_method, tone: 'text-slate-500' };
                return (
                  <tr key={e.id} className="align-top">
                    <td className="px-2 py-1.5 text-xs font-medium capitalize">{e.entity_type.replace('_', ' ')}</td>
                    <td className="px-2 py-1.5 text-xs">{e.heard_text ?? '—'}</td>
                    <td className="px-2 py-1.5 text-xs">{labelName(e) ?? '—'}</td>
                    <td className={`px-2 py-1.5 text-xs ${how.tone}`}>{how.text}</td>
                  </tr>
                );
              })}
            </Table>
          </Card>
          {data.promises.length > 0 && (
            <Card title="Promises">
              <ul className="space-y-2 text-sm">
                {data.promises.map((p: any) => (
                  <li key={p.id}>
                    <span className="font-medium">{p.action}</span>
                    <div className="text-xs text-slate-500">{p.made_by_role} · {p.due_text ?? 'no date'}{p.due_date ? ` (${p.due_date})` : ''}</div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {data.documents.length > 0 && (
            <Card title="Documents mentioned">
              {Object.entries(DOC_LABEL).map(([k, label]) => {
                const items = data.documents.filter((d: any) => d.list_type === k);
                return items.length ? (
                  <div key={k} className="mb-2">
                    <div className="text-xs font-semibold text-slate-500">{label}</div>
                    <ul className="list-disc pl-5 text-sm">{items.map((d: any) => <li key={d.id}>{d.item}</li>)}</ul>
                  </div>
                ) : null;
              })}
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
