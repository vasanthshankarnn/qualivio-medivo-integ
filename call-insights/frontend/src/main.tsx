import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { EvidenceProvider } from './components/evidence';
import './index.css';
import AccessPage from './pages/AccessPage';
import CallDetailPage from './pages/CallDetailPage';
import CallSummaryPage from './pages/CallSummaryPage';
import CallsPage from './pages/CallsPage';
import FollowThroughPage from './pages/FollowThroughPage';
import HubQualityPage from './pages/HubQualityPage';
import IssueDetailPage from './pages/IssueDetailPage';
import IssuesPage from './pages/IssuesPage';
import ConversationPage from './pages/ConversationPage';
import ExecutivePage from './pages/ExecutivePage';
import JourneyPage from './pages/JourneyPage';
import PatientCallsPage from './pages/PatientCallsPage';
import RiskPage from './pages/RiskPage';
import RulesPage from './pages/RulesPage';
import SafetyPage from './pages/SafetyPage';
import SignalsPage from './pages/SignalsPage';
import StuckPage from './pages/StuckPage';
import SummaryPage from './pages/SummaryPage';
import UploadPage from './pages/UploadPage';

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } });

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <EvidenceProvider>
          <AppShell>
            <Routes>
              <Route path="/" element={<SummaryPage />} />
              <Route path="/executive" element={<ExecutivePage />} />
              <Route path="/patient-dashboard" element={<PatientCallsPage />} />
              <Route path="/conversation" element={<ConversationPage />} />
              <Route path="/stages" element={<StuckPage />} />
              <Route path="/access-issues" element={<IssuesPage />} />
              <Route path="/access-issues/:key" element={<IssueDetailPage />} />
              <Route path="/at-risk" element={<RiskPage />} />
              <Route path="/call-summary" element={<CallSummaryPage />} />
              <Route path="/hub" element={<HubQualityPage />} />
              <Route path="/access" element={<AccessPage />} />
              <Route path="/journey" element={<JourneyPage />} />
              <Route path="/journey/:patientId" element={<JourneyPage />} />
              <Route path="/follow-through" element={<FollowThroughPage />} />
              <Route path="/safety" element={<SafetyPage />} />
              <Route path="/calls" element={<CallsPage />} />
              <Route path="/calls/:callId" element={<CallDetailPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/rules" element={<RulesPage />} />
              <Route path="/signals" element={<SignalsPage />} />
            </Routes>
          </AppShell>
        </EvidenceProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
