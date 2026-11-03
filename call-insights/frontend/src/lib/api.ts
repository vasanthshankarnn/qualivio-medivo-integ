/* eslint-disable @typescript-eslint/no-explicit-any */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useFilters, withParams } from './filters';

// Empty = same origin (Vite dev proxy forwards /v1 to the API). Set VITE_API_URL for a separately hosted API.
export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export async function post<T>(path: string, body?: BodyInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { method: 'POST', body });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const audioUrl = (callId: string) => `${API_URL}/v1/calls/${callId}/audio`;

/** One conversation excerpt behind a number (the deck's "evidence drawer"). */
export type Evidence = {
  call_id: string;
  external_call_id: string;
  date: string;
  patient_id?: string | null;
  patient_name?: string | null;
  party?: string;
  practice_name?: string | null;
  payer_name?: string | null;
  stage?: string | null;
  quote?: string | null;
  label?: string | null;
  mock?: boolean;
  pharmacy?: string | null;
  type?: string;
  with?: string;
  entity?: string;
};

export type Vs = { normal: number; delta: number; direction: 'up' | 'down' | 'flat' } | null;
export type RateVs = { text: string; direction: 'up' | 'down' | 'flat'; score: number; detail: string };

export type Insight = {
  insight_id: number;
  insight_key: string;
  rule_id: string;
  level: string;
  subject_type: string;
  subject_id: string;
  title: string;
  detail: string;
  score: number | null;
  band: string | null;
  evidence: { call_id: string; external_call_id: string; date: string; signals: string[]; quote?: string | null }[];
  action: string;
  owner_team: string;
  owner: string;
  status: string;
  useful: boolean | null;
  action_date: string | null;
  action_note: string | null;
  priority?: string;
  insight_type?: string;
  patient?: { patient_id: string; patient_name: string } | null;
};

const screen = (name: string, path: string) =>
  function useScreen() {
    const { qs } = useFilters();
    return useQuery({ queryKey: [name, qs], queryFn: () => get<any>(`${path}${qs}`), placeholderData: (prev) => prev });
  };

export const useOverview = screen('overview', '/v1/dashboard/overview');
export const useSummary = screen('summary', '/v1/dashboard/summary');
export const useExecutive = screen('executive', '/v1/dashboard/executive');
export const useHubQuality = screen('hub-quality', '/v1/dashboard/hub-quality');
// The Summary boxes as their own tabs
export const useStuck = screen('stuck', '/v1/dashboard/stuck');
export const useAccessIssues = screen('access-issues', '/v1/dashboard/access-issues');
export const useAtRisk = screen('at-risk', '/v1/dashboard/at-risk');
export function useAccessIssue(key?: string) {
  const { qs } = useFilters();
  return useQuery({ queryKey: ['access-issue', qs, key], enabled: !!key,
    queryFn: () => get<any>(`/v1/dashboard/access-issues/${encodeURIComponent(key ?? '')}${qs}`) });
}
export function useCallSummary(direction: string, party: string) {
  const { qs } = useFilters();
  const q = withParams(qs, { direction, party });
  return useQuery({ queryKey: ['call-summary', q], queryFn: () => get<any>(`/v1/dashboard/call-summary${q}`), placeholderData: (prev) => prev });
}
export function usePatientCalls(patient: string) {
  const { qs } = useFilters();
  const q = patient ? `${qs ? `${qs}&` : '?'}patient=${encodeURIComponent(patient)}` : qs;
  return useQuery({ queryKey: ['patient-calls', qs, patient], queryFn: () => get<any>(`/v1/dashboard/patient-calls${q}`), placeholderData: (prev) => prev });
}
export const useConversation = (id?: string | null) =>
  useQuery({ queryKey: ['conversation', id], queryFn: () => get<any>(`/v1/calls/${id}/conversation`), enabled: !!id });
export const useAccess = screen('access', '/v1/dashboard/access');
export const useFollowThrough = screen('follow', '/v1/dashboard/follow-through');
export const useSafety = screen('safety', '/v1/dashboard/safety');
export const useAlerts = screen('alerts', '/v1/alerts');
export const useBrief = screen('brief', '/v1/brief');

export const usePatients = () => useQuery({ queryKey: ['patients'], queryFn: () => get<any[]>('/v1/patients') });
export const useJourney = (id?: string) =>
  useQuery({ queryKey: ['journey', id], queryFn: () => get<any>(`/v1/patients/${id}/journey`), enabled: !!id });
export const useCalls = () =>
  useQuery({
    queryKey: ['calls'],
    queryFn: () => get<any[]>('/v1/calls'),
    refetchInterval: (q) => ((q.state.data ?? []).some((c: any) => !['completed', 'failed'].includes(c.status)) ? 4000 : false),
  });
export const useCall = (id?: string) =>
  useQuery({
    queryKey: ['call', id],
    queryFn: () => get<any>(`/v1/calls/${id}`),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data && !['completed', 'failed'].includes(q.state.data.call.status) ? 4000 : false),
  });
export const useMaster = () => useQuery({ queryKey: ['master'], queryFn: () => get<any>('/v1/master'), staleTime: 300_000 });
export const useActions = () => useQuery({ queryKey: ['actions'], queryFn: () => get<any[]>('/v1/actions') });
export const useSignals = () => useQuery({ queryKey: ['signals'], queryFn: () => get<any[]>('/v1/signals') });
export const useRuleWeights = () => useQuery({ queryKey: ['rule-weights'], queryFn: () => get<any[]>('/v1/rule-weights') });

export type ActionUpdate = {
  insight_key: string;
  status?: string;
  owner?: string;
  action_note?: string;
  action_date?: string;
  useful?: boolean | null;
};

/** Status / owner / "was this useful?" on an insight. Every screen refreshes afterwards. */
export function useUpdateAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ActionUpdate) => postJson('/v1/insights/action', body),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useReviewSafety() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { safety_key: string; status: string }) => postJson('/v1/safety/review', body),
    onSuccess: () => qc.invalidateQueries(),
  });
}
