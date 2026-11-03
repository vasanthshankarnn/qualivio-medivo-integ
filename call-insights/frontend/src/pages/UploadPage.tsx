/* eslint-disable @typescript-eslint/no-explicit-any */
import { ArrowRight, Cloud, Database, FileAudio, FileText, Headphones, Plug, UploadCloud, X } from 'lucide-react';
import { useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

import { Card, PageHeader } from '../components/ui';
import { post, useMaster } from '../lib/api';

const field = 'mt-1 w-full rounded-md border border-[#cbd2dc] bg-white px-3 py-2 text-sm focus:border-crm-brand focus:outline-none focus:ring-2 focus:ring-crm-brand/30';

const size = (n: number) => (n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

/** Upload box: click to browse or drag a file in; shows the chosen file with a remove button. */
function DropZone({ file, onFile, accept, extensions, icon, title, hint, required }: {
  file: File | null; onFile: (f: File | null) => void; accept: string; extensions: string[]; icon: ReactNode;
  title: string; hint: string; required?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pick = (f?: File | null) => {
    if (!f) return;
    const ok = extensions.some((ext) => f.name.toLowerCase().endsWith(ext));
    setError(ok ? null : `Please choose a ${extensions.join(', ')} file.`);
    if (ok) onFile(f);
  };

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-crm-brand-light text-crm-brand">{icon}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-app-navy">{file.name}</span>
          <span className="text-xs text-slate-500">{size(file.size)} · ready to upload</span>
        </span>
        <button type="button" onClick={() => { onFile(null); if (input.current) input.current.value = ''; }}
          className="rounded-md p-1.5 text-slate-400 hover:bg-white hover:text-rose-600" title="Remove">
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }
  return (
    <div>
      <button type="button" onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files?.[0]); }}
        className={`flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-7 text-center transition
          ${over ? 'border-crm-brand bg-crm-brand-light/60' : 'border-slate-300 bg-slate-50/60 hover:border-crm-brand/60 hover:bg-crm-brand-light/30'}`}>
        <UploadCloud className={`h-8 w-8 ${over ? 'text-crm-brand' : 'text-slate-400'}`} />
        <span className="text-sm font-semibold text-app-navy">
          {title} {required && <span className="text-crm-orange">*</span>}
        </span>
        <span className="text-xs text-slate-500">Drag and drop here, or</span>
        <span className="rounded-lg bg-app-navy px-3.5 py-1.5 text-xs font-semibold text-white">Browse files</span>
        <span className="mt-1 text-[11px] text-slate-400">{hint}</span>
      </button>
      <input ref={input} type="file" accept={accept} className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
      {error && <p className="mt-1.5 text-xs text-rose-600">{error}</p>}
    </div>
  );
}

export default function UploadPage() {
  const master = useMaster();
  const navigate = useNavigate();
  const [audio, setAudio] = useState<File | null>(null);
  const [transcript, setTranscript] = useState<File | null>(null);
  const [form, setForm] = useState({ external_call_id: '', call_datetime: '', direction: 'Outbound', staff_id: '', case_id: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: any) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!audio) return;
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.append('audio', audio);
    if (transcript) body.append('transcript', transcript);
    Object.entries(form).forEach(([k, v]) => v && body.append(k, v));
    body.append('channel_layout', JSON.stringify({ 0: 'hub staff', 1: 'other party' }));
    try {
      const res = await post<{ call_id: string }>('/v1/calls', body);
      navigate(`/calls/${res.call_id}`);
    } catch (err) {
      setError(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Analyse a call"
        subtitle="Upload a recording. It is transcribed (one channel per party for stereo), analysed for signals, labelled, and added to the insights." />
      <div className="grid items-start gap-6 px-8 pb-8 xl:grid-cols-[minmax(0,46rem)_minmax(0,1fr)]">
      <form onSubmit={submit} className="space-y-5">
        <Card title="Recording" subtitle="Stereo with the hub agent on the left channel works best; mono works too (speakers are identified by AI).">
          <DropZone file={audio} onFile={setAudio} accept="audio/*,.mp3,.wav,.m4a" extensions={['.mp3', '.wav', '.m4a']}
            icon={<FileAudio className="h-5 w-5" />} title="Upload the call recording" hint="MP3, WAV or M4A" required />
          <div className="mt-5 border-t border-slate-100 pt-4">
            <div className="text-sm font-semibold text-app-navy">Transcript <span className="font-normal text-slate-400">(optional)</span></div>
            <p className="mb-2.5 text-xs text-slate-500">If supplied, transcription is skipped. Only lines in the form “[mm:ss] Speaker: text” are used; anything else in the file is ignored.</p>
            <DropZone file={transcript} onFile={setTranscript} accept=".txt,text/plain" extensions={['.txt']}
              icon={<FileText className="h-5 w-5" />} title="Upload a transcript" hint="TXT" />
          </div>
        </Card>
        <Card title="Call details" subtitle="What the phone system knows. Patient, practice, payer and stage are worked out from the conversation.">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm">Call ID<input className={field} value={form.external_call_id} onChange={set('external_call_id')} placeholder="e.g. DEMO-01" /></label>
            <label className="text-sm">Date and time<input type="datetime-local" className={field} value={form.call_datetime} onChange={set('call_datetime')} /></label>
            <label className="text-sm">Direction
              <select className={field} value={form.direction} onChange={set('direction')}><option>Outbound</option><option>Inbound</option></select>
            </label>
            <label className="text-sm">Hub agent
              <select className={field} value={form.staff_id} onChange={set('staff_id')}>
                <option value="">Not known</option>
                {master.data?.staff.map((s: any) => <option key={s.staff_id} value={s.staff_id}>{s.staff_name} · {s.role}</option>)}
              </select>
            </label>
            <label className="text-sm">Hub case ID (optional)<input className={field} value={form.case_id} onChange={set('case_id')} placeholder="e.g. 20455" /></label>
          </div>
        </Card>
        {error && <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
        <button type="submit" disabled={!audio || busy}
          className="inline-flex items-center gap-2 rounded-lg bg-crm-orange px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-crm-orange-dark disabled:cursor-not-allowed disabled:opacity-50">
          <UploadCloud className="h-4 w-4" />{busy ? 'Uploading…' : 'Analyse call'}
        </button>
      </form>
      <Sources />
      </div>
    </>
  );
}

const SOURCE_GROUPS: { title: string; icon: ReactNode; note: string; items: { name: string; tag: string }[] }[] = [
  {
    title: 'Contact-center platforms', icon: <Headphones className="h-4 w-4" />,
    note: 'Recordings and call metadata (agent, case, direction, channel layout) pulled automatically after each call.',
    items: [{ name: 'Genesys Cloud', tag: 'GC' }, { name: 'Amazon Connect', tag: 'AC' }, { name: 'NICE CXone', tag: 'NC' },
      { name: 'Five9', tag: 'F9' }, { name: 'Twilio Flex', tag: 'TF' }, { name: 'Avaya', tag: 'AV' }],
  },
  {
    title: 'Cloud storage & file drop', icon: <Cloud className="h-4 w-4" />,
    note: 'A watched folder: every new recording dropped there is picked up and analysed.',
    items: [{ name: 'Amazon S3', tag: 'S3' }, { name: 'Azure Blob Storage', tag: 'AZ' }, { name: 'Google Cloud Storage', tag: 'GS' },
      { name: 'SFTP', tag: 'FT' }],
  },
  {
    title: 'CRM & hub systems', icon: <Database className="h-4 w-4" />,
    note: 'Case, patient and program details from the hub record; insights and actions written back to the case.',
    items: [{ name: 'Medivo360', tag: 'M3' }, { name: 'Salesforce Health Cloud', tag: 'SF' }, { name: 'Veeva CRM', tag: 'VV' },
      { name: 'Microsoft Dynamics 365', tag: 'D3' }],
  },
];

/** Placeholder: other ways calls can arrive (shown in the demo as integration options, none connected yet). */
function Sources() {
  return (
    <div className="space-y-5 xl:sticky xl:top-20">
      <Card title={<span className="flex items-center gap-2"><Plug className="h-4 w-4 text-crm-orange" />Connect a source</span>}
        subtitle="Manual upload is for the demo. In production, calls arrive on their own from the systems the hub already uses.">
        <div className="space-y-5">
          <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50/60 px-4 py-3">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-emerald-600 text-white"><UploadCloud className="h-4 w-4" /></span>
            <span className="flex-1">
              <span className="block text-sm font-semibold text-app-navy">Manual upload</span>
              <span className="text-xs text-slate-500">Audio + optional transcript, one call at a time</span>
            </span>
            <span className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-[11px] font-semibold text-white">Connected</span>
          </div>
          {SOURCE_GROUPS.map((g) => (
            <div key={g.title}>
              <div className="flex items-center gap-2 text-sm font-semibold text-app-navy">{g.icon}{g.title}
                <span className="ml-auto rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-500">Planned</span></div>
              <p className="mt-0.5 mb-2.5 text-xs text-slate-500">{g.note}</p>
              <div className="grid grid-cols-2 gap-2">
                {g.items.map((i) => (
                  <div key={i.name} className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white px-3 py-2">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-slate-100 text-[11px] font-bold text-slate-600">{i.tag}</span>
                    <span className="min-w-0 flex-1 text-[13px] leading-tight font-medium text-slate-700">{i.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <p className="text-[11px] text-slate-400 italic">Connectors are set up with Ipsen during implementation; no external system is connected in this demo.</p>
        </div>
      </Card>
      <Card title="What happens after you upload">
        <ol className="flex flex-wrap items-center gap-2 text-[13px]">
          {['Transcribed', 'Speakers identified', 'Signals & labels', 'Cross-call rules', 'On the five screens'].map((step, i, all) => (
            <li key={step} className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-crm-brand-light px-3 py-1 font-medium text-crm-brand-dark">
                <span className="text-[11px] font-bold">{i + 1}</span>{step}
              </span>
              {i < all.length - 1 && <ArrowRight className="h-3.5 w-3.5 text-slate-300" />}
            </li>
          ))}
        </ol>
        <p className="mt-3 text-xs text-slate-500">Usually 2–3 minutes per call. The call page refreshes itself while it runs.</p>
      </Card>
    </div>
  );
}
