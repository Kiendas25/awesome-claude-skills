// Shared domain types for ViralCut AI.

export type Screen = 'home' | 'editor' | 'templates' | 'copystyle' | 'assistant';

/** How the transition INTO this clip is rendered. */
export type TransitionType = 'cut' | 'fade';

/** Animation that plays when a text overlay first appears. */
export type AnimationType = 'none' | 'fade-in' | 'slide-up' | 'pop';

/** A single video segment placed on the timeline. */
export interface Clip {
  id: string;
  name: string;
  /** Object URL for in-memory playback (not persisted). Empty string = media missing. */
  url: string;
  /** Natural duration of the source media in seconds. */
  duration: number;
  trimStart: number;
  trimEnd: number;
  /** Per-clip audio volume 0..1.5. */
  volume: number;
  /** How to enter this clip (from the previous one). Default: 'cut'. */
  transition: TransitionType;
}

export type TextPosition = 'top' | 'center' | 'bottom';

/** A text/caption overlay rendered on top of the preview and burned on export. */
export interface TextOverlay {
  id: string;
  text: string;
  position: TextPosition;
  fontSize: number;
  color: string;
  background: boolean;
  /** When the overlay appears, in seconds along the full timeline. */
  start: number;
  end: number;
  animation: AnimationType;
}

export interface MusicTrack {
  /** OPFS storage key for persistence. */
  id: string;
  name: string;
  url: string;
  volume: number;
}

export type AspectRatio = '9:16';

/** A reusable creative recipe applied to a project. */
export interface Template {
  id: string;
  name: string;
  emoji: string;
  description: string;
  aspectRatio: AspectRatio;
  textStyle: {
    position: TextPosition;
    fontSize: number;
    color: string;
    background: boolean;
  };
  captionStyle: {
    position: TextPosition;
    fontSize: number;
    color: string;
    background: boolean;
  };
  suggestedClipSeconds: number;
  suggestedCuts: number;
  musicMood: string;
  starterOverlays: { text: string; position: TextPosition }[];
  export: { width: number; height: number; fps: number };
}

/** A project is the full editable document, persisted to localStorage (sans media blobs). */
export interface Project {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  templateId: string | null;
  clips: Clip[];
  overlays: TextOverlay[];
  music: MusicTrack | null;
  export: { width: number; height: number; fps: number };
}

/** Clip metadata stored in localStorage (no URL — that lives in OPFS). */
export interface StoredClipMeta {
  id: string;
  name: string;
  duration: number;
  trimStart: number;
  trimEnd: number;
  volume: number;
  transition: TransitionType;
}

/** Persisted project shape. Media is referenced by ID and fetched from OPFS on restore. */
export interface StoredProjectMeta {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  templateId: string | null;
  clips: StoredClipMeta[];
  overlays: TextOverlay[];
  musicMeta: { id: string; name: string; volume: number } | null;
  export: { width: number; height: number; fps: number };
}
