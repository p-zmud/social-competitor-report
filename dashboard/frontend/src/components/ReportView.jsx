import { useReportStore } from '../store/useReportStore';
import CompetitorSection from './CompetitorSection';
import FollowersSummary from './FollowersSummary';
import ExportButtons from './ExportButtons';
import GenerationLogPanel from './GenerationLogPanel';

export default function ReportView({ report }) {
  const followersSummary = useReportStore((s) => s.followersSummary);
  const generationLog = useReportStore((s) => s.generationLog);

  if (!report) return null;

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <article className="bg-white rounded-xl shadow-sm border border-[var(--color-border-subtle)] px-8 py-8">
        {/* Title */}
        <div className="mb-8">
          <h1 className="text-xl font-bold mb-1 text-[var(--color-text-primary)]">
            {report.report_title || 'Weekly Social Report'}
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-[var(--color-text-secondary)]">{report.week_label}</span>
            <span className="text-xs font-mono text-[var(--color-text-muted)]">{report.report_id}</span>
            <ExportButtons reportId={report.report_id} />
          </div>
        </div>

        {/* Followers Summary Table (cross-brand overview) */}
        <FollowersSummary data={followersSummary} />

        <hr className="my-8 border-[var(--color-border-subtle)]" />

        {/* Per-brand competitor cards */}
        <CompetitorSection competitors={report.competitors} />

        {/* Generation log */}
        <GenerationLogPanel log={generationLog} />
      </article>
    </div>
  );
}
