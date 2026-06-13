import { useStore } from '../lib/store';
import { AppHeader } from '../components/AppHeader';
import { TEMPLATES } from '../templates';
import type { Template } from '../types';

export function Templates() {
  const project = useStore((s) => s.project);
  const createProject = useStore((s) => s.createProject);
  const applyTemplate = useStore((s) => s.applyTemplate);
  const setScreen = useStore((s) => s.setScreen);

  function use(t: Template) {
    if (!project) createProject(t.name);
    applyTemplate(t);
    setScreen('editor');
  }

  return (
    <div className="pb-24">
      <AppHeader title="Template Library" subtitle="Free, original 9:16 recipes" />
      <div className="mx-auto max-w-md space-y-3 px-4 pt-4">
        {!project && (
          <p className="card text-sm text-slate-400">
            Picking a template starts a new project with its text, pacing and export settings
            pre-filled.
          </p>
        )}
        {TEMPLATES.map((t) => (
          <div key={t.id} className="card">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="flex items-center gap-2 font-bold">
                  <span className="text-xl">{t.emoji}</span>
                  {t.name}
                </h3>
                <p className="mt-1 text-sm text-slate-400">{t.description}</p>
              </div>
              <button onClick={() => use(t)} className="btn-primary shrink-0 px-4 py-2 text-sm">
                Use
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="chip">{t.aspectRatio}</span>
              <span className="chip">~{t.suggestedClipSeconds}s / clip</span>
              <span className="chip">{t.suggestedCuts} cuts</span>
              <span className="chip">🎵 {t.musicMood}</span>
              <span className="chip">
                {t.export.width}×{t.export.height}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
