import type { Project, StoredProjectMeta, StoredClipMeta } from '../types';
import { deleteBlob } from './opfs';

const KEY = 'viralcut.projects.v2';

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
  const clips: StoredClipMeta[] = project.clips.map((c) => ({
    id: c.id,
    name: c.name,
    duration: c.duration,
    trimStart: c.trimStart,
    trimEnd: c.trimEnd,
    volume: c.volume,
    transition: c.transition,
  }));
  const meta: StoredProjectMeta = {
    id: project.id,
    name: project.name,
    createdAt: project.createdAt,
    updatedAt: Date.now(),
    templateId: project.templateId,
    clips,
    overlays: project.overlays,
    musicMeta: project.music
      ? { id: project.music.id, name: project.music.name, volume: project.music.volume }
      : null,
    export: project.export,
  };
  metas.push(meta);
  try {
    localStorage.setItem(KEY, JSON.stringify(metas));
  } catch {
    // Quota exceeded — non-fatal.
  }
}

/** Remove project metadata AND all associated OPFS blobs. */
export async function deleteProjectMeta(id: string): Promise<void> {
  const metas = loadProjectMetas();
  const target = metas.find((m) => m.id === id);
  if (target) {
    for (const c of target.clips) await deleteBlob(c.id);
    if (target.musicMeta) await deleteBlob(target.musicMeta.id);
  }
  localStorage.setItem(KEY, JSON.stringify(metas.filter((m) => m.id !== id)));
}
