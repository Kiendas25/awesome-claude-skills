import { create } from 'zustand';
import type { Clip, MusicTrack, Project, Screen, Template, TextOverlay, TextPosition } from '../types';
import { uid } from '../utils/format';
import { saveProjectMeta } from './storage';
import { getTemplate } from '../templates';

function newProject(name: string): Project {
  return {
    id: uid('p_'),
    name,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    templateId: null,
    clips: [],
    overlays: [],
    music: null,
    export: { width: 1080, height: 1920, fps: 30 },
  };
}

/** Total trimmed duration of all clips. */
export function totalDuration(clips: Clip[]): number {
  return clips.reduce((s, c) => s + Math.max(0, c.trimEnd - c.trimStart), 0);
}

interface AppState {
  screen: Screen;
  project: Project | null;
  selectedClipId: string | null;
  selectedOverlayId: string | null;

  setScreen: (s: Screen) => void;
  createProject: (name?: string) => void;
  closeProject: () => void;
  renameProject: (name: string) => void;

  addClipFromFile: (file: File) => Promise<void>;
  removeClip: (id: string) => void;
  selectClip: (id: string | null) => void;
  updateClip: (id: string, patch: Partial<Clip>) => void;
  moveClip: (id: string, dir: -1 | 1) => void;
  splitClip: (id: string, atSeconds: number) => void;

  addOverlay: (partial?: Partial<TextOverlay>) => void;
  updateOverlay: (id: string, patch: Partial<TextOverlay>) => void;
  removeOverlay: (id: string) => void;
  selectOverlay: (id: string | null) => void;

  setMusicFromFile: (file: File) => Promise<void>;
  setMusicVolume: (v: number) => void;
  removeMusic: () => void;

  applyTemplate: (t: Template) => void;
  persist: () => void;
}

function probeDuration(url: string): Promise<number> {
  return new Promise((resolve) => {
    const v = document.createElement('video');
    v.preload = 'metadata';
    v.onloadedmetadata = () => resolve(isFinite(v.duration) ? v.duration : 0);
    v.onerror = () => resolve(0);
    v.src = url;
  });
}

export const useStore = create<AppState>((set, get) => ({
  screen: 'home',
  project: null,
  selectedClipId: null,
  selectedOverlayId: null,

  setScreen: (screen) => set({ screen }),

  createProject: (name) => {
    const p = newProject(name?.trim() || 'Untitled');
    saveProjectMeta(p);
    set({ project: p, screen: 'editor', selectedClipId: null, selectedOverlayId: null });
  },

  closeProject: () => set({ project: null, screen: 'home' }),

  renameProject: (name) => {
    const p = get().project;
    if (!p) return;
    const next = { ...p, name, updatedAt: Date.now() };
    set({ project: next });
    saveProjectMeta(next);
  },

  addClipFromFile: async (file) => {
    const p = get().project;
    if (!p) return;
    const url = URL.createObjectURL(file);
    const duration = await probeDuration(url);
    const clip: Clip = {
      id: uid('c_'),
      name: file.name,
      url,
      duration: duration || 0,
      trimStart: 0,
      trimEnd: duration || 0,
      volume: 1,
    };
    const next = { ...p, clips: [...p.clips, clip], updatedAt: Date.now() };
    set({ project: next, selectedClipId: clip.id });
    saveProjectMeta(next);
  },

  removeClip: (id) => {
    const p = get().project;
    if (!p) return;
    const clip = p.clips.find((c) => c.id === id);
    if (clip) URL.revokeObjectURL(clip.url);
    const next = { ...p, clips: p.clips.filter((c) => c.id !== id), updatedAt: Date.now() };
    set({
      project: next,
      selectedClipId: get().selectedClipId === id ? null : get().selectedClipId,
    });
    saveProjectMeta(next);
  },

  selectClip: (id) => set({ selectedClipId: id }),

  updateClip: (id, patch) => {
    const p = get().project;
    if (!p) return;
    const next = {
      ...p,
      clips: p.clips.map((c) => (c.id === id ? { ...c, ...patch } : c)),
      updatedAt: Date.now(),
    };
    set({ project: next });
  },

  moveClip: (id, dir) => {
    const p = get().project;
    if (!p) return;
    const idx = p.clips.findIndex((c) => c.id === id);
    const target = idx + dir;
    if (idx < 0 || target < 0 || target >= p.clips.length) return;
    const clips = [...p.clips];
    [clips[idx], clips[target]] = [clips[target], clips[idx]];
    const next = { ...p, clips, updatedAt: Date.now() };
    set({ project: next });
    saveProjectMeta(next);
  },

  splitClip: (id, atSeconds) => {
    const p = get().project;
    if (!p) return;
    const idx = p.clips.findIndex((c) => c.id === id);
    if (idx < 0) return;
    const c = p.clips[idx];
    const cut = Math.min(Math.max(atSeconds, c.trimStart + 0.1), c.trimEnd - 0.1);
    if (!isFinite(cut) || cut <= c.trimStart || cut >= c.trimEnd) return;
    const first: Clip = { ...c, id: uid('c_'), trimEnd: cut };
    const second: Clip = { ...c, id: uid('c_'), trimStart: cut };
    const clips = [...p.clips];
    clips.splice(idx, 1, first, second);
    const next = { ...p, clips, updatedAt: Date.now() };
    set({ project: next, selectedClipId: first.id });
    saveProjectMeta(next);
  },

  addOverlay: (partial) => {
    const p = get().project;
    if (!p) return;
    const total = totalDuration(p.clips) || 5;
    const tpl = getTemplate(p.templateId);
    const style = tpl?.textStyle ?? {
      position: 'center' as TextPosition,
      fontSize: 72,
      color: '#ffffff',
      background: true,
    };
    const overlay: TextOverlay = {
      id: uid('o_'),
      text: 'Tap to edit text',
      position: style.position,
      fontSize: style.fontSize,
      color: style.color,
      background: style.background,
      start: 0,
      end: Math.min(total, 3),
      ...partial,
    };
    const next = { ...p, overlays: [...p.overlays, overlay], updatedAt: Date.now() };
    set({ project: next, selectedOverlayId: overlay.id });
    saveProjectMeta(next);
  },

  updateOverlay: (id, patch) => {
    const p = get().project;
    if (!p) return;
    const next = {
      ...p,
      overlays: p.overlays.map((o) => (o.id === id ? { ...o, ...patch } : o)),
      updatedAt: Date.now(),
    };
    set({ project: next });
    saveProjectMeta(next);
  },

  removeOverlay: (id) => {
    const p = get().project;
    if (!p) return;
    const next = { ...p, overlays: p.overlays.filter((o) => o.id !== id), updatedAt: Date.now() };
    set({
      project: next,
      selectedOverlayId: get().selectedOverlayId === id ? null : get().selectedOverlayId,
    });
    saveProjectMeta(next);
  },

  selectOverlay: (id) => set({ selectedOverlayId: id }),

  setMusicFromFile: async (file) => {
    const p = get().project;
    if (!p) return;
    if (p.music) URL.revokeObjectURL(p.music.url);
    const music: MusicTrack = { name: file.name, url: URL.createObjectURL(file), volume: 0.7 };
    const next = { ...p, music, updatedAt: Date.now() };
    set({ project: next });
    saveProjectMeta(next);
  },

  setMusicVolume: (v) => {
    const p = get().project;
    if (!p || !p.music) return;
    set({ project: { ...p, music: { ...p.music, volume: v } } });
  },

  removeMusic: () => {
    const p = get().project;
    if (!p) return;
    if (p.music) URL.revokeObjectURL(p.music.url);
    const next = { ...p, music: null, updatedAt: Date.now() };
    set({ project: next });
    saveProjectMeta(next);
  },

  applyTemplate: (t) => {
    const p = get().project;
    if (!p) return;
    const starter: TextOverlay[] = t.starterOverlays.map((s, i) => ({
      id: uid('o_'),
      text: s.text,
      position: s.position,
      fontSize: t.textStyle.fontSize,
      color: t.textStyle.color,
      background: t.textStyle.background,
      start: i * t.suggestedClipSeconds,
      end: (i + 1) * t.suggestedClipSeconds,
    }));
    const next: Project = {
      ...p,
      templateId: t.id,
      export: { ...t.export },
      // Keep existing overlays, append the template's starters.
      overlays: [...p.overlays, ...starter],
      updatedAt: Date.now(),
    };
    set({ project: next, screen: 'editor' });
    saveProjectMeta(next);
  },

  persist: () => {
    const p = get().project;
    if (p) saveProjectMeta(p);
  },
}));
