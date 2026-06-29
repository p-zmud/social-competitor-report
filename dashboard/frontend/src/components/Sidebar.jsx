import { useReportStore } from '../store/useReportStore';
import { Plus, X, Calendar, AlertTriangle } from 'lucide-react';

export default function Sidebar({ open, onToggle, onGenerate }) {
  const { reports, currentReportId, selectReport } = useReportStore();

  return (
    <>
      {open && (
        <div className="fixed inset-0 bg-black/30 z-30 sm:hidden" onClick={onToggle} />
      )}

      <aside
        className={`
          fixed top-0 left-0 z-40 h-full w-60 bg-white flex flex-col
          border-r border-[var(--color-border)]
          transition-transform duration-200
          sm:relative sm:translate-x-0 sm:z-auto
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Reports</span>
          <div className="flex items-center gap-1">
            <button
              onClick={onGenerate}
              className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-raised)] transition-colors rounded cursor-pointer"
              title="Generate Report"
              aria-label="Generate report"
            >
              <Plus size={16} />
            </button>
            <button onClick={onToggle} className="sm:hidden p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer">
              <X size={16} />
            </button>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-2 px-2">
          {reports.length === 0 && (
            <p className="px-3 py-6 text-xs text-[var(--color-text-muted)] text-center">No reports yet</p>
          )}
          {reports.map((r) => {
            const isActive = currentReportId === r.report_id;
            return (
              <button
                key={r.report_id}
                onClick={() => selectReport(r.report_id)}
                className={`
                  w-full text-left px-3 py-2.5 text-sm rounded-lg cursor-pointer
                  transition-all duration-150 flex items-center gap-2.5 mb-0.5
                  ${isActive
                    ? 'bg-[var(--color-accent)] text-white font-medium shadow-sm'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-raised)]'}
                `}
              >
                <Calendar size={14} className={isActive ? 'text-white/80' : 'text-[var(--color-text-muted)]'} />
                <span className="flex-1">{r.week_label || r.report_id}</span>
                {r.has_failures && (
                  <AlertTriangle size={12} className={isActive ? 'text-white/90' : 'text-red-600'} />
                )}
              </button>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
