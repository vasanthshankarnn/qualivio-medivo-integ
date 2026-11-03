/* eslint-disable @typescript-eslint/no-explicit-any */
import { Sparkles } from 'lucide-react';

const ROLE_LABEL: Record<string, string> = {
  hub_staff: 'Hub',
  nurse_educator: 'Nurse educator',
  specialty_pharmacy: 'Specialty pharmacy',
  patient: 'Patient',
  caregiver: 'Caregiver',
  provider_office: 'Office',
  payer: 'Payer',
  voicemail_greeting: 'Voicemail',
  other: 'Other',
};
const HUB_ROLES = new Set(['hub_staff', 'nurse_educator', 'specialty_pharmacy']);

/** "Channel 0 (hub staff)", "Channel 0", "Speaker 1", "Guest-1" -> "channel 0" / "speaker 1": the AI may shorten labels. */
export const speakerKey = (label: string) => {
  const m = /(channel|speaker|guest)\s*-?\s*(\d+)/i.exec(label ?? '');
  return m ? `${m[1].toLowerCase() === 'guest' ? 'speaker' : m[1].toLowerCase()} ${m[2]}` : (label ?? '').trim().toLowerCase();
};

export type Persona = { name: string | null; role: string; roleLabel: string; hub: boolean };

/** Speaker label in the transcript -> who the AI says it is (name + role). Works for mono (diarized) and stereo calls. */
export function personas(extraction: any): Record<string, Persona> {
  const out: Record<string, Persona> = {};
  for (const s of extraction?.raw?.speakers ?? []) {
    out[speakerKey(s.label)] = { name: s.name || null, role: s.role, roleLabel: ROLE_LABEL[s.role] ?? s.role, hub: HUB_ROLES.has(s.role) };
  }
  return out;
}

/** Name + role for a transcript line, with a small flag saying how we know who is speaking. */
export function SpeakerTag({ seg, map, compact }: { seg: any; map: Record<string, Persona>; compact?: boolean }) {
  const p = map[speakerKey(seg.speaker_label)];
  const fromChannel = seg.channel !== null && seg.channel !== undefined;
  const hub = p ? p.hub : seg.channel === 0;
  const title = fromChannel
    ? `Channel ${seg.channel} of a stereo recording${p ? ` · identified as ${p.roleLabel}` : ''}`
    : `Mono recording: “${seg.speaker_label}” identified by AI from the conversation${p ? ` as ${p.roleLabel}` : ''}`;
  return (
    <span className={`flex shrink-0 items-start gap-1 ${compact ? 'w-32' : 'w-44'}`} title={title}>
      <span className="min-w-0">
        <span className={`block truncate font-semibold ${hub ? 'text-app-navy' : 'text-crm-teal'}`}>
          {p?.name ?? p?.roleLabel ?? seg.speaker_label}
        </span>
        {p && <span className="block truncate text-[11px] text-slate-400">{p.name ? p.roleLabel : seg.speaker_label}</span>}
      </span>
      {fromChannel ? (
        <span className="mt-0.5 rounded bg-slate-100 px-1 text-[9px] font-bold text-slate-500">CH{seg.channel}</span>
      ) : (
        <span className="mt-0.5 inline-flex items-center gap-0.5 rounded bg-violet-50 px-1 text-[9px] font-bold text-violet-600 ring-1 ring-violet-200">
          <Sparkles className="h-2.5 w-2.5" />AI
        </span>
      )}
    </span>
  );
}

export const isMono = (segments: any[]) => segments.length > 0 && segments.every((s) => s.channel === null || s.channel === undefined);
