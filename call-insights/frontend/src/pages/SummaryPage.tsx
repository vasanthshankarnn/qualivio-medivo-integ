/* eslint-disable @typescript-eslint/no-explicit-any */
import { ArrowUp, ChevronRight } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useEvidence } from '../components/evidence';
import { ErrorBox, Loading, ScreenHeader, SourceNote } from '../components/ui';
import { useSummary } from '../lib/api';
import { useFilters, withParams } from '../lib/filters';
import { lowerFirst, pctText, periodWord, plural } from '../lib/format';

/** Executive summary – one page for leaders; every box opens its own tab (Neil, 16 Oct review). Every number on the
 *  page is a slice of the same calls: by stage, by issue, by patient at risk, by reason. */
const STAGE_TONE: Record<string, string> = {
  green: 'bg-[#1e8e3e]',
  amber: 'bg-[#e8a317]',
  red: 'bg-[#c0392b]',
  none: 'bg-slate-200',
};
const plainStage = (s: string) => s.replace(' & appeal', '').replace(' & first fill', '').replace(' & assistance', '');

export default function SummaryPage() {
  const { data, error } = useSummary();
  const { f, qs } = useFilters();
  const open = useEvidence();
  const navigate = useNavigate();
  if (!data) return error ? <ErrorBox error={error} /> : <Loading />;
  const { stuck, issues, risk, glance } = data;
  const slow = stuck.slowest;
  const total = glance.conversations.value;
  const maxReason = Math.max(1, ...data.reasons.map((r: any) => r.count));
  const maxRisk = Math.max(1, ...risk.reasons.map((r: any) => r.patients));
  const conv = glance.conversations;
  const fcrBelow = glance.fcr.value !== null && glance.fcr.target && glance.fcr.value < glance.fcr.target;
  const repeatUp = glance.repeat.vs?.direction === 'up';
  const se = glance.side_effects;
  const when = periodWord(f.days);
  const slowCalls = slow ? stuck.stages.find((s: any) => s.stage === slow.stage)?.calls : 0;

  return (
    <>
      <ScreenHeader title="Executive summary" subtitle="Ipsen's three objectives at a glance. Click any box for the detail."
        actions={
          <span className="rounded-full bg-white px-4 py-1.5 text-[13px] font-semibold text-app-navy ring-1 ring-slate-200">
            {total.toLocaleString()} calls · {when}
          </span>
        } />
      <div className="space-y-6 px-8 pb-6">
        <div className="grid gap-5 xl:grid-cols-3">
          <SummaryCard title="Where patients get stuck" link={{ to: `/stages${qs}`, label: 'See stages' }}>
            <div className="mb-2 text-[12px] text-slate-500">{total} calls by stage</div>
            <div className="grid grid-cols-7 gap-1.5">
              {stuck.stages.map((s: any) => (
                <button key={s.stage} type="button"
                  onClick={() => navigate(`/stages${withParams(qs, { focus: s.slug })}`)}
                  title={`${s.stage}: ${plural(s.calls, 'call')} · ${plural(s.patients, 'patient')} now`}
                  className="group text-center">
                  <span className={`grid h-12 place-items-center rounded text-[15px] font-bold text-white tabular-nums transition group-hover:opacity-85 ${STAGE_TONE[s.status]}`}>
                    {s.calls}
                  </span>
                  <span className="mt-1.5 block text-[10.5px] leading-tight tracking-tight whitespace-nowrap text-slate-500">{s.short}</span>
                </button>
              ))}
            </div>
            {slow ? (
              <button type="button" onClick={() => navigate(`/stages${withParams(qs, { focus: slow.slug })}`)}
                className="mt-4 block text-left">
                <span className="block text-[17px] font-semibold text-[#c0392b]">{plainStage(slow.stage)} is the slowest stage</span>
                <span className="mt-0.5 block text-[14px] text-slate-700">
                  {plural(slowCalls, 'call')} · {slow.waiting} waiting {stuck.wait_days}+ days
                </span>
                {slow.top_reason && <span className="mt-0.5 block text-[13px] text-slate-500">Top reason: {lowerFirst(slow.top_reason)}</span>}
              </button>
            ) : <p className="mt-4 text-[14px] text-slate-600">No one waiting {stuck.wait_days}+ days.</p>}
          </SummaryCard>

          <SummaryCard title="Emerging access issues" link={{ to: `/access-issues${qs}`, label: 'See issues' }}>
            <div className="flex items-baseline gap-2.5">
              <span className="text-[44px] leading-none font-semibold text-crm-orange tabular-nums">{issues.count}</span>
              <span className="text-[15px] text-slate-600">emerging {when}</span>
            </div>
            <div className="mt-1 text-[12.5px] text-slate-500">heard on {issues.calls} of {total} calls</div>
            <ul className="mt-3 space-y-2.5">
              {issues.top.map((t: any) => (
                <li key={t.key}>
                  <button type="button" onClick={() => navigate(`/access-issues/${encodeURIComponent(t.key)}${qs}`)} className="flex w-full items-start gap-2.5 text-left hover:opacity-80">
                    <ArrowUp className="mt-0.5 h-5 w-5 shrink-0 text-[#c0392b]" strokeWidth={3} />
                    <span className="min-w-0 flex-1 text-[14px] leading-snug text-slate-800">{t.label}</span>
                    <span className="shrink-0 text-[14px] font-semibold whitespace-nowrap text-[#c0392b]">{t.vs}</span>
                  </button>
                </li>
              ))}
              {issues.top.length === 0 && <li className="text-sm text-slate-500">Nothing above normal.</li>}
            </ul>
          </SummaryCard>

          <SummaryCard title="Patients at risk of dropping off" link={{ to: `/at-risk${qs}`, label: 'See patients' }}>
            <button type="button" onClick={() => navigate(`/at-risk${qs}`)} className="flex items-baseline gap-2.5 text-left">
              <span className="text-[44px] leading-none font-semibold text-[#0f7c80] tabular-nums">{risk.patients}</span>
              <span className="text-[15px] text-slate-600">{risk.patients === 1 ? 'patient' : 'patients'} · {risk.new_this_week} new</span>
            </button>
            <div className="mt-1 text-[12.5px] text-slate-500">raised on {risk.calls} of {total} calls</div>
            <div className="mt-3 space-y-2">
              {risk.reasons.map((r: any) => (
                <button key={r.reason} type="button" onClick={() => navigate(`/at-risk${withParams(qs, { cat: r.key })}`)}
                  className="grid w-full grid-cols-[11.5rem_1fr_2rem] items-center gap-3 text-left hover:opacity-80">
                  <span className="truncate text-[14px] text-slate-700">{r.reason}</span>
                  <span className="h-4 rounded-sm bg-slate-100">
                    <span className="block h-4 rounded-sm bg-[#0f7c80]" style={{ width: `${(100 * r.patients) / maxRisk}%` }} />
                  </span>
                  <span className="text-[13px] font-semibold text-[#0f7c80] tabular-nums">{r.patients}</span>
                </button>
              ))}
              {risk.reasons.length === 0 && <p className="text-sm text-slate-500">No drop-off signals.</p>}
            </div>
          </SummaryCard>
        </div>

        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-[17px] font-semibold text-app-navy">Hub at a glance</h2>
            <Link to={`/hub${qs}`} className="inline-flex items-center gap-0.5 text-[14px] font-semibold text-crm-orange-dark hover:underline">
              See hub quality <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
            <GlanceTile bar="bg-slate-500" value={conv.value.toLocaleString()} label="calls"
              sub={conv.change_pct !== null && conv.previous >= 5
                ? <span className="font-semibold text-slate-600">{conv.change_pct >= 0 ? '▲' : '▼'} {Math.abs(conv.change_pct)}% vs previous</span>
                : <span className="text-slate-500">{when}</span>}
              onClick={() => open('Calls', conv.evidence)} />
            <GlanceTile bar={fcrBelow ? 'bg-[#e8a317]' : 'bg-[#1e8e3e]'} value={pctText(glance.fcr.value)} label="first-call resolution"
              sub={<span className={`font-semibold ${fcrBelow ? 'text-[#c98a0b]' : 'text-[#1e8e3e]'}`}>
                {glance.fcr.resolved} of {glance.fcr.of} answered{glance.fcr.target ? ` · target ${glance.fcr.target}%` : ''}</span>}
              onClick={() => open('First-call resolution', glance.fcr.evidence)} />
            <GlanceTile bar={repeatUp ? 'bg-[#e8a317]' : 'bg-[#1e8e3e]'} value={pctText(glance.repeat.value)} label="repeat calls (7 days)"
              sub={glance.repeat.vs && <span className={`font-semibold ${repeatUp ? 'text-[#c98a0b]' : 'text-[#1e8e3e]'}`}>
                {glance.repeat.vs.delta >= 0 ? '▲' : '▼'} {Math.abs(glance.repeat.vs.delta)} pts vs normal</span>}
              onClick={() => open('Repeat calls within 7 days', glance.repeat.evidence)} />
            <GlanceTile bar="bg-slate-500" value={glance.avg_call.minutes !== null ? `${glance.avg_call.minutes} min` : '—'} label="average call"
              sub={glance.avg_call.longest && <span className="font-semibold text-slate-600">longest: {lowerFirst(glance.avg_call.longest.split(' & ')[0])}</span>} />
            <GlanceTile bar={se.awaiting ? 'bg-[#e8a317]' : 'bg-[#1e8e3e]'} value={se.value} label={se.value === 1 ? 'possible side effect' : 'possible side effects'}
              sub={<span className={`font-semibold ${se.awaiting ? 'text-[#c98a0b]' : 'text-[#1e8e3e]'}`}>
                {se.value === 0 ? 'none heard' : se.awaiting ? `${se.awaiting} to review` : 'all reviewed'}</span>}
              onClick={se.value ? () => open('Possible side effects', se.evidence) : undefined} />
          </div>
        </section>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,11fr)_minmax(0,9fr)]">
          <section className="card px-5 pt-4 pb-5">
            <div className="flex items-baseline justify-between">
              <h2 className="text-[17px] font-semibold text-app-navy">Why they called <span className="ml-1 text-[13px] font-normal text-slate-500">{total} calls</span></h2>
              <Link to={`/call-summary${qs}`} className="inline-flex items-center gap-0.5 text-[14px] font-semibold text-crm-orange-dark hover:underline">
                See call summary <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="mt-4 space-y-2">
              {data.reasons.map((r: any, i: number) => (
                <button key={r.reason} type="button" onClick={() => navigate(`/call-summary${withParams(qs, { reason: r.reason })}`)}
                  className="grid w-full grid-cols-[14rem_1fr_3rem] items-center gap-4 text-left hover:opacity-85">
                  <span className="truncate text-[14px] text-slate-700">{r.reason}</span>
                  <span className="flex items-center gap-2">
                    <span className={`h-4 rounded-sm ${i === 0 ? 'bg-crm-orange' : 'bg-app-navy'}`} style={{ width: `${Math.max(3, (85 * r.count) / maxReason)}%` }} />
                    <span className="text-[13px] font-semibold text-app-navy tabular-nums">{r.count.toLocaleString()}</span>
                  </span>
                  <span className="text-right text-[12.5px] text-slate-500 tabular-nums">{r.share}%</span>
                </button>
              ))}
            </div>
          </section>
          <section className="card px-5 pt-4 pb-5">
            <h2 className="text-[17px] font-semibold text-app-navy">What changed {when}</h2>
            <ul className="mt-3 space-y-1">
              {data.what_changed.map((l: any, i: number) => (
                <li key={i}>
                  <button type="button" onClick={() => open(l.text, l.evidence)}
                    className="flex w-full gap-2.5 rounded-md px-1 py-1.5 text-left text-[14px] leading-snug text-slate-700 hover:bg-slate-50">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-500" />{l.text}
                  </button>
                </li>
              ))}
              {data.what_changed.length === 0 && <li className="text-sm text-slate-500">All within normal range.</li>}
            </ul>
          </section>
        </div>
      </div>
      <SourceNote><b>Source:</b> call recordings.</SourceNote>
    </>
  );
}

function SummaryCard({ title, link, children }: { title: string; link: { to: string; label: string }; children: ReactNode }) {
  return (
    <section className="card flex flex-col px-5 pt-4 pb-4">
      <h2 className="mb-3 text-[17px] font-semibold text-app-navy">{title}</h2>
      <div className="flex-1">{children}</div>
      <Link to={link.to} className="mt-4 inline-flex items-center gap-0.5 self-start text-[14px] font-semibold text-crm-orange-dark hover:underline">
        {link.label} <ChevronRight className="h-4 w-4" />
      </Link>
    </section>
  );
}

function GlanceTile({ bar, value, label, sub, onClick }: { bar: string; value: ReactNode; label: string; sub?: ReactNode; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick}
      className={`flex overflow-hidden rounded-xl border border-slate-200 bg-white text-left shadow-[0_1px_2px_rgba(1,52,118,.04),0_6px_18px_-10px_rgba(1,52,118,.12)] transition ${onClick ? 'hover:-translate-y-px hover:shadow-md' : 'cursor-default'}`}>
      <span className={`w-1.5 shrink-0 ${bar}`} />
      <span className="px-4 py-3.5">
        <span className="block text-[28px] leading-none font-semibold text-app-navy tabular-nums">{value}</span>
        <span className="mt-1.5 block text-[14px] text-slate-700">{label}</span>
        {sub && <span className="mt-0.5 block text-[12.5px]">{sub}</span>}
      </span>
    </button>
  );
}
