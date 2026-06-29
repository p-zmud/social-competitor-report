import { useEffect, useState } from 'react';
import { useReportStore } from './store/useReportStore';
import Sidebar from './components/Sidebar';
import ReportView from './components/ReportView';
import GenerateModal from './components/GenerateModal';
import SettingsModal from './components/SettingsModal';
import { Menu, BarChart3, Settings } from 'lucide-react';

export default function App() {
  const { loadReports, currentReport, loading } = useReportStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  useEffect(() => {
    loadReports();
  }, []);

  return (
    <div className="flex h-screen bg-[var(--color-surface-raised)] text-[var(--color-text-primary)] font-body">
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(v => !v)}
        onGenerate={() => setShowGenerateModal(true)}
      />

      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center gap-3 px-5 py-3 bg-white border-b border-[var(--color-border)] shadow-sm">
          <button
            onClick={() => setSidebarOpen(v => !v)}
            className="sm:hidden p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] cursor-pointer"
          >
            <Menu size={20} />
          </button>
          <BarChart3 size={20} className="text-[var(--color-accent)]" />
          <span className="text-sm font-semibold tracking-tight text-[var(--color-text-primary)]">
            Social Competitor Report
          </span>
          <button
            onClick={() => setShowSettingsModal(true)}
            className="ml-auto p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-raised)] rounded transition-colors cursor-pointer"
            title="Settings"
            aria-label="Settings"
          >
            <Settings size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-2">
                <div className="w-6 h-6 border-2 border-[var(--color-accent)] border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-[var(--color-text-muted)]">Loading report...</p>
              </div>
            </div>
          ) : currentReport ? (
            <ReportView report={currentReport} />
          ) : (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-2 text-center">
                <BarChart3 size={32} className="text-[var(--color-text-muted)]" />
                <p className="text-sm text-[var(--color-text-muted)]">Select a report from the sidebar</p>
              </div>
            </div>
          )}
        </div>
      </main>

      <GenerateModal isOpen={showGenerateModal} onClose={() => setShowGenerateModal(false)} />
      <SettingsModal isOpen={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
    </div>
  );
}
