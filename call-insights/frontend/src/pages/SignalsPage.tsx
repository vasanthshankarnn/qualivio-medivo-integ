/* eslint-disable @typescript-eslint/no-explicit-any */
import { Card, ErrorBox, Loading, PageHeader, SignalChip, Table } from '../components/ui';
import { useSignals } from '../lib/api';

export default function SignalsPage() {
  const { data, isLoading, error } = useSignals();
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <>
      <PageHeader title="Signal library" subtitle="What the AI listens for on every call (Conversational Signal Library, S01-S38)." />
      <div className="px-8 pb-8">
        <Card>
          <Table head={['Signal', 'Stage', 'What it means', 'Who says it', 'Example']}>
            {data?.map((s: any) => (
              <tr key={s.signal_id} className="align-top hover:bg-crm-row-hover">
                <td className="px-3 py-2"><SignalChip id={s.signal_id} name={s.signal_name} type={s.insight_type} /></td>
                <td className="px-3 py-2 text-slate-600">{s.journey_stage}</td>
                <td className="max-w-md px-3 py-2 text-slate-700">{s.meaning}{s.rule_based && <span className="ml-1 text-xs text-slate-400">(cross-call rule)</span>}</td>
                <td className="px-3 py-2 text-slate-600">{s.who_says}</td>
                <td className="max-w-sm px-3 py-2 text-slate-500">{s.example_line}</td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
    </>
  );
}
