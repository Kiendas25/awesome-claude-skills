import type { Project, StoredProjectMeta } from '../types';

// Local-first persistence. We store project *metadata* in localStorage so the
// list survives reloads. Media blobs (object URLs) cannot be persisted this way,
// so reopening a saved project asks the user to re-attach their video.
// This keeps the MVP free of any database/cloud dependency.

const KEY = 'viralcut.projects.v1';

export function loadProjectMetas(): StoredProjectMeta[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as StoredProjectMeta[];
    return Array.isArray(parsed) ? parsed.sort((a, b) => b.updatedAt - a.updatedAt) : [];
  } catch {
    return [];
  }
}

export function saveProjectMeta(project: Project): void {
  const metas = loadProjectMetas().filter((m) => m.id !== project.id);
  const meta: StoredProjectMeta = {
    id: project.id,
    name: project.name,
    createdAt: project.createdAt,
    updatedAt: Date.now(),
    templateId: project.templateId,
    clipCount: project.clips.length,
    overlays: project.overlays,
    export: project.export,
  };
  metas.push(meta);
  try {
    localStorage.setItem(KEY, JSON.stringify(metas));
  } catch {
    // Quota or private-mode failure — non-fatal for the MVP.
  }
}

export function deleteProjectMeta(id: string): void {
  const metas = loadProjectMetas().filter((m) => m.id !== id);
  localStorage.setItem(KEY, JSON.stringify(metas));
}
