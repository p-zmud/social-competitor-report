import { useState, useEffect } from 'react';
import { X, Plus, Trash2, ArrowUp, ArrowDown } from 'lucide-react';
import { getSettings, saveSettings, getProfiles, saveProfiles, resetProfiles } from '../api';

const inputCls =
  'border border-[var(--color-border)] rounded px-2.5 py-1.5 w-full text-sm focus:outline-none focus:border-[var(--color-accent)]';

export default function SettingsModal({ isOpen, onClose }) {
  const [status, setStatus] = useState(null);
  const [model, setModel] = useState('');
  const [customModel, setCustomModel] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [orKey, setOrKey] = useState('');
  const [apify, setApify] = useState('');
  const [summaryPrompt, setSummaryPrompt] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [isOverride, setIsOverride] = useState(false);
  const [profilesErr, setProfilesErr] = useState('');
  const [profilesSaving, setProfilesSaving] = useState(false);
  const [profilesSaved, setProfilesSaved] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    getSettings()
      .then((s) => {
        setStatus(s);
        setSummaryPrompt(s.summary_prompt || '');
        if (s.models.includes(s.model)) {
          setModel(s.model);
          setUseCustom(false);
        } else {
          setUseCustom(true);
          setCustomModel(s.model);
          setModel(s.models[0] || '');
        }
      })
      .catch(() => {});
    getProfiles()
      .then((p) => {
        setProfiles(p.profiles || []);
        setIsOverride(p.is_override);
      })
      .catch(() => {});
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setSaving(true);
    const body = {};
    const chosen = useCustom ? customModel.trim() : model;
    if (chosen) body.model = chosen;
    if (orKey.trim()) body.openrouter_api_key = orKey.trim();
    if (apify.trim()) body.apify_token = apify.trim();
    body.summary_prompt = summaryPrompt;
    try {
      const s = await saveSettings(body);
      setStatus(s);
      setOrKey('');
      setApify('');
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      console.error('Failed to save settings:', e);
    } finally {
      setSaving(false);
    }
  };

  const EMPTY_PROFILE = { name: '', facebook_page: '', instagram_handle: '', tiktok_handle: '' };

  const updateProfile = (i, key, val) =>
    setProfiles((ps) => ps.map((p, j) => (j === i ? { ...p, [key]: val } : p)));
  const addProfile = () => setProfiles((ps) => [...ps, { ...EMPTY_PROFILE }]);
  const removeProfile = (i) => setProfiles((ps) => ps.filter((_, j) => j !== i));
  const moveProfile = (i, dir) =>
    setProfiles((ps) => {
      const j = i + dir;
      if (j < 0 || j >= ps.length) return ps;
      const next = [...ps];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });

  const handleSaveProfiles = async () => {
    setProfilesSaving(true);
    setProfilesErr('');
    try {
      const r = await saveProfiles(profiles);
      setProfiles(r.profiles);
      setIsOverride(true);
      setProfilesSaved(true);
      setTimeout(() => setProfilesSaved(false), 1500);
    } catch (e) {
      setProfilesErr(e.message);
    } finally {
      setProfilesSaving(false);
    }
  };

  const handleResetProfiles = async () => {
    setProfilesErr('');
    try {
      const r = await resetProfiles();
      setProfiles(r.profiles);
      setIsOverride(false);
    } catch (e) {
      setProfilesErr(e.message);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-start justify-center" onClick={onClose}>
      <div
        className="bg-white rounded-lg p-5 max-w-2xl w-full mx-4 mt-16 max-h-[85vh] overflow-y-auto border border-[var(--color-border)] shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold">Settings</h2>
          <button onClick={onClose} aria-label="Close" className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-4 text-sm">
          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">
              OpenRouter API key{' '}
              {status?.openrouter_api_key_set && (
                <span className="text-[var(--color-positive)]">• set ({status.openrouter_api_key_masked})</span>
              )}
            </label>
            <input
              type="password"
              value={orKey}
              onChange={(e) => setOrKey(e.target.value)}
              placeholder={status?.openrouter_api_key_set ? 'enter to replace' : 'sk-or-...'}
              className={inputCls}
            />
          </div>

          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">
              Apify token{' '}
              {status?.apify_token_set && (
                <span className="text-[var(--color-positive)]">• set ({status.apify_token_masked})</span>
              )}
            </label>
            <input
              type="password"
              value={apify}
              onChange={(e) => setApify(e.target.value)}
              placeholder={status?.apify_token_set ? 'enter to replace' : 'apify_api_...'}
              className={inputCls}
            />
          </div>

          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">Summary model (OpenRouter)</label>
            <select
              value={useCustom ? '__custom__' : model}
              onChange={(e) => {
                if (e.target.value === '__custom__') setUseCustom(true);
                else {
                  setUseCustom(false);
                  setModel(e.target.value);
                }
              }}
              className={inputCls}
            >
              {status?.models?.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
              <option value="__custom__">Custom…</option>
            </select>
            {useCustom && (
              <input
                type="text"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="provider/model-id"
                className={`${inputCls} mt-2`}
              />
            )}
          </div>

          <div>
            <label className="block text-xs text-[var(--color-text-muted)] mb-1">
              Summary prompt
            </label>
            <textarea
              value={summaryPrompt}
              onChange={(e) => setSummaryPrompt(e.target.value)}
              placeholder={status?.summary_prompt_default}
              rows={5}
              className={`${inputCls} resize-y`}
            />
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              Leave empty to use the default. The brand name and posts are added automatically.
            </p>
          </div>

          <div className="border-t border-[var(--color-border)] pt-4">
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-medium text-[var(--color-text-muted)]">
                Tracked profiles{' '}
                {isOverride
                  ? <span className="text-[var(--color-accent)]">• custom</span>
                  : <span>• config defaults</span>}
              </label>
              <button onClick={addProfile} className="flex items-center gap-1 text-xs text-[var(--color-accent)] cursor-pointer">
                <Plus size={12} /> Add profile
              </button>
            </div>

            <div className="space-y-2">
              {profiles.map((p, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <input value={p.name} onChange={(e) => updateProfile(i, 'name', e.target.value)}
                    placeholder="Brand name" className={`${inputCls} flex-[2] min-w-0`} />
                  <input value={p.facebook_page} onChange={(e) => updateProfile(i, 'facebook_page', e.target.value)}
                    placeholder="FB page" className={`${inputCls} flex-1 min-w-0`} />
                  <input value={p.instagram_handle} onChange={(e) => updateProfile(i, 'instagram_handle', e.target.value)}
                    placeholder="IG handle" className={`${inputCls} flex-1 min-w-0`} />
                  <input value={p.tiktok_handle} onChange={(e) => updateProfile(i, 'tiktok_handle', e.target.value)}
                    placeholder="TikTok handle" className={`${inputCls} flex-1 min-w-0`} />
                  <button onClick={() => moveProfile(i, -1)} aria-label="Move up" className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer"><ArrowUp size={14} /></button>
                  <button onClick={() => moveProfile(i, 1)} aria-label="Move down" className="text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer"><ArrowDown size={14} /></button>
                  <button onClick={() => removeProfile(i)} aria-label="Remove" className="text-[var(--color-text-muted)] hover:text-[var(--color-negative)] cursor-pointer"><Trash2 size={14} /></button>
                </div>
              ))}
            </div>

            {profilesErr && <p className="text-xs text-[var(--color-negative)] mt-2">{profilesErr}</p>}

            <div className="flex items-center gap-3 mt-3">
              <button onClick={handleSaveProfiles} disabled={profilesSaving}
                className="bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:opacity-40 text-white text-sm font-medium px-4 py-1.5 rounded cursor-pointer">
                {profilesSaved ? '✓ Saved' : profilesSaving ? 'Saving…' : 'Save profiles'}
              </button>
              <button onClick={handleResetProfiles}
                className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] underline cursor-pointer">
                Reset to config defaults
              </button>
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:opacity-40 text-white text-sm font-medium px-4 py-2 rounded w-full cursor-pointer"
          >
            {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save'}
          </button>

          <p className="text-xs text-[var(--color-text-muted)]">
            Keys are stored locally in <code>data/settings.json</code> and never leave your machine.
          </p>
        </div>
      </div>
    </div>
  );
}
