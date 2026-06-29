import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, MinusCircle, AlertTriangle } from 'lucide-react';

const STATUS_ICON = {
  ok: <CheckCircle2 size={14} className="text-green-600" />,
  failed: <XCircle size={14} className="text-red-600" />,
  skipped: <MinusCircle size={14} className="text-gray-400" />,
  partial: <AlertTriangle size={14} className="text-yellow-600" />,
};

const fmtDuration = (s) => (s == null ? '—' : `${s.toFixed(1)}s`);

export default function GenerationLogPanel({ log }) {
  const [open, setOpen] = useState(false);
  if (!log || log.length === 0) return null;
  const failed = log.filter(s => s.status === 'failed');
  const headerCls = failed.length > 0 ? 'text-red-700' : 'text-gray-600';

  return (
    <section className="my-6 rounded border border-gray-200 bg-gray-50">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-2 w-full px-4 py-2 text-sm ${headerCls} hover:bg-gray-100`}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="font-medium">Generation report</span>
        <span className="ml-auto text-xs">
          {failed.length > 0
            ? `${failed.length} step${failed.length > 1 ? 's' : ''} failed`
            : `${log.length} steps OK`}
        </span>
      </button>
      {open && (
        <div className="px-4 py-2 border-t border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="py-1">Step</th>
                <th className="py-1">Status</th>
                <th className="py-1">Duration</th>
                <th className="py-1">Items</th>
              </tr>
            </thead>
            <tbody>
              {log.map((s, i) => (
                <tr key={i} className="border-t border-gray-100">
                  <td className="py-1">{s.name}</td>
                  <td className="py-1">
                    <span className="inline-flex items-center gap-1">
                      {STATUS_ICON[s.status] || null} {s.status}
                    </span>
                  </td>
                  <td className="py-1">{fmtDuration(s.duration_s)}</td>
                  <td className="py-1">{s.status === 'ok' ? s.items_count : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {failed.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-semibold text-red-700">Errors:</div>
              <ul className="text-xs text-red-700 list-disc list-inside">
                {failed.map((s, i) => (
                  <li key={i}><strong>{s.name}:</strong> {s.error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
