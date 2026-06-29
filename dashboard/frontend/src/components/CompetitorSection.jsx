function fmtNum(n) {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (abs >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return n.toLocaleString();
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '—';
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function formatDelta(d) {
  if (d == null) return '';
  return (d > 0 ? '+' : '') + fmtNum(d);
}

function deltaStyle(d) {
  if (d > 0) return { color: 'var(--color-positive)' };
  if (d < 0) return { color: 'var(--color-negative)' };
  return { color: 'var(--color-text-muted)' };
}

const platforms = ['facebook', 'instagram', 'tiktok'];
const platformLabel = { facebook: 'Facebook', instagram: 'Instagram', tiktok: 'TikTok' };

function PostsTable({ posts }) {
  if (!posts || posts.length === 0) {
    return <p className="text-xs text-[var(--color-text-muted)] italic mt-2">No posts published in this period.</p>;
  }
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold text-[var(--color-text-muted)] mb-1">
        All posts this period ({posts.length})
      </p>
      <div className="overflow-x-auto max-h-96 overflow-y-auto border border-[var(--color-border-subtle)] rounded">
        <table className="text-xs w-full">
          <thead className="sticky top-0 bg-[var(--color-surface-raised)]">
            <tr className="text-[var(--color-text-muted)] text-left">
              <th className="px-2 py-1 font-medium">Platform</th>
              <th className="px-2 py-1 font-medium">Date</th>
              <th className="px-2 py-1 font-medium">Description</th>
              <th className="px-2 py-1 font-medium text-right">Likes</th>
              <th className="px-2 py-1 font-medium text-right">Comments</th>
              <th className="px-2 py-1 font-medium text-right">Shares</th>
              <th className="px-2 py-1 font-medium text-right">Views</th>
              <th className="px-2 py-1 font-medium">Link</th>
            </tr>
          </thead>
          <tbody>
            {posts.map((p, j) => (
              <tr key={j} className="border-t border-[var(--color-border-subtle)] align-top">
                <td className="px-2 py-1 whitespace-nowrap">{platformLabel[p.platform] || p.platform}</td>
                <td className="px-2 py-1 whitespace-nowrap tabular-nums">{fmtDate(p.published_at)}</td>
                <td className="px-2 py-1 max-w-[18rem] truncate" title={p.caption}>{p.caption || '—'}</td>
                <td className="px-2 py-1 text-right tabular-nums">{fmtNum(p.likes)}</td>
                <td className="px-2 py-1 text-right tabular-nums">{fmtNum(p.comments)}</td>
                <td className="px-2 py-1 text-right tabular-nums">{fmtNum(p.shares)}</td>
                <td className="px-2 py-1 text-right tabular-nums">{p.views ? fmtNum(p.views) : '—'}</td>
                <td className="px-2 py-1">
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noopener noreferrer">link</a>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function CompetitorSection({ competitors }) {
  if (!competitors || competitors.length === 0) return null;

  return (
    <section>
      <h2 className="text-base font-bold mb-4">Competitors</h2>
      <div className="space-y-8">
        {competitors.map((comp, i) => (
          <div key={i} className="text-sm">
            <h3 className="text-base font-bold mb-1">{comp.name}</h3>

            {comp.content_summary && (
              <p className="text-[var(--color-text-secondary)] mb-2">{comp.content_summary}</p>
            )}

            {comp.best_post && (
              <div className="mb-2">
                <p className="text-[var(--color-text-secondary)]">
                  Best post ({comp.best_post.platform}):
                  {comp.best_post.caption && (
                    <> "{comp.best_post.caption.length > 80 ? comp.best_post.caption.slice(0, 80) + '...' : comp.best_post.caption}"</>
                  )}
                  {comp.best_post.views != null && comp.best_post.views > 0 && (
                    <> — Views: {comp.best_post.views.toLocaleString()}</>
                  )}
                  {comp.best_post.url && (
                    <> · <a href={comp.best_post.url} target="_blank" rel="noopener noreferrer">Link</a></>
                  )}
                </p>
                {comp.best_post.image_url && (
                  <div className="mt-2">
                    <img
                      src={comp.best_post.image_url}
                      alt=""
                      style={{ maxWidth: '300px', height: 'auto' }}
                      className="rounded border border-[var(--color-border)]"
                      loading="lazy"
                    />
                  </div>
                )}
              </div>
            )}

            <PostsTable posts={comp.posts} />

            {comp.followers && (() => {
              const rows = platforms.filter(p => comp.followers[p]);
              if (rows.length === 0) return null;
              return (
                <table className="text-sm mt-3 mb-1">
                  <thead>
                    <tr className="text-[var(--color-text-muted)]">
                      <th className="text-left pr-4 font-medium py-0.5">Platform</th>
                      <th className="text-right pr-4 font-medium py-0.5">Followers</th>
                      <th className="text-right pr-4 font-medium py-0.5">Previous</th>
                      <th className="text-right font-medium py-0.5">Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(p => {
                      const d = comp.followers[p];
                      return (
                        <tr key={p}>
                          <td className="pr-4 py-0.5">{platformLabel[p]}</td>
                          <td className="text-right pr-4 py-0.5 tabular-nums">{fmtNum(d.current)}</td>
                          <td className="text-right pr-4 py-0.5 tabular-nums text-[var(--color-text-muted)]">{fmtNum(d.previous)}</td>
                          <td className="text-right py-0.5 tabular-nums font-medium" style={deltaStyle(d.delta)}>
                            {formatDelta(d.delta)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              );
            })()}

            {i < competitors.length - 1 && <hr className="mt-6 border-[var(--color-border-subtle)]" />}
          </div>
        ))}
      </div>
    </section>
  );
}
