import { useState, useRef, useEffect } from 'react';
import { generateReport, connectGenerateWS } from '../api';
import { useReportStore } from '../store/useReportStore';
import { X } from 'lucide-react';

const presets = [
  { label: '7 days', value: '7' },
  { label: '14 days', value: '14' },
  { label: '30 days', value: '30' },
];

export default function GenerateModal({ isOpen, onClose }) {
  const { loadReports, selectReport } = useReportStore();
  const [mode, setMode] = useState('preset');
  const [preset, setPreset] = useState('7');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [noLlm, setNoLlm] = useState(false);
  const [skipApify, setSkipApify] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(null);
  const wsRef = useRef(null);

  const closeWs = () => {
    if (wsRef.current) {
      try { wsRef.current.close(); } catch { /* noop */ }
      wsRef.current = null;
    }
  };

  useEffect(() => () => closeWs(), []);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    let sd, ed;
    if (mode === 'preset') {
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      const start = new Date(yesterday);
      start.setDate(start.getDate() - parseInt(preset) + 1);
      const fmt = (d) => d.toISOString().split('T')[0];
      sd = fmt(start);
      ed = fmt(yesterday);
    } else {
      sd = startDate;
      ed = endDate;
    }

    setGenerating(true);
    setProgress({ steps: [], current: null, detail: null, finished: false, error: null, result: null });

    await generateReport({ startDate: sd, endDate: ed, noLlm, skipApify });

    closeWs();
    wsRef.current = connectGenerateWS((snap) => {
      setProgress({
        steps: snap.steps_done || [],
        current: snap.current_step,
        detail: snap.current_detail,
        finished: snap.finished,
        error: snap.error,
        result: snap.result,
      });
      if (snap.finished || snap.error) {
        closeWs();
        if (snap.finished && snap.result) {
          loadReports();
          selectReport(snap.result.report_id);
        }
      }
    });
  };

  const handleClose = () => {
    // Always dismiss the dialog and stop watching. The backend run is a daemon
    // thread with no cancel hook, so closing can't abort it — it finishes in the
    // background and the report still appears in the list when done.
    closeWs();
    setGenerating(false);
    setProgress(null);
    setMode('preset');
    setPreset('7');
    setStartDate('');
    setEndDate('');
    setNoLlm(false);
    setSkipApify(false);
    onClose();
  };

  const canGenerate = mode === 'preset' || (startDate && endDate);
  const showForm = !generating;
  const showProgress = generating && progress;

  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-start justify-center" onClick={handleClose}>
      <div
        className="bg-white rounded-lg p-5 max-w-sm w-full mx-4 mt-24 border border-[var(--color-border)] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold">Generate Report</h2>
          <button
            onClick={handleClose}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {showForm && (
          <div className="space-y-3">
            <div className="flex gap-2 text-xs">
              {['preset', 'custom'].map(m => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`px-2.5 py-1 rounded cursor-pointer ${
                    mode === m ? 'bg-[var(--color-accent)] text-white' : 'text-[var(--color-text-secondary)] hover:bg-gray-100'
                  }`}
                >
                  {m === 'preset' ? 'Quick' : 'Custom'}
                </button>
              ))}
            </div>

            {mode === 'preset' && (
              <div className="flex gap-2">
                {presets.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => setPreset(p.value)}
                    className={`px-3 py-1.5 rounded text-xs cursor-pointer ${
                      preset === p.value
                        ? 'bg-[var(--color-accent)] text-white'
                        : 'bg-gray-100 text-[var(--color-text-secondary)] hover:bg-gray-200'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            )}

            {mode === 'custom' && (
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">From</label>
                  <input
                    type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                    className="border border-[var(--color-border)] rounded px-2.5 py-1.5 text-sm w-full focus:outline-none focus:border-[var(--color-accent)]"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-xs text-[var(--color-text-muted)] mb-1">To</label>
                  <input
                    type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                    className="border border-[var(--color-border)] rounded px-2.5 py-1.5 text-sm w-full focus:outline-none focus:border-[var(--color-accent)]"
                  />
                </div>
              </div>
            )}

            <div className="flex gap-4 text-xs text-[var(--color-text-secondary)]">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" checked={noLlm} onChange={(e) => setNoLlm(e.target.checked)} /> No LLM
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" checked={skipApify} onChange={(e) => setSkipApify(e.target.checked)} /> No Apify
              </label>
            </div>

            <button
              onClick={handleGenerate}
              disabled={!canGenerate}
              className="bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:opacity-40 text-white text-sm font-medium px-4 py-2 rounded w-full cursor-pointer"
            >
              Generate
            </button>
          </div>
        )}

        {showProgress && (
          <div className="space-y-1.5 text-xs">
            {progress.steps.map((step, i) => (
              <div key={i} className="text-[var(--color-positive)]">✓ {step.name}</div>
            ))}
            {progress.current && !progress.finished && !progress.error && (
              <div className="text-[var(--color-text-secondary)]">
                ⏳ {progress.current}
                {progress.detail && <span className="text-[var(--color-text-muted)]"> — {progress.detail}</span>}
              </div>
            )}
            {progress.error && (
              <div className="text-[var(--color-negative)]">✗ {progress.error}</div>
            )}
            {progress.finished && !progress.error && (
              <div className="text-[var(--color-positive)] font-medium">Done.</div>
            )}
            {(progress.finished || progress.error) && (
              <button onClick={handleClose} className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] mt-1 cursor-pointer">
                Close
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
