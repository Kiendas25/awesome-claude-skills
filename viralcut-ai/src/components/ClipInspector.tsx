import { useStore } from '../lib/store';
import { fmtTime, clamp } from '../utils/format';
import type { TransitionType } from '../types';

const TRANSITIONS: { id: TransitionType; label: string; desc: string }[] = [
  { id: 'cut', label: '✂️ Cut', desc: 'Instant switch (default)' },
  { id: 'fade', label: '🌑 Fade', desc: 'Fade to black then in' },
];

export function ClipInspector() {
  const project = useStore((s) => s.project);
  const selectedClipId = useStore((s) => s.selectedClipId);
  const updateClip = useStore((s) => s.updateClip);
  const splitClip = useStore((s) => s.splitClip);

  const clip = project?.clips.find((c) => c.id === selectedClipId);
  if (!clip) {
    return (
      <div className="card text-sm text-slate-400">
        Select a clip in the timeline to trim, split, set transition, or adjust volume.
      </div>
    );
  }

  const dur = clip.duration || clip.trimEnd;
  const mid = (clip.trimStart + clip.trimEnd) / 2;
  const clipDur = clip.trimEnd - clip.trimStart;
  const clipIdx = project!.clips.findIndex((c) => c.id === clip.id);

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <span className="label mb-0">Edit clip</span>
        <span className="font-mono text-xs text-slate-500">{fmtTime(clipDur, true)}</span>
      </div>

      {/* Transition (only meaningful for clip index > 0) */}
      {clipIdx > 0 && (
        <div>
          <label className="label">Transition in</label>
          <div className="flex gap-2">
            {TRANSITIONS.map((t) => (
              <button
                key={t.id}
                onClick={() => updateClip(clip.id, { transition: t.id })}
                title={t.desc}
                className={`chip flex-1 text-center ${
                  (clip.transition ?? 'cut') === t.id ? 'border-brand text-brand-glow' : ''
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <label className="label">Trim start · {fmtTime(clip.trimStart, true)}</label>
        <input
          type="range"
          min={0}
          max={dur}
          step={0.05}
          value={clip.trimStart}
          onChange={(e) =>
            updateClip(clip.id, {
              trimStart: clamp(parseFloat(e.target.value), 0, clip.trimEnd - 0.1),
            })
          }
          className="w-full"
        />
      </div>

      <div>
        <label className="label">Trim end · {fmtTime(clip.trimEnd, true)}</label>
        <input
          type="range"
          min={0}
          max={dur}
          step={0.05}
          value={clip.trimEnd}
          onChange={(e) =>
            updateClip(clip.id, {
              trimEnd: clamp(parseFloat(e.target.value), clip.trimStart + 0.1, dur),
            })
          }
          className="w-full"
        />
      </div>

      <div>
        <label className="label">Volume · {Math.round(clip.volume * 100)}%</label>
        <input
          type="range"
          min={0}
          max={1.5}
          step={0.05}
          value={clip.volume}
          onChange={(e) => updateClip(clip.id, { volume: parseFloat(e.target.value) })}
          className="w-full"
        />
      </div>

      <button onClick={() => splitClip(clip.id, mid)} className="btn-ghost w-full text-sm">
        ✂️ Split at midpoint ({fmtTime(mid, true)})
      </button>
    </div>
  );
}
