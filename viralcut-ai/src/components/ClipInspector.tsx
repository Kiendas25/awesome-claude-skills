import { useStore } from '../lib/store';
import { fmtTime, clamp } from '../utils/format';

// Trim / split / volume controls for the currently selected clip.

export function ClipInspector() {
  const project = useStore((s) => s.project);
  const selectedClipId = useStore((s) => s.selectedClipId);
  const updateClip = useStore((s) => s.updateClip);
  const splitClip = useStore((s) => s.splitClip);

  const clip = project?.clips.find((c) => c.id === selectedClipId);
  if (!clip) {
    return (
      <div className="card text-sm text-slate-400">
        Select a clip in the timeline to trim, split or adjust its volume.
      </div>
    );
  }

  const dur = clip.duration || clip.trimEnd;
  const mid = (clip.trimStart + clip.trimEnd) / 2;

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <span className="label mb-0">Edit clip</span>
        <span className="font-mono text-xs text-slate-500">
          {fmtTime(clip.trimEnd - clip.trimStart, true)}
        </span>
      </div>

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
