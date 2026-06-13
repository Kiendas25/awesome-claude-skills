import { useEffect, useState } from 'react';
import { useStore, totalDuration } from '../lib/store';
import { exportTimeline } from '../lib/export';
import { transcodeToMp4, isCrossOriginIsolated } from '../lib/ffmpeg';
import { fmtTime, fmtBytes } from '../utils/format';

type Phase = 'idle' | 'rendering' | 'transcoding' | 'done' | 'error';

export function ExportPanel() {
  const project = useStore((s) => s.project);
  const [phase, setPhase] = useState<Phase>('idle');
  const [progress, setProgress] = useState(0);
  const [eta, setEta] = useState('');
  const [result, setResult] = useState<{ url: string; ext: string; size: number; draft: boolean } | null>(null);
  const [error, setError] = useState('');
  const [log, setLog] = useState('');
  const [tabHidden, setTabHidden] = useState(false);

  const clips = project?.clips ?? [];
  const total = totalDuration(clips);
  const canExport = clips.length > 0 && total > 0 && clips.every((c) => c.url);

  // Warn when the user backgrounds the tab during export.
  useEffect(() => {
    const handler = () => setTabHidden(document.hidden);
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, []);

  // ETA: estimated seconds remaining based on progress and elapsed.
  const startTimeRef = { current: 0 };

  async function run(draft: boolean, convertMp4 = false) {
    if (!project || !canExport) return;
    setPhase('rendering');
    setProgress(0);
    setEta('');
    setError('');
    setResult(null);
    startTimeRef.current = Date.now();

    try {
      const out = await exportTimeline({
        clips: project.clips,
        overlays: project.overlays,
        music: project.music,
        width: project.export.width,
        height: project.export.height,
        fps: project.export.fps,
        draft,
        onProgress: (r) => {
          setProgress(r);
          if (r > 0.02) {
            const elapsed = (Date.now() - startTimeRef.current) / 1000;
            const remaining = (elapsed / r) * (1 - r);
            setEta(remaining > 2 ? `~${Math.ceil(remaining)}s left` : '');
          }
        },
      });

      let blob = out.blob;
      let ext = out.ext;

      if (convertMp4 && ext !== 'mp4') {
        if (!isCrossOriginIsolated()) {
          throw new Error(
            'FFmpeg MP4 conversion needs Cross-Origin Isolation + internet (first load). On iPhone, your Full/Draft export is already MP4, so just use those — no conversion needed.'
          );
        }
        if (!navigator.onLine) {
          throw new Error(
            'FFmpeg core downloads on first use and you appear to be offline. Use Full/Draft export instead (already MP4 on iOS).'
          );
        }
        setPhase('transcoding');
        setProgress(0);
        blob = await transcodeToMp4(out.blob, setProgress, (m) => setLog(m));
        ext = 'mp4';
      }

      const url = URL.createObjectURL(blob);
      setResult({ url, ext, size: blob.size, draft: out.draft });
      setPhase('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase('error');
    }
    setEta('');
  }

  const busy = phase === 'rendering' || phase === 'transcoding';

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <span className="label mb-0">Export</span>
        <span className="font-mono text-xs text-slate-500">
          {project?.export.width}×{project?.export.height} · {fmtTime(total)}
        </span>
      </div>

      {busy && tabHidden && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-2 text-sm text-amber-300">
          ⚠️ Tab is hidden — export may slow or pause. Switch back to this tab.
        </div>
      )}

      {busy && (
        <div>
          <div className="mb-1 flex justify-between text-xs text-slate-400">
            <span>{phase === 'rendering' ? 'Recording timeline…' : 'Converting to MP4…'}</span>
            <span>{eta || `${Math.round(progress * 100)}%`}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-panel2">
            <div
              className="h-full bg-gradient-to-r from-brand to-accent transition-all"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
          {phase === 'rendering' && (
            <p className="mt-1 text-[11px] text-slate-500">
              Recording plays through in real time. Draft mode is ~4× faster at half resolution.
            </p>
          )}
          {log && phase === 'transcoding' && (
            <p className="mt-1 truncate font-mono text-[10px] text-slate-600">{log}</p>
          )}
        </div>
      )}

      {phase === 'done' && result && (
        <div className="space-y-2 rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3">
          <p className="text-sm text-emerald-300">
            ✅ {result.draft ? '(Draft) ' : ''}Export ready · {result.ext.toUpperCase()} ·{' '}
            {fmtBytes(result.size)}
          </p>
          <video src={result.url} controls className="w-full rounded-lg" />
          <a
            href={result.url}
            download={`${(project?.name || 'viralcut').replace(/\s+/g, '_')}${result.draft ? '_draft' : ''}.${result.ext}`}
            className="btn-primary block w-full text-center text-sm"
          >
            ⬇ Download {result.ext.toUpperCase()}
          </a>
          {result.draft && (
            <p className="text-xs text-slate-400">
              This is a draft preview at 540×960. Export at full quality when ready.
            </p>
          )}
        </div>
      )}

      {phase === 'error' && (
        <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </p>
      )}

      {!busy && (
        <div className="space-y-2">
          <button onClick={() => run(false)} disabled={!canExport} className="btn-primary w-full">
            ⚡ Full export — {project?.export.width}×{project?.export.height}
          </button>
          <button onClick={() => run(true)} disabled={!canExport} className="btn-ghost w-full text-sm">
            🚀 Draft export — 540×960 (~4× faster)
          </button>
          <button
            onClick={() => run(false, true)}
            disabled={!canExport}
            className="btn-ghost w-full text-sm"
          >
            🎬 Full export → MP4 via FFmpeg.wasm
          </button>
          {!canExport && clips.some((c) => !c.url) && (
            <p className="text-xs text-amber-400">
              Some clips are missing media. Re-upload them or restore the project.
            </p>
          )}
          <p className="text-[11px] text-slate-500">
            Full export = real-time recording. Draft is 4× faster. FFmpeg MP4 requires
            cross-origin-isolation headers (set automatically by Vite dev/preview).
          </p>
        </div>
      )}
    </div>
  );
}
