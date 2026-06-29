import { create } from 'zustand';
import { fetchReports, fetchReport, fetchFollowersSummary, fetchGenerationLog } from '../api';

let _selectAbort = null;

export const useReportStore = create((set) => ({
  reports: [],
  currentReport: null,
  currentReportId: null,
  followersSummary: [],
  generationLog: null,
  loading: false,
  generating: false,
  generateProgress: null,
  error: null,

  loadReports: async () => {
    try {
      const reports = await fetchReports();
      set({ reports, error: null });
      // Auto-select the most recent report (by end date extracted from report_id)
      const endDate = (id) => {
        const m = id.match(/(\d{4}-\d{2}-\d{2})$/);
        return m ? m[1] : '0000-00-00';
      };
      const sorted = [...reports].sort((a, b) => endDate(b.report_id).localeCompare(endDate(a.report_id)));
      const best = sorted.find(r => r.has_data) || sorted[0];
      if (best && !useReportStore.getState().currentReportId) {
        useReportStore.getState().selectReport(best.report_id);
      }
    } catch (e) {
      set({ error: String(e) });
    }
  },

  selectReport: async (reportId) => {
    if (_selectAbort) _selectAbort.abort();
    _selectAbort = new AbortController();
    const signal = _selectAbort.signal;
    set({ loading: true, currentReportId: reportId, generationLog: null });
    try {
      const [report, followers, log] = await Promise.all([
        fetchReport(reportId, signal),
        fetchFollowersSummary(reportId, signal).catch((e) => {
          if (e.name === 'AbortError') throw e;
          return [];
        }),
        fetchGenerationLog(reportId, signal).catch((e) => {
          if (e.name === 'AbortError') throw e;
          return null;
        }),
      ]);
      if (signal.aborted) return;
      set({ currentReport: report, followersSummary: followers, generationLog: log, loading: false, error: null });
    } catch (e) {
      if (e.name === 'AbortError') return;
      set({ currentReport: null, followersSummary: [], generationLog: null, loading: false, error: String(e) });
    }
  },

  setGenerating: (val) => set({ generating: val }),
  setGenerateProgress: (p) => set({ generateProgress: p }),
}));
