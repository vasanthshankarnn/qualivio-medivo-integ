/* eslint-disable @typescript-eslint/no-explicit-any */
import { Link } from 'react-router-dom';

import { Badge, Card, ErrorBox, Loading, PageHeader, Table } from '../components/ui';
import { useCalls, useMaster, usePatients } from '../lib/api';
import { PARTY_LABEL, fmtDateTime } from '../lib/format';

const STATUS_TONE: Record<string, string> = {
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  failed: 'bg-rose-50 text-rose-700 ring-rose-200',
};

export default function CallsPage() {
  const calls = useCalls();
  const patients = usePatients();
  const master = useMaster();
  if (calls.isLoading) return <Loading />;
  if (calls.error) return <ErrorBox error={calls.error} />;
  const patientName = (id: string) => patients.data?.find((p: any) => p.patient_id === id)?.patient_name ?? '—';
  const practiceName = (id: string) => master.data?.practices.find((p: any) => p.practice_id === id)?.practice_name ?? '—';

  return (
    <>
      <PageHeader title="All calls" subtitle="Every analysed conversation with the labels it was resolved to (patient, practice, payer, program)."
        actions={<Link to="/upload" className="rounded-md bg-crm-orange px-3 py-2 text-sm font-medium text-white hover:bg-crm-orange-dark">Analyse a call</Link>} />
      <div className="px-8 pb-8">
        <Card>
          <Table head={['Call', 'Date', 'With', 'Patient', 'Practice', 'Stage', 'Signals', 'Transcript', 'Status']}>
            {calls.data?.map((c: any) => (
              <tr key={c.call_id} className="hover:bg-crm-row-hover">
                <td className="px-3 py-2"><Link to={`/calls/${c.call_id}`} className="link font-medium">{c.external_call_id ?? c.call_id.slice(0, 8)}</Link></td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDateTime(c.call_datetime)}</td>
                <td className="px-3 py-2">{PARTY_LABEL[c.other_party_type] ?? '—'}</td>
                <td className="px-3 py-2">{c.patient_id ? patientName(c.patient_id) : '—'}</td>
                <td className="px-3 py-2">{c.practice_id ? practiceName(c.practice_id) : '—'}</td>
                <td className="px-3 py-2">{c.journey_stage ?? '—'}</td>
                <td className="px-3 py-2">{c.signal_count}</td>
                <td className="px-3 py-2 text-slate-500">{c.transcript_source === 'azure' ? 'From audio' : c.transcript_source === 'provided' ? 'Supplied' : '—'}</td>
                <td className="px-3 py-2"><Badge tone={STATUS_TONE[c.status] ?? 'bg-sky-50 text-sky-700 ring-sky-200'}>{c.status}</Badge></td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
    </>
  );
}
