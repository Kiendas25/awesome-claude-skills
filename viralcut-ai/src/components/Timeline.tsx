import { useStore } from '../lib/store';
import { fmtTime } from '../utils/format';

// Bottom clip strip: shows clips in order with quick reorder / select / delete.

export function Timeline() {
  const project = useStore((s) => s.project);
  const selectedClipId = useStore((s) => s.selectedClipId);
  const selectClip = useStore((s) => s.selectClip);
  const moveClip = useStore((s) => s.moveClip);
  const removeClip = useStore((s) => s.removeClip);

  const clips = project?.clips ?? [];
  if (clips.length === 0) return null;

  return (
    <div className="card">
      <div className="mb-2 flex items-center justify-between">
        <span className="label mb-0">Timeline · {clips.length} clip{clips.length > 1 ? 's' : ''}</span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {clips.map((c, i) => {
          const dur = Math.max(0, c.trimEnd - c.trimStart);
          const active = c.id === selectedClipId;
          return (
            <div
              key={c.id}
              className={`relative w-28 shrink-0 rounded-xl border p-2 ${
                active ? 'border-brand bg-panel2' : 'border-edge bg-panel2/60'
              }`}
              onClick={() => selectClip(c.id)}
            >
              <div className="flex h-10 items-center justify-center rounded-lg bg-gradient-to-br from-brand/30 to-accent/20 text-xl">
                🎞️
              </div>
              <p className="mt-1 truncate text-[10px] text-slate-300">{c.name}</p>
              <p className="font-mono text-[10px] text-slate-500">{fmtTime(dur, true)}</p>
              <div className="mt-1 flex items-center justify-between">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    moveClip(c.id, -1);
                  }}
                  disabled={i === 0}
                  className="rounded px-1 text-slate-400 disabled:opacity-20"
                  aria-label="Move left"
                >
                  ◀
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Remove this clip?')) removeClip(c.id);
                  }}
                  className="rounded px-1 text-red-400"
                  aria-label="Delete clip"
                >
                  🗑
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    moveClip(c.id, 1);
                  }}
                  disabled={i === clips.length - 1}
                  className="rounded px-1 text-slate-400 disabled:opacity-20"
                  aria-label="Move right"
                >
                  ▶
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
