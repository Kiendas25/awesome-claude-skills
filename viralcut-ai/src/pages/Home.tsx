import { useRef, useState } from 'react';
import { useStore } from '../lib/store';
import { AppHeader } from '../components/AppHeader';
import { loadProjectMetas, deleteProjectMeta } from '../lib/storage';

export function Home() {
  const createProject = useStore((s) => s.createProject);
  const addClipFromFile = useStore((s) => s.addClipFromFile);
  const setScreen = useStore((s) => s.setScreen);
  const fileRef = useRef<HTMLInputElement>(null);
  const [metas, setMetas] = useState(() => loadProjectMetas());

  async function onUpload(file: File) {
    createProject(file.name.replace(/\.[^.]+$/, ''));
    // createProject sets project synchronously in the store; add the clip next tick.
    await addClipFromFile(file);
    setScreen('editor');
  }

  return (
    <div className="pb-24">
      <AppHeader title="ViralCut AI" subtitle="Local-first short-form editor" />

      <div className="mx-auto max-w-md space-y-5 px-4 pt-5">
        <section className="card bg-gradient-to-br from-brand/20 to-accent/10">
          <p className="text-sm text-slate-300">
            Make TikToks, Shorts &amp; Reels right in your browser. No login, no cloud, no paid APIs —
            your videos never leave your device.
          </p>
        </section>

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
          <h2 className="label">Recent projects</h2>
          {metas.length === 0 ? (
            <div className="card text-sm text-slate-400">
              No saved projects yet. Create one to get started.
            </div>
          ) : (
            <ul className="space-y-2">
              {metas.map((m) => (
                <li key={m.id} className="card flex items-center justify-between py-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{m.name}</p>
                    <p className="text-xs text-slate-500">
                      {m.clipCount} clip{m.clipCount === 1 ? '' : 's'} · {m.overlays.length} overlay
                      {m.overlays.length === 1 ? '' : 's'} ·{' '}
                      {new Date(m.updatedAt).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      deleteProjectMeta(m.id);
                      setMetas(loadProjectMetas());
                    }}
                    className="ml-3 shrink-0 text-red-400"
                    aria-label="Delete project"
                  >
                    🗑
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-[11px] text-slate-600">
            Note: saved projects keep settings &amp; text, but video files must be re-uploaded after a
            reload (browsers can't persist large media locally). See README for details.
          </p>
        </section>
      </div>
    </div>
  );
}
