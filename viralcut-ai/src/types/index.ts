// Shared domain types for ViralCut AI.

export type Screen = 'home' | 'editor' | 'templates' | 'copystyle' | 'assistant';

/** A single video segment placed on the timeline. */
export interface Clip {
  id: string;
  name: string;
  /** Object URL for in-memory playback (not persisted). */
  url: string;
  /** Natural duration of the source media in seconds. */
  duration: number;
  /** Trim window into the source media, in seconds. */
  trimStart: number;
  trimEnd: number;
  /** Per-clip audio volume 0..1.5. */
  volume: number;
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
}

export interface MusicTrack {
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
  export: {
    width: number;
    height: number;
    fps: number;
  };
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

/** Persisted project shape — media URLs are stripped since blobs can't survive reloads. */
export interface StoredProjectMeta {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  templateId: string | null;
  clipCount: number;
  overlays: TextOverlay[];
  export: { width: number; height: number; fps: number };
}
