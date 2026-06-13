// Origin Private File System — persist video/audio blobs across page reloads.
// Falls back silently if the browser doesn't support OPFS (Firefox < 111, old Safari).
//
// Files are stored as: <OPFS root>/viralcut-media/<id>
// IDs come from the Clip or MusicTrack; each blob replaces any previous version.

const DIR = 'viralcut-media';

export function isSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    'storage' in navigator &&
    typeof navigator.storage.getDirectory === 'function'
  );
}

async function getDir(): Promise<FileSystemDirectoryHandle> {
  const root = await navigator.storage.getDirectory();
  return root.getDirectoryHandle(DIR, { create: true });
}

export async function saveBlob(id: string, blob: Blob): Promise<void> {
  if (!isSupported()) return;
  try {
    const dir = await getDir();
    const fh = await dir.getFileHandle(id, { create: true });
    const writable = await fh.createWritable();
    await writable.write(blob);
    await writable.close();
  } catch (e) {
    console.warn('[OPFS] write failed', e);
  }
}

export async function loadBlob(id: string): Promise<Blob | null> {
  if (!isSupported()) return null;
  try {
    const dir = await getDir();
    const fh = await dir.getFileHandle(id);
    return await fh.getFile();
  } catch {
    return null;
  }
}

export async function deleteBlob(id: string): Promise<void> {
  if (!isSupported()) return;
  try {
    const dir = await getDir();
    await dir.removeEntry(id);
  } catch {
    // Not found — that's fine.
  }
}

/** Check that at least one id resolves to a stored blob (quick existence probe). */
export async function hasBlob(id: string): Promise<boolean> {
  const b = await loadBlob(id);
  return b !== null;
}
