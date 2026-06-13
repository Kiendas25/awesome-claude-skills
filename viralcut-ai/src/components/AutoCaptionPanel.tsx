import { useRef, useState } from 'react';
import { useStore, totalDuration } from '../lib/store';
import type { TextOverlay } from '../types';

// Auto-caption strategies — fully offline, no paid API.
//
// 1. Script-to-captions: paste script, we split into equal-duration caption
//    overlays timed evenly across the total video duration.
//
// 2. Live mic (Chrome/Edge only): play video, browser SpeechRecognition
//    listens via mic. Each final segment → timed bottom caption.
//    Web Speech API types vary across TS DOM versions; we use `any` casts.

/* eslint-disable @typescript-eslint/no-explicit-any */
function getSpeechRec(): (new () => any) | undefined {
  if (typeof window === 'undefined') return undefined;
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

const SPEECH_SUPPORTED = typeof window !== 'undefined' && getSpeechRec() != null;

function scriptToCaptions(
  script: string,
  totalSec: number,
  fontSize: number
): Omit<TextOverlay, 'id'>[] {
  const sentences = script
    .replace(/\n+/g, ' ')
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (!sentences.length) return [];
  const dur = totalSec / sentences.length;
  return sentences.map((text, i) => ({
    text,
    position: 'bottom' as const,
    fontSize,
    color: '#ffffff',
    background: true,
    start: parseFloat((i * dur).toFixed(2)),
    end: parseFloat(((i + 1) * dur - 0.05).toFixed(2)),
    animation: 'fade-in' as const,
  }));
}

export function AutoCaptionPanel() {
  const project = useStore((s) => s.project);
  const addOverlay = useStore((s) => s.addOverlay);
  const updateOverlay = useStore((s) => s.updateOverlay);

  const [tab, setTab] = useState<'script' | 'live'>('script');
  const [script, setScript] = useState('');
  const [fontSize, setFontSize] = useState(54);
  const [added, setAdded] = useState(0);
  const [listening, setListening] = useState(false);
  const [liveLog, setLiveLog] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recRef = useRef<any | null>(null);
  const liveStartRef = useRef<number>(0);

  const clips = project?.clips ?? [];
  const total = totalDuration(clips);

  function applyScript() {
    if (!total || !script.trim()) return;
    const captions = scriptToCaptions(script, total, fontSize);
    for (const cap of captions) addOverlay(cap);
    setAdded(captions.length);
    setScript('');
  }

  function startLive() {
    const Ctor = getSpeechRec();
    if (!Ctor) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rec: any = new Ctor();
    rec.continuous = true;
    rec.interimResults = false;
    rec.lang = 'en-US';
    liveStartRef.current = Date.now() / 1000;
    setLiveLog('Listening… play your video now.');

    rec.onresult = (e: any) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          const text: string = e.results[i][0].transcript.trim();
          const now = Date.now() / 1000 - liveStartRef.current;
          addOverlay({
            text,
            position: 'bottom',
            fontSize,
            color: '#ffffff',
            background: true,
            start: Math.max(0, now - 3),
            end: now,
            animation: 'fade-in',
          });
          setLiveLog(`Captured: "${text}"`);
        }
      }
    };
    rec.onerror = (e: any) => {
      setLiveLog(`Mic error: ${e.error ?? 'unknown'}`);
      setListening(false);
    };
    rec.onend = () => setListening(false);
    rec.start();
    recRef.current = rec;
    setListening(true);
  }

  function stopLive() {
    recRef.current?.stop();
    recRef.current = null;
    setListening(false);
  }

  function shiftAllCaptions(deltaS: number) {
    if (!project) return;
    for (const o of project.overlays) {
      if (o.position === 'bottom') {
        updateOverlay(o.id, {
          start: Math.max(0, o.start + deltaS),
          end: Math.max(0.1, o.end + deltaS),
        });
      }
    }
  }

  const previewCount = script ? scriptToCaptions(script, total || 30, fontSize).length : 0;

  return (
    <div className="card space-y-3">
      <span className="label mb-0">Auto-captions</span>

      <div className="flex gap-2">
        {(['script', 'live'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`chip flex-1 ${tab === t ? 'border-brand text-brand-glow' : ''}`}
          >
            {t === 'script' ? '📄 Script' : '🎤 Live mic'}
          </button>
        ))}
      </div>

      <div>
        <label className="label">Caption font size · {fontSize}px</label>
        <input
          type="range"
          min={36}
          max={90}
          step={2}
          value={fontSize}
          onChange={(e) => setFontSize(parseInt(e.target.value))}
          className="w-full"
        />
      </div>

      {tab === 'script' && (
        <>
          <div>
            <label className="label">Paste your script</label>
            <textarea
              value={script}
              onChange={(e) => setScript(e.target.value)}
              rows={5}
              placeholder="Paste your spoken script here. Each sentence becomes a timed caption across the video."
              className="input resize-none"
            />
          </div>
          <button
            onClick={applyScript}
            disabled={!script.trim() || !total}
            className="btn-primary w-full"
          >
            ✨ Generate {previewCount} caption{previewCount === 1 ? '' : 's'}
          </button>
          {added > 0 && (
            <p className="text-sm text-emerald-400">✅ Added {added} caption(s) to timeline.</p>
          )}
          {!total && (
            <p className="text-xs text-amber-400">Add at least one video clip first.</p>
          )}
          <div className="flex items-center gap-2">
            <span className="label mb-0 shrink-0 text-xs">Shift timing</span>
            <button onClick={() => shiftAllCaptions(-0.5)} className="chip">−0.5s</button>
            <button onClick={() => shiftAllCaptions(0.5)} className="chip">+0.5s</button>
          </div>
        </>
      )}

      {tab === 'live' && (
        <>
          {!SPEECH_SUPPORTED ? (
            <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-300">
              Live capture requires Chrome or Edge with Web Speech API support.
            </p>
          ) : (
            <>
              <p className="text-sm text-slate-400">
                Allow microphone access, click Start, then play your video. Each recognised sentence
                is added as a timed bottom caption. Use headphones to prevent feedback.
              </p>
              {liveLog && (
                <p className="rounded-xl bg-panel2 px-3 py-2 text-sm text-slate-300">{liveLog}</p>
              )}
              <button
                onClick={listening ? stopLive : startLive}
                className={listening ? 'btn-ghost w-full' : 'btn-primary w-full'}
              >
                {listening ? '⏹ Stop listening' : '🎤 Start listening'}
              </button>
            </>
          )}
        </>
      )}
    </div>
  );
}
