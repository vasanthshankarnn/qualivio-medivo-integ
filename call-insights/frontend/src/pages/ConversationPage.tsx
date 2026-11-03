/* eslint-disable @typescript-eslint/no-explicit-any */
import { Activity, ClipboardCheck, Download, MessageSquareText, Pause, Play, RefreshCw, RotateCcw, RotateCw, Radio, Users } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useEvidence } from '../components/evidence';
import { ErrorBox, Loading } from '../components/ui';
import { audioUrl, post, useConversation } from '../lib/api';
import { fmtClock, fmtDate } from '../lib/format';
import { personas, speakerKey } from '../lib/speakers';
import { AREAS, ScoreLegend, scoreTone } from './PatientCallsPage';

/** Qualivio's conversation analysis page (down to the timeline player), on call-insights data.
 *  "Overall score" is replaced by the number of signals heard; the five area scores are demo values. */
export default function ConversationPage() {
  const [params] = useSearchParams();
  const callId = params.get('callId');
  const { data, error, refetch } = useConversation(callId);
  const open = useEvidence();
  const [busy, setBusy] = useState(false);
  if (!callId) return <ErrorBox error="No call selected – open a call from Conversation analysis." />;
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;

  const reprocess = async () => {
    setBusy(true);
    try {
      await post(`/v1/calls/${callId}/process`);
      window.setTimeout(() => { void refetch(); setBusy(false); }, 4000);
    } catch {
      setBusy(false);
    }
  };

  return (
    <div className="print:bg-white">
      <div className="flex flex-wrap items-start justify-between gap-4 px-8 pt-7 pb-5">
        <div>
          <h1 className="flex items-center gap-2.5 text-[26px] leading-tight font-bold tracking-tight text-app-navy">
            <MessageSquareText className="h-6 w-6 text-crm-orange" /> Conversation analysis
          </h1>
          <p className="mt-1.5 text-[15px] text-slate-600">
            Patient: <Link to={data.patient_id ? `/journey/${data.patient_id}` : '#'} className="font-semibold text-app-navy hover:underline">{data.patient_name}</Link>
            {data.case_id && <> · case {data.case_id}</>} | Call date: {fmtDate(data.date)}
            <span className="text-slate-400"> · {data.external_call_id} · Hub ↔ {data.party}{data.staff_name ? ` · ${data.staff_name}` : ''}</span>
          </p>
        </div>
        <div className="flex items-center gap-3 print:hidden">
          <ScoreLegend />
          <button type="button" onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-lg bg-crm-orange px-4 py-2.5 text-[13px] font-bold tracking-wide text-white uppercase shadow-sm hover:bg-crm-orange-dark">
            <Download className="h-4 w-4" /> Export PDF
          </button>
          <button type="button" onClick={reprocess} disabled={busy}
            className="inline-flex items-center gap-2 rounded-lg bg-app-navy px-4 py-2.5 text-[13px] font-bold tracking-wide text-white uppercase shadow-sm hover:bg-crm-brand disabled:opacity-60">
            <RefreshCw className={`h-4 w-4 ${busy ? 'animate-spin' : ''}`} /> {busy ? 'Reprocessing…' : 'Reprocess call'}
          </button>
        </div>
      </div>

      <div className="space-y-5 px-8 pb-8">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          <button type="button" onClick={() => open(`Signals heard on ${data.external_call_id}`,
            data.signals.map((s: any) => ({ call_id: data.call_id, external_call_id: data.external_call_id, date: data.date, patient_id: data.patient_id,
              patient_name: data.patient_name, quote: s.quote, label: `${s.signal_id} · ${s.signal_name}` })))}
            className="card px-5 py-4 text-left hover:-translate-y-px hover:shadow-md">
            <div className="flex items-start justify-between">
              <span className="text-[14px] font-bold text-app-navy">Signals</span>
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-crm-orange-light text-crm-orange-dark"><Radio className="h-5 w-5" /></span>
            </div>
            <div className="mt-3 text-[26px] font-bold text-app-navy tabular-nums">{data.signals.length}</div>
            <div className="text-[11px] text-slate-400">heard on this call · click to see them</div>
          </button>
          {AREAS.map((a) => (
            <div key={a.key} className="card px-5 py-4">
              <div className="flex items-start justify-between">
                <span className="text-[14px] font-bold text-app-navy">{a.label}</span>
                <span className={`grid h-9 w-9 place-items-center rounded-lg ${a.tone}`}>{a.icon}</span>
              </div>
              <div className={`mt-3 text-[26px] font-bold tabular-nums ${scoreTone(data.scores[a.key])}`}>{Math.round(data.scores[a.key])}%</div>
              <div className="text-[11px] text-slate-400">demo score</div>
            </div>
          ))}
        </div>

        <section className="card px-5 pt-5 pb-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-violet-50 text-violet-600"><ClipboardCheck className="h-5 w-5" /></span>
              <div>
                <h2 className="text-[15px] font-bold tracking-wide text-app-navy uppercase">QA feedback scores</h2>
                <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">Manual quality assessment</p>
              </div>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-50 px-3 py-1 text-[10px] font-bold tracking-widest text-violet-600 uppercase ring-1 ring-violet-200">
              <span className="h-1.5 w-1.5 rounded-full bg-violet-500" /> Not available
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
            {[{ key: 'overall', label: 'Signals reviewed', icon: <Radio className="h-5 w-5" />, tone: 'bg-crm-orange-light text-crm-orange-dark' }, ...AREAS].map((a) => (
              <div key={a.key} className="relative overflow-hidden rounded-xl border border-slate-200 bg-white px-4 pt-4 pb-3">
                <span className="absolute -top-7 -right-7 h-16 w-16 rounded-full bg-violet-50" />
                <span className={`relative grid h-9 w-9 place-items-center rounded-lg ${a.tone}`}>{a.icon}</span>
                <div className="relative mt-4 text-[12px] font-bold tracking-wide text-slate-600 uppercase">{a.label}</div>
                <div className="relative mt-1 text-[20px] font-bold text-slate-300">--</div>
                <div className="relative mt-3 flex items-center justify-between border-t border-slate-100 pt-2 text-[10px] font-semibold uppercase">
                  <span className="text-slate-400">● QA score</span>
                  <span className="text-violet-600">Feedback</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <TimelinePlayer data={data} />
      </div>
    </div>
  );
}

function TimelinePlayer({ data }: { data: any }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const duration = Math.max(1, data.duration_s);
  const who = useMemo(() => personas({ raw: { speakers: data.speakers } }), [data]);
  const lanes = useMemo(() => {
    const hub: any[] = [], other: any[] = [];
    for (const s of data.segments) {
      const p = who[speakerKey(s.speaker_label)];
      ((p ? p.hub : s.channel === 0) ? hub : other).push(s);
    }
    return { hub, other };
  }, [data, who]);
  const otherName = data.speakers.find((s: any) => !['hub_staff', 'nurse_educator', 'specialty_pharmacy'].includes(s.role))?.name;
  const hubName = data.speakers.find((s: any) => ['hub_staff', 'nurse_educator', 'specialty_pharmacy'].includes(s.role))?.name;

  useEffect(() => {
    const a = audio.current;
    if (!a) return;
    const tick = () => setT(a.currentTime);
    a.addEventListener('timeupdate', tick);
    return () => a.removeEventListener('timeupdate', tick);
  }, []);
  const seek = (s: number) => { if (audio.current) { audio.current.currentTime = Math.max(0, Math.min(duration, s)); setT(audio.current.currentTime); } };
  const toggle = () => (playing ? audio.current?.pause() : void audio.current?.play());
  const cycle = () => {
    const next = rate === 1 ? 1.5 : rate === 1.5 ? 2 : 1;
    setRate(next);
    if (audio.current) audio.current.playbackRate = next;
  };
  const pct = (s: number) => `${(100 * s) / duration}%`;
  const ticks = Array.from({ length: Math.floor(duration / 30) }, (_, i) => (i + 1) * 30);
  const speakers = new Set(data.segments.map((s: any) => speakerKey(s.speaker_label))).size;

  const Lane = ({ label, segs, color }: { label: string; segs: any[]; color: string }) => (
    <div className="grid grid-cols-[4.5rem_1fr] items-center gap-3">
      <span className="truncate text-[11px] font-medium text-slate-500">{label}</span>
      <div className="relative h-5">
        {segs.map((s) => {
          const start = Number(s.start_s ?? 0), end = Number(s.end_s ?? start + 1);
          const active = t >= start && t <= end;
          return (
            <button key={s.seq} type="button" onClick={() => seek(start)} title={`${fmtClock(start)} · ${s.text}`}
              className={`absolute top-0 h-5 rounded-full transition hover:brightness-110 ${active ? 'ring-2 ring-offset-1' : ''}`}
              style={{ left: pct(start), width: `max(6px, ${pct(end - start)})`, background: color, ['--tw-ring-color' as any]: color }} />
          );
        })}
      </div>
    </div>
  );

  return (
    <section className="card overflow-hidden border-l-4 border-l-crm-brand px-5 pt-5 pb-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-full bg-crm-brand-light text-crm-brand"><Activity className="h-5 w-5" /></span>
          <div>
            <h2 className="text-[15px] font-bold text-app-navy">Timeline analysis player</h2>
            <p className="text-[12px] text-slate-500">Click markers to jump to key moments · {fmtClock(duration)}</p>
          </div>
        </div>
        <div className="flex items-center gap-4 text-[11.5px] text-slate-600">
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-crm-brand" />{otherName ? `${otherName} (other party)` : 'Other party'}</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-violet-500" />{hubName ? `${hubName} (hub)` : 'Hub agent'}</span>
        </div>
      </div>

      <audio ref={audio} src={audioUrl(data.call_id)} preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} className="hidden" />
      <p className="mt-4 text-[12px] text-slate-500">Recording: <span className="font-semibold text-ok">✓ available</span></p>
      <div className="mt-3 flex items-center gap-3">
        <button type="button" onClick={() => seek(t - 10)} className="grid h-9 w-9 place-items-center rounded-full text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50" title="Back 10 s">
          <RotateCcw className="h-4 w-4" />
        </button>
        <button type="button" onClick={toggle} className="grid h-11 w-11 place-items-center rounded-full bg-crm-brand text-white shadow-md hover:bg-app-navy" title={playing ? 'Pause' : 'Play'}>
          {playing ? <Pause className="h-5 w-5" /> : <Play className="ml-0.5 h-5 w-5" />}
        </button>
        <button type="button" onClick={() => seek(t + 10)} className="grid h-9 w-9 place-items-center rounded-full text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50" title="Forward 10 s">
          <RotateCw className="h-4 w-4" />
        </button>
        <span className="font-mono text-[12px] text-slate-600">{fmtClock(t)} / {fmtClock(duration)}</span>
        <button type="button" onClick={cycle} className="rounded-md bg-slate-100 px-2 py-1 text-[11px] font-bold text-slate-600 hover:bg-slate-200">{rate}x</button>
      </div>

      <div className="mt-5 space-y-2">
        <Lane label={otherName ?? 'Speaker'} segs={lanes.other} color="#1a56a8" />
        <Lane label={hubName ?? 'Agent'} segs={lanes.hub} color="#8b5cf6" />
        <div className="grid grid-cols-[4.5rem_1fr] gap-3">
          <span />
          <div className="relative h-8 cursor-pointer rounded-md bg-slate-50" onClick={(e) => {
            const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
            seek(((e.clientX - r.left) / r.width) * duration);
          }}>
            <span className="absolute top-0 bottom-0 w-0.5 rounded bg-crm-brand" style={{ left: pct(t) }} />
            {ticks.map((s) => (
              <span key={s} className="absolute top-1 -translate-x-1/2 text-center text-[9px] text-slate-400" style={{ left: pct(s) }}>
                <span className="mx-auto block h-2 w-px bg-slate-300" />{fmtClock(s).replace(/^0/, '')}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-6 border-t border-slate-100 pt-3 text-[12px] text-slate-500">
        <span className="inline-flex items-center gap-1.5"><MessageSquareText className="h-4 w-4" />{data.segments.length} segments</span>
        <span className="inline-flex items-center gap-1.5"><Users className="h-4 w-4" />{speakers} speakers</span>
        <Link to={`/calls/${data.call_id}`} className="ml-auto font-semibold text-crm-brand hover:underline">Full transcript & signals →</Link>
      </div>
    </section>
  );
}
