import { BookOpen, ListChecks, PhoneCall, Upload } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';

import { useFilters } from '../lib/filters';
import { TopBar } from './TopBar';

// Summary, then each Summary box as its own tab (Neil, 16 Oct review), then hub quality and the two Qualivio views.
const SCREENS = [
  { to: '/', label: 'Executive summary', match: ['/'] },
  { to: '/stages', label: 'Where patients get stuck', match: ['/stages'] },
  { to: '/access-issues', label: 'Emerging access issues', match: ['/access-issues', '/access'] },
  { to: '/at-risk', label: 'Patients at risk of dropping off', match: ['/at-risk', '/journey'] },
  { to: '/call-summary', label: 'Call summary', match: ['/call-summary'] },
  { to: '/hub', label: 'Hub quality', match: ['/hub', '/follow-through', '/safety'] },
  { to: '/executive', label: 'Call analysis', match: ['/executive'] },
  { to: '/patient-dashboard', label: 'Conversation analysis', match: ['/patient-dashboard', '/conversation'] },
];

const MORE = [
  { section: 'Calls', items: [{ to: '/calls', label: 'All calls', icon: PhoneCall }, { to: '/upload', label: 'Analyse a call', icon: Upload }] },
  { section: 'Configuration', items: [{ to: '/rules', label: 'Rules & actions', icon: ListChecks }, { to: '/signals', label: 'Signal library', icon: BookOpen }] },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { qs } = useFilters();
  const isActive = (match: string[]) => match.some((m) => (m === '/' ? pathname === '/' : pathname.startsWith(m)));
  return (
    <div className="flex h-full">
      <aside className="app-chrome flex w-[15.5rem] shrink-0 flex-col text-white">
        <div className="px-5 pt-6 pb-5">
          <img src="/medivo360-logo-white.svg" alt="Medivo360" className="h-9 w-auto object-contain object-left" />
          <div className="mt-2.5 text-[11px] font-semibold tracking-[0.18em] text-white/55 uppercase">Patient journey intelligence</div>
        </div>
        <nav className="flex-1 overflow-y-auto px-3">
          <div className="px-2 pb-2 text-[13px] font-bold text-white">Insight workspace</div>
          <div className="space-y-1">
            {SCREENS.map(({ to, label, match }) => (
              <Link key={to} to={{ pathname: to, search: qs }}
                className={`flex items-start gap-3 rounded-lg px-3 py-2.5 text-[14px] leading-snug transition ${
                  isActive(match) ? 'bg-crm-orange font-semibold text-white shadow-md shadow-black/10' : 'text-white/85 hover:bg-white/10 hover:text-white'
                }`}>
                {label}
              </Link>
            ))}
          </div>
          {MORE.map((g) => (
            <div key={g.section} className="mt-7">
              <div className="px-2 pb-1.5 text-[10px] font-bold tracking-widest text-white/50 uppercase">{g.section}</div>
              {g.items.map(({ to, label, icon: Icon }) => (
                <NavLink key={to} to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition ${isActive ? 'bg-white/15 font-semibold text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'}`}>
                  <Icon className="h-4 w-4 shrink-0" />
                  {label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="px-5 py-5 text-xs leading-relaxed text-white/65">
          <div className="text-[13px] font-semibold text-white">Refreshed daily</div>
          calls + connected channels
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto" data-app-scroll-container>
        <TopBar />
        <div key={pathname} className="page-in">{children}</div>
      </main>
    </div>
  );
}
