import { useState } from 'react';
import { AppHeader } from '../components/AppHeader';
import {
  NICHES,
  type Niche,
  generateHooks,
  generateCaptions,
  generateCTAs,
  generateHashtags,
  generateStructure,
  suggestTemplate,
} from '../utils/ai';
import { useStore } from '../lib/store';
import { getTemplate, TEMPLATES } from '../templates';

type Tab = 'hooks' | 'captions' | 'cta' | 'hashtags' | 'structure' | 'template';

const TABS: { id: Tab; label: string }[] = [
  { id: 'hooks', label: 'Hooks' },
  { id: 'captions', label: 'Captions' },
  { id: 'cta', label: 'CTA' },
  { id: 'hashtags', label: 'Hashtags' },
  { id: 'structure', label: 'Structure' },
  { id: 'template', label: 'Template' },
];

function CopyRow({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-edge bg-panel2 px-3 py-2">
      <span className="text-sm text-slate-200">{text}</span>
      <button
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          } catch {
            /* clipboard blocked — ignore */
          }
        }}
        className="shrink-0 text-xs text-brand-glow"
      >
        {copied ? '✓' : 'Copy'}
      </button>
    </div>
  );
}

// Local rule-based assistant. 100% offline, deterministic, no paid AI API.
export function Assistant() {
  const applyTemplate = useStore((s) => s.applyTemplate);
  const project = useStore((s) => s.project);
  const createProject = useStore((s) => s.createProject);
  const setScreen = useStore((s) => s.setScreen);

  const [tab, setTab] = useState<Tab>('hooks');
  const [topic, setTopic] = useState('');
  const [niche, setNiche] = useState<Niche>('general');
  const [seed, setSeed] = useState(0);
  const [duration, setDuration] = useState(30);

  const suggestion = suggestTemplate(`${topic} ${niche}`);
  const suggested = getTemplate(suggestion.templateId);

  return (
    <div className="pb-24">
      <AppHeader title="AI Assistant" subtitle="Offline · rule-based · no paid API" />
      <div className="mx-auto max-w-md space-y-4 px-4 pt-4">
        <div className="card space-y-3">
          <div>
            <label className="label">Topic</label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. morning routines, budgeting…"
              className="input"
            />
          </div>
          <div>
            <label className="label">Niche</label>
            <div className="flex flex-wrap gap-1.5">
              {NICHES.map((n) => (
                <button
                  key={n.id}
                  onClick={() => setNiche(n.id)}
                  className={`chip ${niche === n.id ? 'border-brand text-brand-glow' : ''}`}
                >
                  {n.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-1.5 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`chip shrink-0 ${tab === t.id ? 'border-brand text-brand-glow' : ''}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="space-y-2">
          {tab === 'hooks' && (
            <>
              {generateHooks(topic, 6, seed).map((h, i) => (
                <CopyRow key={i} text={h} />
              ))}
              <button onClick={() => setSeed((s) => s + 1)} className="btn-ghost w-full text-sm">
                🔄 More ideas
              </button>
            </>
          )}

          {tab === 'captions' &&
            generateCaptions(topic, niche, 5).map((c, i) => <CopyRow key={i} text={c} />)}

          {tab === 'cta' && (
            <>
              {generateCTAs(5, seed).map((c, i) => (
                <CopyRow key={i} text={c} />
              ))}
              <button onClick={() => setSeed((s) => s + 1)} className="btn-ghost w-full text-sm">
                🔄 More ideas
              </button>
            </>
          )}

          {tab === 'hashtags' && (
            <div className="card flex flex-wrap gap-1.5">
              {generateHashtags(niche, topic).map((h, i) => (
                <span key={i} className="chip text-accent">
                  {h}
                </span>
              ))}
              <CopyRow text={generateHashtags(niche, topic).join(' ')} />
            </div>
          )}

          {tab === 'structure' && (
            <>
              <div className="card">
                <label className="label">Target length · {duration}s</label>
                <input
                  type="range"
                  min={10}
                  max={90}
                  step={5}
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
              {generateStructure(duration, suggested?.suggestedCuts ?? 4).map((step, i) => (
                <div key={i} className="card flex gap-3 py-3">
                  <span className="chip h-fit shrink-0 font-mono">{step.range}</span>
                  <div>
                    <p className="font-semibold text-brand-glow">{step.label}</p>
                    <p className="text-sm text-slate-400">{step.note}</p>
                  </div>
                </div>
              ))}
            </>
          )}

          {tab === 'template' && suggested && (
            <div className="card space-y-3">
              <p className="text-sm text-slate-400">{suggestion.reason}</p>
              <h3 className="text-lg font-bold">
                {suggested.emoji} {suggested.name}
              </h3>
              <p className="text-sm text-slate-300">{suggested.description}</p>
              <button
                onClick={() => {
                  if (!project) createProject(suggested.name);
                  applyTemplate(suggested);
                  setScreen('editor');
                }}
                className="btn-primary w-full"
              >
                Use {suggested.name} template
              </button>
              <p className="label">Other templates</p>
              <div className="flex flex-wrap gap-1.5">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      if (!project) createProject(t.name);
                      applyTemplate(t);
                      setScreen('editor');
                    }}
                    className="chip"
                  >
                    {t.emoji} {t.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
