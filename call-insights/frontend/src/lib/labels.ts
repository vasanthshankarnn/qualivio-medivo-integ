/* eslint-disable @typescript-eslint/no-explicit-any */
import { useMaster, usePatients } from './api';

/** Turns an insight subject (patient / practice / case / call id) into a readable label and link. */
export function useSubjectLabel() {
  const master = useMaster();
  const patients = usePatients();
  return (subjectType: string, subjectId: string): { label: string; to?: string } => {
    if (subjectType === 'patient') {
      const p = patients.data?.find((x: any) => x.patient_id === subjectId);
      return { label: p?.patient_name ?? subjectId, to: `/journey/${subjectId}` };
    }
    if (subjectType === 'case') {
      const p = patients.data?.find((x: any) => x.case_id === subjectId);
      return { label: p ? `Case ${subjectId} · ${p.patient_name}` : `Case ${subjectId}`, to: p ? `/journey/${p.patient_id}` : undefined };
    }
    if (subjectType === 'practice') {
      const p = master.data?.practices.find((x: any) => x.practice_id === subjectId);
      return { label: p?.practice_name ?? subjectId, to: '/access' };
    }
    return { label: `Call ${subjectId}` };
  };
}
