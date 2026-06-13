import { useState } from 'react';
import { useStore } from '../lib/store';
import { AppHeader } from '../components/AppHeader';
import type { Template, TextPosition } from '../types';
import { suggestTemplate } from '../utils/ai';
import { getTemplate } from '../templates';
import { uid } from '../utils/format';

// "Copy Style" — describe a video you like (or paste a URL for reference only),
// and we synthesize a REUSABLE LOCAL TEMPLATE. We never download the video.

const PACING = ['slow', 'medium', 'fast'] as const;
const TEXT_STYLES: { id: TextPosition; label: string }[] = [
  { id: 'top', label: 'Top bar' },
  { id: 'center', label: 'Centered' },
  { id: 'bottom', label: 'Captions' },
];

export function CopyStyle() {
  const applyTemplate = useStore((s) => s.applyTemplate);
  const createProject = useStore((s) => s.createProject);
  const project = useStore((s) => s.project);
  const setScreen = useStore((s) => s.setScreen);

  const [url, setUrl] = useState('');
  const [niche, setNiche] = useState('');
  const [pacing, setPacing] = useState<(typeof PACING)[number]>('fast');
  const [textStyle, setTextStyle] = useState<TextPosition>('center');
  const [color, setColor] = useState('#ffffff');
  const [hook, setHook] = useState('');
  const [cuts, setCuts] = useState(5);
  const [musicMood, setMusicMood] = useState('energetic / trending');
  const [generated, setGenerated] = useState<Template | null>(null);

  function build(): Template {
    const secPerClip = pacing === 'fast' ? 2 : pacing === 'medium' ? 4 : 7;
    const fontSize = textStyle === 'center' ? 80 : 58;
    const suggestion = suggestTemplate(`${niche} ${hook} ${musicMood}`);
    const base = getTemplate(suggestion.templateId);
    const t: Template = {
      id: uid('custom_'),
      name: niche ? `${niche} style` : 'Custom style',
      emoji: '🎯',
      description: `Copied style · ${pacing} pacing · ${cuts} cuts · ${musicMood}`,
      aspectRatio: '9:16',
      textStyle: { position: textStyle, fontSize, color, background: true },
      captionStyle: { position: 'bottom', fontSize: 54, color: '#ffffff', background: true },
      suggestedClipSeconds: secPerClip,
      suggestedCuts: cuts,
      musicMood,
      starterOverlays: [
        { text: hook || base?.starterOverlays[0]?.text || 'Your hook here', position: textStyle },
      ],
      export: { width: 1080, height: 1920, fps: 30 },
    };
    return t;
  }

  function onGenerate() {
    setGenerated(build());
  }

  function onUse() {
    const t = generated ?? build();
    if (!project) createProject(t.name);
    applyTemplate(t);
    setScreen('editor');
  }

  return (
    <div className="pb-24">
      <AppHeader title="Copy Style" subtitle="Turn a vibe into a reusable template" />
      <div className="mx-auto max-w-md space-y-4 px-4 pt-4">
        <div className="card border-amber-500/40 bg-amber-500/5 text-xs text-amber-200/90">
          We never download videos. Paste a URL only as a personal reference — describe the style
          below and we build a local template from your description.
        </div>

        <div className="card space-y-3">
          <div>
            <label className="label">Reference URL (optional, not downloaded)</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://… (kept locally as a note)"
              className="input"
            />
          </div>

          <div>
            <label className="label">Niche</label>
            <input
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              placeholder="fitness, finance, cooking…"
              className="input"
            />
          </div>

          <div>
            <label className="label">Pacing</label>
            <div className="flex gap-2">
              {PACING.map((p) => (
                <button
                  key={p}
                  onClick={() => setPacing(p)}
                  className={`chip flex-1 capitalize ${pacing === p ? 'border-brand text-brand-glow' : ''}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="label">Text style</label>
            <div className="flex gap-2">
              {TEXT_STYLES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTextStyle(t.id)}
                  className={`chip flex-1 ${textStyle === t.id ? 'border-brand text-brand-glow' : ''}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <label className="label mb-0">Text color</label>
            <input
              type="color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              className="h-8 w-12 rounded border border-edge bg-transparent"
            />
          </div>

          <div>
            <label className="label">Hook line</label>
            <input
              value={hook}
              onChange={(e) => setHook(e.target.value)}
              placeholder="Stop scrolling if…"
              className="input"
            />
          </div>

          <div>
            <label className="label">Number of cuts · {cuts}</label>
            <input
              type="range"
              min={1}
              max={12}
              value={cuts}
              onChange={(e) => setCuts(parseInt(e.target.value))}
              className="w-full"
            />
          </div>

          <div>
            <label className="label">Music mood</label>
            <input
              value={musicMood}
              onChange={(e) => setMusicMood(e.target.value)}
              className="input"
            />
          </div>

          <button onClick={onGenerate} className="btn-ghost w-full">
            🔧 Generate template
          </button>
        </div>

        {generated && (
          <div className="card space-y-2 border-brand/50">
            <h3 className="font-bold">
              {generated.emoji} {generated.name}
            </h3>
            <p className="text-sm text-slate-400">{generated.description}</p>
            <div className="flex flex-wrap gap-1.5">
              <span className="chip">~{generated.suggestedClipSeconds}s / clip</span>
              <span className="chip">{generated.suggestedCuts} cuts</span>
              <span className="chip capitalize">text: {generated.textStyle.position}</span>
              <span className="chip">🎵 {generated.musicMood}</span>
            </div>
            <button onClick={onUse} className="btn-primary w-full">
              Use this template
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
