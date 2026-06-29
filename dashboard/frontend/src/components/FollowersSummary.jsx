function fmtNum(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return n.toLocaleString('en-US');
}

function fmtDelta(d) {
  if (d == null) return null;
  const sign = d > 0 ? '+' : d < 0 ? '−' : '±';
  const abs = Math.abs(d);
  let body;
  if (abs >= 1_000_000) body = (abs / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  else if (abs >= 1_000) body = (abs / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  else body = abs.toLocaleString('en-US');
  return `${sign}${body}`;
}

function deltaColor(d) {
  if (d == null || d === 0) return 'var(--color-text-muted)';
  return d > 0 ? 'var(--color-positive)' : 'var(--color-negative)';
}

function Cell({ value, delta }) {
  return (
    <div className="flex items-baseline justify-end gap-1.5">
      <span className="tabular-nums">{fmtNum(value)}</span>
      {delta != null && (
        <span className="text-xs tabular-nums" style={{ color: deltaColor(delta) }}>
          {fmtDelta(delta)}
        </span>
      )}
    </div>
  );
}

export default function FollowersSummary({ data }) {
  if (!data || data.length === 0) return null;

  return (
    <section>
      <h2 className="text-base font-bold mb-3">Followers Summary</h2>
      <table className="text-sm w-full max-w-xl">
        <thead>
          <tr className="text-[var(--color-text-muted)] text-xs">
            <th className="text-left pr-4 py-1.5 font-medium">Brand</th>
            <th className="text-right pr-4 py-1.5 font-medium">Facebook</th>
            <th className="text-right pr-4 py-1.5 font-medium">Instagram</th>
            <th className="text-right py-1.5 font-medium">TikTok</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-t border-[var(--color-border-subtle)]">
              <td className="pr-4 py-1.5">{row.name}</td>
              <td className="pr-4 py-1.5"><Cell value={row.facebook} delta={row.facebook_delta} /></td>
              <td className="pr-4 py-1.5"><Cell value={row.instagram} delta={row.instagram_delta} /></td>
              <td className="py-1.5"><Cell value={row.tiktok} delta={row.tiktok_delta} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
