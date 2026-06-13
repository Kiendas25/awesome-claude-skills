import type { Template } from '../types';

// Free, original templates. No CapCut assets — these are plain JSON recipes.
// Each defines aspect ratio, text placement, pacing hints and export settings.

const EXPORT_9_16 = { width: 1080, height: 1920, fps: 30 };

export const TEMPLATES: Template[] = [
  {
    id: 'hook',
    name: 'Hook',
    emoji: '🪝',
    description: 'Punchy opener that grabs attention in the first 2 seconds.',
    aspectRatio: '9:16',
    textStyle: { position: 'center', fontSize: 84, color: '#ffffff', background: true },
    captionStyle: { position: 'bottom', fontSize: 54, color: '#ffffff', background: true },
    suggestedClipSeconds: 3,
    suggestedCuts: 4,
    musicMood: 'energetic / trending',
    starterOverlays: [
      { text: 'WAIT FOR IT…', position: 'center' },
      { text: 'You need to see this', position: 'top' },
    ],
    export: EXPORT_9_16,
  },
  {
    id: 'quote',
    name: 'Motivational Quote',
    emoji: '🔥',
    description: 'Centered quote with calm pacing and bold typography.',
    aspectRatio: '9:16',
    textStyle: { position: 'center', fontSize: 72, color: '#ffffff', background: false },
    captionStyle: { position: 'bottom', fontSize: 48, color: '#e2e8f0', background: true },
    suggestedClipSeconds: 6,
    suggestedCuts: 2,
    musicMood: 'cinematic / uplifting',
    starterOverlays: [{ text: 'Discipline beats motivation.', position: 'center' }],
    export: EXPORT_9_16,
  },
  {
    id: 'podcast',
    name: 'Podcast Clip',
    emoji: '🎙️',
    description: 'Talking-head clip with bottom captions for accessibility.',
    aspectRatio: '9:16',
    textStyle: { position: 'top', fontSize: 56, color: '#22d3ee', background: true },
    captionStyle: { position: 'bottom', fontSize: 58, color: '#ffffff', background: true },
    suggestedClipSeconds: 30,
    suggestedCuts: 1,
    musicMood: 'subtle / none',
    starterOverlays: [{ text: 'EP. 42 — The big idea', position: 'top' }],
    export: EXPORT_9_16,
  },
  {
    id: 'beforeafter',
    name: 'Before / After',
    emoji: '↔️',
    description: 'Two-shot transformation reveal with labels.',
    aspectRatio: '9:16',
    textStyle: { position: 'top', fontSize: 70, color: '#ffffff', background: true },
    captionStyle: { position: 'bottom', fontSize: 50, color: '#ffffff', background: true },
    suggestedClipSeconds: 3,
    suggestedCuts: 2,
    musicMood: 'satisfying / build-up',
    starterOverlays: [
      { text: 'BEFORE', position: 'top' },
      { text: 'AFTER', position: 'top' },
    ],
    export: EXPORT_9_16,
  },
  {
    id: 'product',
    name: 'Product Promo',
    emoji: '🛍️',
    description: 'Fast cuts showing a product with a clear CTA at the end.',
    aspectRatio: '9:16',
    textStyle: { position: 'top', fontSize: 64, color: '#ffffff', background: true },
    captionStyle: { position: 'bottom', fontSize: 52, color: '#ffffff', background: true },
    suggestedClipSeconds: 2,
    suggestedCuts: 6,
    musicMood: 'upbeat / commercial',
    starterOverlays: [
      { text: 'New drop 👀', position: 'top' },
      { text: 'Link in bio', position: 'bottom' },
    ],
    export: EXPORT_9_16,
  },
  {
    id: 'meme',
    name: 'Meme Caption',
    emoji: '😂',
    description: 'Top white caption bar in classic meme style.',
    aspectRatio: '9:16',
    textStyle: { position: 'top', fontSize: 60, color: '#ffffff', background: true },
    captionStyle: { position: 'bottom', fontSize: 46, color: '#ffffff', background: true },
    suggestedClipSeconds: 4,
    suggestedCuts: 3,
    musicMood: 'funny / trending',
    starterOverlays: [{ text: 'me pretending to work', position: 'top' }],
    export: EXPORT_9_16,
  },
  {
    id: 'faceless',
    name: 'Faceless Video',
    emoji: '🥷',
    description: 'B-roll with large readable text — no face needed.',
    aspectRatio: '9:16',
    textStyle: { position: 'center', fontSize: 76, color: '#ffffff', background: true },
    captionStyle: { position: 'bottom', fontSize: 56, color: '#ffffff', background: true },
    suggestedClipSeconds: 4,
    suggestedCuts: 5,
    musicMood: 'lo-fi / ambient',
    starterOverlays: [{ text: '3 habits that changed my life', position: 'center' }],
    export: EXPORT_9_16,
  },
];

export function getTemplate(id: string | null): Template | undefined {
  if (!id) return undefined;
  return TEMPLATES.find((t) => t.id === id);
}
