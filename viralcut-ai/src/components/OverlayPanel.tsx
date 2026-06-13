import { useStore, totalDuration } from '../lib/store';
import type { TextPosition } from '../types';
import { fmtTime, clamp } from '../utils/format';

const POSITIONS: TextPosition[] = ['top', 'center', 'bottom'];
const COLORS = ['#ffffff', '#22d3ee', '#7c5cff', '#fbbf24', '#f43f5e', '#000000'];

// Add / edit text overlays and manual captions.
export function OverlayPanel() {
  const project = useStore((s) => s.project);
  const selectedOverlayId = useStore((s) => s.selectedOverlayId);
  const addOverlay = useStore((s) => s.addOverlay);
  const updateOverlay = useStore((s) => s.updateOverlay);
  const removeOverlay = useStore((s) => s.removeOverlay);
  const selectOverlay = useStore((s) => s.selectOverlay);

  const overlays = project?.overlays ?? [];
  const total = totalDuration(project?.clips ?? []) || 5;
  const selected = overlays.find((o) => o.id === selectedOverlayId);

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <span className="label mb-0">Text & captions</span>
        <div className="flex gap-2">
          <button onClick={() => addOverlay()} className="chip border-brand text-brand-glow">
            + Text
          </button>
          <button
            onClick={() => addOverlay({ position: 'bottom', text: 'Caption goes here' })}
            className="chip border-accent text-accent"
          >
            + Caption
          </button>
        </div>
      </div>

      {overlays.length === 0 && (
        <p className="text-sm text-slate-400">No overlays yet. Add a title or caption.</p>
      )}

      <div className="flex flex-wrap gap-2">
        {overlays.map((o) => (
          <button
            key={o.id}
            onClick={() => selectOverlay(o.id === selectedOverlayId ? null : o.id)}
            className={`chip max-w-[140px] truncate ${
              o.id === selectedOverlayId ? 'border-brand text-brand-glow' : ''
            }`}
          >
            {o.text || '(empty)'}
          </button>
        ))}
      </div>

      {selected && (
        <div className="space-y-3 border-t border-edge pt-3">
          <div>
            <label className="label">Text</label>
            <textarea
              value={selected.text}
              onChange={(e) => updateOverlay(selected.id, { text: e.target.value })}
              rows={2}
              className="input resize-none"
            />
          </div>

          <div className="flex gap-2">
            {POSITIONS.map((p) => (
              <button
                key={p}
                onClick={() => updateOverlay(selected.id, { position: p })}
                className={`chip flex-1 capitalize ${
                  selected.position === p ? 'border-brand text-brand-glow' : ''
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          <div>
            <label className="label">Font size · {selected.fontSize}px</label>
            <input
              type="range"
              min={32}
              max={140}
              step={2}
              value={selected.fontSize}
              onChange={(e) => updateOverlay(selected.id, { fontSize: parseInt(e.target.value) })}
              className="w-full"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="label mb-0">Color</span>
            {COLORS.map((c) => (
              <button
                key={c}
                onClick={() => updateOverlay(selected.id, { color: c })}
                className={`h-6 w-6 rounded-full border-2 ${
                  selected.color === c ? 'border-white' : 'border-edge'
                }`}
                style={{ background: c }}
                aria-label={`Color ${c}`}
              />
            ))}
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              checked={selected.background}
              onChange={(e) => updateOverlay(selected.id, { background: e.target.checked })}
            />
            Background highlight
          </label>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Start · {fmtTime(selected.start, true)}</label>
              <input
                type="range"
                min={0}
                max={total}
                step={0.1}
                value={selected.start}
                onChange={(e) =>
                  updateOverlay(selected.id, {
                    start: clamp(parseFloat(e.target.value), 0, selected.end - 0.1),
                  })
                }
                className="w-full"
              />
            </div>
            <div>
              <label className="label">End · {fmtTime(selected.end, true)}</label>
              <input
                type="range"
                min={0}
                max={total}
                step={0.1}
                value={selected.end}
                onChange={(e) =>
                  updateOverlay(selected.id, {
                    end: clamp(parseFloat(e.target.value), selected.start + 0.1, total),
                  })
                }
                className="w-full"
              />
            </div>
          </div>

          <button
            onClick={() => removeOverlay(selected.id)}
            className="btn-ghost w-full text-sm text-red-300"
          >
            🗑 Delete overlay
          </button>
        </div>
      )}
    </div>
  );
}
