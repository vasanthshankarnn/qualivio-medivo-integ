/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, Card, ErrorBox, Loading, PageHeader, Table } from '../components/ui';
import { post, useActions, useRuleWeights } from '../lib/api';
import { RULE_LABEL } from '../lib/format';

export default function RulesPage() {
  const actions = useActions();
  const weights = useRuleWeights();
  const qc = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);
  if (actions.isLoading) return <Loading />;
  if (actions.error) return <ErrorBox error={actions.error} />;

  async function recompute() {
    const r = await post<any>('/v1/insights/recompute');
    setMsg(`Recomputed as of ${r.as_of}: ${Object.entries(r.insights).map(([k, v]) => `${RULE_LABEL[k] ?? k} ${v}`).join(' · ')}`);
    await qc.invalidateQueries();
  }

  return (
    <>
      <PageHeader title="Rules & actions"
        subtitle="Deterministic: each rule groups calls by a label, checks its condition, and fires exactly one next best action. No AI decides actions."
        actions={<button type="button" onClick={recompute} className="rounded-md bg-app-navy px-3 py-2 text-sm font-medium text-white hover:opacity-90">Recompute insights</button>} />
      <div className="space-y-5 px-8 pb-8">
        {msg && <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{msg}</div>}
        <Card title="Rule → next best action" subtitle="Draft from the proposal (slide 11) and the cross-call rules; to be confirmed with Ipsen">
          <Table head={['Rule', 'Insight type', 'When it fires', 'Next best action', 'Owner', 'Priority', 'Source']}>
            {actions.data?.map((a: any) => (
              <tr key={a.rule_id} className="align-top hover:bg-crm-row-hover">
                <td className="px-3 py-2"><Badge tone="bg-crm-brand-light text-crm-brand-dark ring-blue-200">{a.rule_id}</Badge></td>
                <td className="px-3 py-2">{a.insight_type}</td>
                <td className="px-3 py-2 font-medium">{a.title}</td>
                <td className="max-w-md px-3 py-2 text-slate-700">{a.action}</td>
                <td className="px-3 py-2">{a.owner_team}</td>
                <td className="px-3 py-2">{a.priority}</td>
                <td className="px-3 py-2 text-xs text-slate-500">{a.source}</td>
              </tr>
            ))}
          </Table>
        </Card>
        {weights.data && (
          <div className="grid gap-5 lg:grid-cols-2">
            {['R3', 'R2'].map((rule) => (
              <Card key={rule} title={`${RULE_LABEL[rule]} weights (${rule})`}
                subtitle={weights.data.find((w: any) => w.rule_id === rule)?.source}>
                <div className="flex flex-wrap gap-2">
                  {weights.data.filter((w: any) => w.rule_id === rule).map((w: any) => (
                    <Badge key={w.signal_id}>{w.signal_id} {w.signal_name}: {Number(w.weight) > 0 ? '+' : ''}{Number(w.weight)}</Badge>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
