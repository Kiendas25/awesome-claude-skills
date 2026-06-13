import { FFmpeg } from '@ffmpeg/ffmpeg';
import { toBlobURL, fetchFile } from '@ffmpeg/util';

// Lazy FFmpeg.wasm loader. The core is large (~30MB) so we only fetch it the
// first time the user actually exports/transcodes. Files are pulled from a
// public CDN (unpkg) at runtime and turned into same-origin blob URLs.

let ffmpeg: FFmpeg | null = null;
let loadPromise: Promise<FFmpeg> | null = null;

const CORE_VERSION = '0.12.6';
const BASE = `https://unpkg.com/@ffmpeg/core@${CORE_VERSION}/dist/umd`;

export function isCrossOriginIsolated(): boolean {
  return typeof window !== 'undefined' && (window as Window).crossOriginIsolated === true;
}

export async function getFFmpeg(onLog?: (msg: string) => void): Promise<FFmpeg> {
  if (ffmpeg) return ffmpeg;
  if (loadPromise) return loadPromise;

  loadPromise = (async () => {
    const instance = new FFmpeg();
    if (onLog) {
      instance.on('log', ({ message }) => onLog(message));
    }
    await instance.load({
      coreURL: await toBlobURL(`${BASE}/ffmpeg-core.js`, 'text/javascript'),
      wasmURL: await toBlobURL(`${BASE}/ffmpeg-core.wasm`, 'application/wasm'),
    });
    ffmpeg = instance;
    return instance;
  })();

  return loadPromise;
}

/**
 * Transcode an exported recording (typically WebM) to MP4 (H.264 / AAC).
 * Returns the MP4 blob, or throws if FFmpeg can't run in this environment.
 */
export async function transcodeToMp4(
  input: Blob,
  onProgress?: (ratio: number) => void,
  onLog?: (msg: string) => void
): Promise<Blob> {
  const ff = await getFFmpeg(onLog);
  if (onProgress) {
    ff.on('progress', ({ progress }) => onProgress(Math.min(1, Math.max(0, progress))));
  }
  const inName = 'in.webm';
  const outName = 'out.mp4';
  await ff.writeFile(inName, await fetchFile(input));
  await ff.exec([
    '-i',
    inName,
    '-c:v',
    'libx264',
    '-preset',
    'veryfast',
    '-pix_fmt',
    'yuv420p',
    '-c:a',
    'aac',
    '-movflags',
    '+faststart',
    outName,
  ]);
  const data = (await ff.readFile(outName)) as Uint8Array;
  await ff.deleteFile(inName).catch(() => {});
  await ff.deleteFile(outName).catch(() => {});
  // Copy into a fresh ArrayBuffer so the Blob type-checks regardless of the
  // underlying (possibly Shared) buffer FFmpeg returns.
  const bytes = new Uint8Array(data.length);
  bytes.set(data);
  return new Blob([bytes], { type: 'video/mp4' });
}
