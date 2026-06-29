import { useState, useCallback } from 'react';
import { exportHtml, exportMarkdown } from '../api';

export default function ExportButtons({ reportId }) {
  const [htmlCopied, setHtmlCopied] = useState(false);
  const [mdCopied, setMdCopied] = useState(false);

  const handleCopyHtml = useCallback(async () => {
    try {
      const html = await exportHtml(reportId);
      const blob = new Blob([html], { type: 'text/html' });
      const plainBlob = new Blob([html], { type: 'text/plain' });
      let item;
      try {
        item = new ClipboardItem({ 'text/html': blob, 'text/plain': plainBlob });
      } catch {
        // Older Safari requires Promise-wrapped blobs
        item = new ClipboardItem({
          'text/html': Promise.resolve(blob),
          'text/plain': Promise.resolve(plainBlob),
        });
      }
      await navigator.clipboard.write([item]);
      setHtmlCopied(true);
      setTimeout(() => setHtmlCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy HTML:', err);
      // Fallback: copy markdown as plain text so user gets *something* on the clipboard
      try {
        const md = await exportMarkdown(reportId);
        await navigator.clipboard.writeText(md);
        setMdCopied(true);
        setTimeout(() => setMdCopied(false), 2000);
      } catch (err2) {
        console.error('Markdown fallback also failed:', err2);
      }
    }
  }, [reportId]);

  const handleCopyMarkdown = useCallback(async () => {
    try {
      const md = await exportMarkdown(reportId);
      await navigator.clipboard.writeText(md);
      setMdCopied(true);
      setTimeout(() => setMdCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy Markdown:', err);
    }
  }, [reportId]);

  return (
    <span className="text-xs text-[var(--color-text-muted)] no-print">
      <button onClick={handleCopyHtml} className="hover:text-[var(--color-accent)] cursor-pointer">
        {htmlCopied ? '✓ copied' : 'copy HTML'}
      </button>
      {' · '}
      <button onClick={handleCopyMarkdown} className="hover:text-[var(--color-accent)] cursor-pointer">
        {mdCopied ? '✓ copied' : 'copy Markdown'}
      </button>
    </span>
  );
}
