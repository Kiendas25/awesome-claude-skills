// Local, rule-based "AI" helper. No network, no paid API.
// Everything here is deterministic text generation driven by JSON templates
// and simple string interpolation. It is intentionally transparent.

export type Niche =
  | 'fitness'
  | 'business'
  | 'tech'
  | 'food'
  | 'travel'
  | 'education'
  | 'beauty'
  | 'gaming'
  | 'finance'
  | 'general';

export const NICHES: { id: Niche; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'fitness', label: 'Fitness' },
  { id: 'business', label: 'Business' },
  { id: 'tech', label: 'Tech' },
  { id: 'food', label: 'Food' },
  { id: 'travel', label: 'Travel' },
  { id: 'education', label: 'Education' },
  { id: 'beauty', label: 'Beauty' },
  { id: 'gaming', label: 'Gaming' },
  { id: 'finance', label: 'Finance' },
];

// Hook frameworks — each is a function of the topic.
const HOOK_PATTERNS: ((t: string) => string)[] = [
  (t) => `Stop scrolling if you care about ${t}.`,
  (t) => `Nobody talks about this ${t} secret.`,
  (t) => `I tried ${t} for 30 days. Here's what happened.`,
  (t) => `3 ${t} mistakes that are costing you.`,
  (t) => `The truth about ${t} nobody tells you.`,
  (t) => `Watch this before you try ${t}.`,
  (t) => `${t}, but make it actually simple.`,
  (t) => `This ${t} hack feels illegal to know.`,
  (t) => `POV: you finally understand ${t}.`,
  (t) => `Why your ${t} isn't working (and the fix).`,
];

const CTA_PATTERNS: string[] = [
  'Follow for part 2 👀',
  'Save this so you don\'t forget.',
  'Comment "GUIDE" and I\'ll send it.',
  'Share this with someone who needs it.',
  'Follow for daily tips.',
  'Tap the link in bio to learn more.',
  'Which one will you try? Comment below 👇',
];

const NICHE_TAGS: Record<Niche, string[]> = {
  fitness: ['fitness', 'gymtok', 'workout', 'fitnesstips', 'healthylifestyle'],
  business: ['business', 'entrepreneur', 'startup', 'sidehustle', 'businesstips'],
  tech: ['tech', 'technology', 'ai', 'coding', 'gadgets'],
  food: ['food', 'recipe', 'foodtok', 'cooking', 'easyrecipes'],
  travel: ['travel', 'traveltok', 'wanderlust', 'traveltips', 'budgettravel'],
  education: ['learnontiktok', 'education', 'studytok', 'facts', 'didyouknow'],
  beauty: ['beauty', 'skincare', 'makeup', 'beautytips', 'glowup'],
  gaming: ['gaming', 'gamingtok', 'gamer', 'gameplay', 'gamingclips'],
  finance: ['finance', 'money', 'investing', 'personalfinance', 'moneytips'],
  general: ['viral', 'fyp', 'foryou', 'trending', 'contentcreator'],
};

const COMMON_TAGS = ['fyp', 'foryoupage', 'viral', 'shorts', 'reels'];

function pickN<T>(arr: T[], n: number, seed = 0): T[] {
  // Deterministic-ish rotation so repeated calls vary a little but stay stable per seed.
  const out: T[] = [];
  for (let i = 0; i < Math.min(n, arr.length); i++) {
    out.push(arr[(i + seed) % arr.length]);
  }
  return out;
}

export function generateHooks(topic: string, count = 6, seed = 0): string[] {
  const t = topic.trim() || 'this topic';
  return pickN(HOOK_PATTERNS, count, seed).map((fn) => fn(t));
}

export function generateCaptions(topic: string, niche: Niche, count = 4): string[] {
  const t = topic.trim() || 'your idea';
  const base = [
    `Here's everything you need to know about ${t}.`,
    `${t} explained in 30 seconds 👇`,
    `If you do one thing for your ${niche} journey, make it this.`,
    `The simplest way to start with ${t} today.`,
    `Bookmark this ${t} breakdown for later.`,
  ];
  return base.slice(0, count);
}

export function generateCTAs(count = 4, seed = 0): string[] {
  return pickN(CTA_PATTERNS, count, seed);
}

export function generateHashtags(niche: Niche, topic: string): string[] {
  const fromTopic = topic
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, '')
    .split(/\s+/)
    .filter((w) => w.length > 2)
    .slice(0, 3);
  const set = new Set<string>([...fromTopic, ...NICHE_TAGS[niche], ...COMMON_TAGS]);
  return Array.from(set)
    .slice(0, 12)
    .map((t) => `#${t}`);
}

export interface VideoStructureStep {
  range: string;
  label: string;
  note: string;
}

export function generateStructure(durationSec = 30, cuts = 4): VideoStructureStep[] {
  const hookEnd = Math.max(2, Math.round(durationSec * 0.1));
  const ctaStart = Math.max(hookEnd + 1, Math.round(durationSec * 0.85));
  const bodyCuts = Math.max(1, cuts - 1);
  const bodyLen = ctaStart - hookEnd;
  const steps: VideoStructureStep[] = [
    { range: `0–${hookEnd}s`, label: 'Hook', note: 'Bold claim or question. Big on-screen text.' },
  ];
  for (let i = 0; i < bodyCuts; i++) {
    const a = hookEnd + Math.round((bodyLen * i) / bodyCuts);
    const b = hookEnd + Math.round((bodyLen * (i + 1)) / bodyCuts);
    steps.push({
      range: `${a}–${b}s`,
      label: `Point ${i + 1}`,
      note: 'One idea per cut. Keep it moving, add a caption.',
    });
  }
  steps.push({
    range: `${ctaStart}–${durationSec}s`,
    label: 'CTA',
    note: 'Tell viewers exactly what to do next.',
  });
  return steps;
}

export interface SuggestedTemplate {
  templateId: string;
  reason: string;
}

/** Map a free-text description to a recommended built-in template id. */
export function suggestTemplate(description: string): SuggestedTemplate {
  const d = description.toLowerCase();
  if (/quote|motivat|mindset|discipline/.test(d))
    return { templateId: 'quote', reason: 'Mentions motivation/quotes.' };
  if (/podcast|interview|talking|episode/.test(d))
    return { templateId: 'podcast', reason: 'Talking-head / podcast style detected.' };
  if (/before|after|transform|glow ?up|result/.test(d))
    return { templateId: 'beforeafter', reason: 'Transformation / reveal detected.' };
  if (/product|promo|sale|shop|buy|launch|drop/.test(d))
    return { templateId: 'product', reason: 'Product / promo language detected.' };
  if (/meme|funny|joke|relatable/.test(d))
    return { templateId: 'meme', reason: 'Humor / meme language detected.' };
  if (/faceless|b-?roll|aesthetic|lo-?fi|no face/.test(d))
    return { templateId: 'faceless', reason: 'Faceless / b-roll style detected.' };
  return { templateId: 'hook', reason: 'Defaulting to a strong hook-first structure.' };
}
