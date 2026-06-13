import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useStore, totalDuration } from '../lib/store';
import type { TextOverlay } from '../types';
import { fmtTime, clamp } from '../utils/format';

// Live preview: plays all clips back-to-back inside a 9:16 frame and renders
// text overlays as DOM elements scaled to the export canvas (1080px wide).

function overlayStyle(o: TextOverlay, scale: number): React.CSSProperties {
  const vertical =
    o.position === 'top'
      ? { top: '12%' }
      : o.position === 'bottom'
        ? { bottom: '14%' }
        : { top: '50%', transform: 'translateY(-50%)' };
  return {
    position: 'absolute',
    left: '6%',
    right: '6%',
    ...vertical,
    textAlign: 'center',
    fontWeight: 800,
    lineHeight: 1.15,
    fontSize: `${o.fontSize * scale}px`,
    color: o.color,
    textShadow: '0 2px 6px rgba(0,0,0,0.85)',
    pointerEvents: 'none',
    wordBreak: 'break-word',
  };
}

export function VideoPreview() {
  const project = useStore((s) => s.project);
  const clips = project?.clips ?? [];
  const overlays = project?.overlays ?? [];

  const videoRef = useRef<HTMLVideoElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);

  const [index, setIndex] = useState(0);
  const [globalTime, setGlobalTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [scale, setScale] = useState(0.3);

  const total = totalDuration(clips);

  // Offsets of each clip on the global timeline.
  const offsets: number[] = [];
  {
    let acc = 0;
    for (const c of clips) {
      offsets.push(acc);
      acc += Math.max(0, c.trimEnd - c.trimStart);
    }
  }

  // Scale overlays relative to the 1080px export width.
  useLayoutEffect(() => {
    const el = frameRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setScale(el.clientWidth / 1080));
    ro.observe(el);
    setScale(el.clientWidth / 1080);
    return () => ro.disconnect();
  }, []);

  const loadClip = useCallback(
    (i: number, seekToStart = true) => {
      const v = videoRef.current;
      const clip = clips[i];
      if (!v || !clip) return;
      if (v.src !== clip.url) v.src = clip.url;
      const apply = () => {
        if (seekToStart) v.currentTime = clip.trimStart;
      };
      if (v.readyState >= 1) apply();
      else v.onloadedmetadata = apply;
    },
    [clips]
  );

  // Load the active clip whenever the index changes.
  useEffect(() => {
    if (clips.length === 0) return;
    loadClip(index);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, clips.length]);

  const stop = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    videoRef.current?.pause();
    setPlaying(false);
  }, []);

  const tick = useCallback(() => {
    const v = videoRef.current;
    const clip = clips[index];
    if (!v || !clip) return;
    const clipDur = Math.max(0, clip.trimEnd - clip.trimStart);
    const local = clamp(v.currentTime - clip.trimStart, 0, clipDur);
    setGlobalTime(offsets[index] + local);

    if (v.currentTime >= clip.trimEnd - 0.03 || v.ended) {
      if (index < clips.length - 1) {
        const ni = index + 1;
        setIndex(ni);
        const next = clips[ni];
        const v2 = videoRef.current!;
        const go = () => {
          v2.currentTime = next.trimStart;
          v2.play().catch(() => {});
        };
        if (v2.src !== next.url) {
          v2.src = next.url;
          v2.onloadedmetadata = go;
        } else go();
      } else {
        stop();
        setGlobalTime(total);
        return;
      }
    }
    rafRef.current = requestAnimationFrame(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clips, index, offsets, stop, total]);

  const play = useCallback(() => {
    const v = videoRef.current;
    if (!v || clips.length === 0) return;
    // Restart from the beginning if we're at the end.
    if (globalTime >= total - 0.05) {
      setIndex(0);
      loadClip(0);
    }
    v.play().catch(() => {});
    setPlaying(true);
    rafRef.current = requestAnimationFrame(tick);
  }, [clips.length, globalTime, total, loadClip, tick]);

  const seekGlobal = useCallback(
    (t: number) => {
      let i = 0;
      while (i < clips.length - 1 && t >= offsets[i] + (clips[i].trimEnd - clips[i].trimStart)) i++;
      const clip = clips[i];
      if (!clip) return;
      setIndex(i);
      const local = t - offsets[i];
      const v = videoRef.current!;
      const apply = () => {
        v.currentTime = clip.trimStart + clamp(local, 0, clip.trimEnd - clip.trimStart);
      };
      if (v.src !== clip.url) {
        v.src = clip.url;
        v.onloadedmetadata = apply;
      } else apply();
      setGlobalTime(t);
    },
    [clips, offsets]
  );

  useEffect(() => () => cancelAnimationFrame(rafRef.current), []);

  const activeOverlays = overlays.filter((o) => globalTime >= o.start && globalTime <= o.end);

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        ref={frameRef}
        className="relative aspect-[9/16] w-full max-w-[300px] overflow-hidden rounded-3xl border border-edge bg-black shadow-2xl"
      >
        {clips.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center text-slate-500">
            <span className="text-4xl">🎬</span>
            <p className="text-sm">No clips yet. Upload a video to start.</p>
          </div>
        ) : (
          <>
            <video
              ref={videoRef}
              className="h-full w-full object-cover"
              playsInline
              muted={false}
              onClick={() => (playing ? stop() : play())}
            />
            {activeOverlays.map((o) => (
              <div key={o.id} style={overlayStyle(o, scale)}>
                {o.background ? (
                  <span
                    style={{
                      background: 'rgba(0,0,0,0.55)',
                      padding: '0.1em 0.35em',
                      borderRadius: '0.3em',
                      boxDecorationBreak: 'clone',
                      WebkitBoxDecorationBreak: 'clone',
                    }}
                  >
                    {o.text}
                  </span>
                ) : (
                  o.text
                )}
              </div>
            ))}
          </>
        )}
      </div>

      {clips.length > 0 && (
        <div className="flex w-full max-w-[300px] items-center gap-3">
          <button
            onClick={() => (playing ? stop() : play())}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand text-white"
            aria-label={playing ? 'Pause' : 'Play'}
          >
            {playing ? '❚❚' : '▶'}
          </button>
          <input
            type="range"
            min={0}
            max={Math.max(0.1, total)}
            step={0.05}
            value={Math.min(globalTime, total)}
            onChange={(e) => {
              stop();
              seekGlobal(parseFloat(e.target.value));
            }}
            className="flex-1"
          />
          <span className="w-16 shrink-0 text-right font-mono text-xs text-slate-400">
            {fmtTime(globalTime, true)}/{fmtTime(total)}
          </span>
        </div>
      )}
    </div>
  );
}
