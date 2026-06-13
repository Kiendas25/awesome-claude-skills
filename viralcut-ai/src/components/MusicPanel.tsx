import { useRef } from 'react';
import { useStore } from '../lib/store';

// Background music from a local audio file. No streaming, no library — bring your own.
export function MusicPanel() {
  const project = useStore((s) => s.project);
  const setMusicFromFile = useStore((s) => s.setMusicFromFile);
  const setMusicVolume = useStore((s) => s.setMusicVolume);
  const removeMusic = useStore((s) => s.removeMusic);
  const inputRef = useRef<HTMLInputElement>(null);

  const music = project?.music;

  return (
    <div className="card space-y-3">
      <span className="label mb-0">Background music</span>
      <input
        ref={inputRef}
        type="file"
        accept="audio/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) setMusicFromFile(f);
          e.target.value = '';
        }}
      />
      {!music ? (
        <button onClick={() => inputRef.current?.click()} className="btn-ghost w-full text-sm">
          🎵 Add music from device
        </button>
      ) : (
        <>
          <p className="truncate text-sm text-slate-300">🎵 {music.name}</p>
          <div>
            <label className="label">Music volume · {Math.round(music.volume * 100)}%</label>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={music.volume}
              onChange={(e) => setMusicVolume(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>
          <div className="flex gap-2">
            <button onClick={() => inputRef.current?.click()} className="btn-ghost flex-1 text-sm">
              Replace
            </button>
            <button onClick={removeMusic} className="btn-ghost flex-1 text-sm text-red-300">
              Remove
            </button>
          </div>
        </>
      )}
    </div>
  );
}
