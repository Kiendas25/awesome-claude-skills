import { useRef, useState } from 'react';
import { useStore } from '../lib/store';
import { AppHeader } from '../components/AppHeader';
import { loadProjectMetas, deleteProjectMeta } from '../lib/storage';
import { isSupported as opfsSupported } from '../lib/opfs';

export function Home() {
  const createProject = useStore((s) => s.createProject);
  const addClipFromFile = useStore((s) => s.addClipFromFile);
  const restoreProject = useStore((s) => s.restoreProject);
  const setScreen = useStore((s) => s.setScreen);
  const fileRef = useRef<HTMLInputElement>(null);
  const [metas, setMetas] = useState(() => loadProjectMetas());
  const [restoring, setRestoring] = useState<string | null>(null);
  const [notice, setNotice] = useState('');

  async function onUpload(file: File) {
    createProject(file.name.replace(/\.[^.]+$/, ''));
    await addClipFromFile(file);
    setScreen('editor');
  }

  async function onRestore(metaId: string) {
    const meta = metas.find((m) => m.id === metaId);
    if (!meta) return;
    setRestoring(metaId);
    const missing = await restoreProject(meta);
    setRestoring(null);
    if (missing.length) {
      setNotice(
        `Restored "${meta.name}". ${missing.length} clip(s) couldn't be recovered from storage and need re-uploading: ${missing.join(', ')}.`
      );
    }
  }

  const opfs = opfsSupported();

  return (
    <div className="pb-24">
      <AppHeader title="ViralCut AI" subtitle="Local-first short-form editor" />

      <div className="mx-auto max-w-md space-y-5 px-4 pt-5">
        <section className="card bg-gradient-to-br from-brand/20 to-accent/10">
          <p className="text-sm text-slate-300">
            Make TikToks, Shorts &amp; Reels right in your browser. No login, no cloud, no paid
            APIs — your videos never leave your device.
          </p>
          <p className={`mt-2 text-xs ${opfs ? 'text-emerald-400' : 'text-amber-400'}`}>
            {opfs
              ? '✅ Media auto-saves via OPFS — clips survive page reloads.'
              : '⚠️ Your browser doesn\'t support OPFS. Clips will need re-uploading after reload.'}
          </p>
        </section>

        {notice && (
          <div className="card border-amber-500/40 bg-amber-500/10 text-sm text-amber-200">
            {notice}
            <button onClick={() => setNotice('')} className="ml-2 text-xs underline">dismiss</button>
          </div>
        )}

        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = '';
          }}
        />

        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => createProject()} className="btn-primary h-24 flex-col text-base">
            <span className="text-2xl">＋</span>
            New Project
          </button>
          <button onClick={() => fileRef.current?.click()} className="btn-ghost h-24 flex-col text-base">
            <span className="text-2xl">⬆️</span>
            Upload Video
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => setScreen('templates')} className="btn-ghost h-16 flex-col text-sm">
            🧩 Templates
          </button>
          <button onClick={() => setScreen('assistant')} className="btn-ghost h-16 flex-col text-sm">
            ✨ AI Assistant
          </button>
        </div>

        <section>
          <h2 className="label">Saved projects</h2>
          {metas.length === 0 ? (
            <div className="card text-sm text-slate-400">
              No saved projects yet. Create one to get started.
            </div>
          ) : (
            <ul className="space-y-2">
              {metas.map((m) => (
                <li key={m.id} className="card flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{m.name}</p>
                    <p className="text-xs text-slate-500">
                      {m.clips.length} clip{m.clips.length === 1 ? '' : 's'} ·{' '}
                      {m.overlays.length} overlay{m.overlays.length === 1 ? '' : 's'} ·{' '}
                      {new Date(m.updatedAt).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      onClick={() => onRestore(m.id)}
                      disabled={restoring === m.id}
                      className="chip border-brand text-brand-glow disabled:opacity-50"
                    >
                      {restoring === m.id ? '…' : 'Open'}
                    </button>
                    <button
                      onClick={async () => {
                        if (confirm('Delete this project and its saved media?')) {
                          await deleteProjectMeta(m.id);
                          setMetas(loadProjectMetas());
                        }
                      }}
                      className="text-red-400"
                      aria-label="Delete project"
                    >
                      🗑
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {!opfs && (
            <p className="mt-2 text-[11px] text-slate-600">
              Projects restore settings &amp; text, but video files must be re-uploaded (OPFS not
              available in this browser). Chrome / Edge support automatic media persistence.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
