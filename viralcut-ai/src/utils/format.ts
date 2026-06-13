/** Format seconds as M:SS or M:SS.d for short clips. */
export function fmtTime(seconds: number, decimals = false): string {
  if (!isFinite(seconds) || seconds < 0) seconds = 0;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (decimals) {
    return `${m}:${s.toFixed(1).padStart(4, '0')}`;
  }
  return `${m}:${Math.floor(s).toString().padStart(2, '0')}`;
}

/** Short random id without external deps. */
export function uid(prefix = ''): string {
  return prefix + Math.random().toString(36).slice(2, 9) + Date.now().toString(36).slice(-3);
}

export function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}

export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
