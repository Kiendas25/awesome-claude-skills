import { useState } from 'react';
import { useStore, totalDuration } from '../lib/store';
import { exportTimeline } from '../lib/export';
import { transcodeToMp4, isCrossOriginIsolated } from '../lib/ffmpeg';
import { fmtTime, fmtBytes } from '../utils/format';

type Phase = 'idle' | 'rendering' | 'transcoding' | 'done' | 'error';

// Export flow: record the timeline (canvas + audio), then optionally convert
// the WebM to MP4 with FFmpeg.wasm.
export function ExportPanel() {
  const project = useStore((s) => s.project);
  const [phase, setPhase] = useState<Phase>('idle');
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<{ url: string; ext: string; size: number } | null>(null);
  const [error, setError] = useState('');
  const [log, setLog] = useState('');

  const clips = project?.clips ?? [];
  const total = totalDuration(clips);
  const canExport = clips.length > 0 && total > 0;

  async function run(convertMp4: boolean) {
    if (!project || !canExport) return;
    setPhase('rendering');
    setProgress(0);
    setError('');
    setResult(null);
    try {
      const out = await exportTimeline({
        clips: project.clips,
        overlays: project.overlays,
        music: project.music,
        width: project.export.width,
        height: project.export.height,
        fps: project.export.fps,
        onProgress: setProgress,
      });

      let blob = out.blob;
      let ext = out.ext;

      if (convertMp4 && ext !== 'mp4') {
        if (!isCrossOriginIsolated()) {
          throw new Error(
            'MP4 conversion needs cross-origin isolation. Use `npm run dev` / `npm run preview` (headers are set there), then retry.'
          );
        }
        setPhase('transcoding');
        setProgress(0);
        blob = await transcodeToMp4(out.blob, setProgress, (m) => setLog(m));
        ext = 'mp4';
      }

      const url = URL.createObjectURL(blob);
      setResult({ url, ext, size: blob.size });
      setPhase('done');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase('error');
    }
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

      {busy && (
        <div>
          <div className="mb-1 flex justify-between text-xs text-slate-400">
            <span>{phase === 'rendering' ? 'Recording timeline…' : 'Converting to MP4…'}</span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-panel2">
            <div
              className="h-full bg-gradient-to-r from-brand to-accent transition-all"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
          {phase === 'rendering' && (
            <p className="mt-1 text-[11px] text-slate-500">
              Recording plays the video through in real time — keep this tab focused.
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
            ✅ Export ready · {result.ext.toUpperCase()} · {fmtBytes(result.size)}
          </p>
          <video src={result.url} controls className="w-full rounded-lg" />
          <a
            href={result.url}
            download={`${(project?.name || 'viralcut').replace(/\s+/g, '_')}.${result.ext}`}
            className="btn-primary w-full text-sm"
          >
            ⬇ Download {result.ext.toUpperCase()}
          </a>
        </div>
      )}

      {phase === 'error' && (
        <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </p>
      )}

      {!busy && (
        <div className="grid grid-cols-1 gap-2">
          <button onClick={() => run(false)} disabled={!canExport} className="btn-primary w-full">
            ⚡ Export video (fast, WebM/MP4)
          </button>
          <button onClick={() => run(true)} disabled={!canExport} className="btn-ghost w-full text-sm">
            🎬 Export as MP4 (FFmpeg.wasm)
          </button>
          <p className="text-[11px] text-slate-500">
            Fast export uses your browser's recorder. MP4 export converts the result with
            FFmpeg.wasm (downloads ~30&nbsp;MB core on first use).
          </p>
        </div>
      )}
    </div>
  );
}
