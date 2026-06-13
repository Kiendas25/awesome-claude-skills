import type { Clip, TextOverlay, MusicTrack } from '../types';

// Browser-native export pipeline.
//
// Strategy: composite everything onto a 1080x1920 <canvas> in real time while
// MediaRecorder captures the canvas stream + a mixed audio stream. This path
// natively supports burned-in text overlays and music, and works fully offline.
// Output is WebM (Chrome/Firefox) or MP4 (some Safari builds). FFmpeg.wasm is
// used afterwards (optionally) to convert WebM -> MP4 — see lib/ffmpeg.ts.

export interface ExportOptions {
  clips: Clip[];
  overlays: TextOverlay[];
  music: MusicTrack | null;
  width: number;
  height: number;
  fps: number;
  onProgress?: (ratio: number) => void;
}

export interface ExportResult {
  blob: Blob;
  mimeType: string;
  ext: string;
}

function pickMimeType(): string {
  const candidates = [
    'video/mp4;codecs=h264,aac',
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ];
  for (const c of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(c)) return c;
  }
  return 'video/webm';
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let line = '';
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = w;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

/** Draw one overlay onto the canvas (used by export and can mirror the preview). */
export function drawOverlay(
  ctx: CanvasRenderingContext2D,
  canvasW: number,
  canvasH: number,
  o: Pick<TextOverlay, 'text' | 'position' | 'fontSize' | 'color' | 'background'>
): void {
  if (!o.text.trim()) return;
  const pad = canvasW * 0.06;
  const maxWidth = canvasW - pad * 2;
  ctx.save();
  ctx.font = `800 ${o.fontSize}px Inter, system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const lines = wrapText(ctx, o.text, maxWidth);
  const lineHeight = o.fontSize * 1.2;
  const blockHeight = lines.length * lineHeight;

  let cy: number;
  if (o.position === 'top') cy = canvasH * 0.14 + blockHeight / 2;
  else if (o.position === 'bottom') cy = canvasH * 0.84 - blockHeight / 2;
  else cy = canvasH / 2;

  const startY = cy - blockHeight / 2 + lineHeight / 2;
  lines.forEach((ln, i) => {
    const y = startY + i * lineHeight;
    const w = ctx.measureText(ln).width;
    if (o.background) {
      const bx = canvasW / 2 - w / 2 - pad * 0.4;
      const bw = w + pad * 0.8;
      const bh = lineHeight * 0.96;
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      const r = 16;
      const by = y - bh / 2;
      ctx.beginPath();
      ctx.moveTo(bx + r, by);
      ctx.arcTo(bx + bw, by, bx + bw, by + bh, r);
      ctx.arcTo(bx + bw, by + bh, bx, by + bh, r);
      ctx.arcTo(bx, by + bh, bx, by, r);
      ctx.arcTo(bx, by, bx + bw, by, r);
      ctx.closePath();
      ctx.fill();
    }
    ctx.lineWidth = o.fontSize * 0.12;
    ctx.strokeStyle = 'rgba(0,0,0,0.85)';
    ctx.strokeText(ln, canvasW / 2, y);
    ctx.fillStyle = o.color;
    ctx.fillText(ln, canvasW / 2, y);
  });
  ctx.restore();
}

function drawCover(
  ctx: CanvasRenderingContext2D,
  video: HTMLVideoElement,
  cw: number,
  ch: number
): void {
  const vw = video.videoWidth || cw;
  const vh = video.videoHeight || ch;
  const scale = Math.max(cw / vw, ch / vh);
  const dw = vw * scale;
  const dh = vh * scale;
  ctx.drawImage(video, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
}

function loadClipVideo(url: string): Promise<HTMLVideoElement> {
  return new Promise((resolve, reject) => {
    const v = document.createElement('video');
    v.src = url;
    v.crossOrigin = 'anonymous';
    v.muted = false;
    v.playsInline = true;
    v.preload = 'auto';
    v.onloadeddata = () => resolve(v);
    v.onerror = () => reject(new Error('Failed to load clip media'));
  });
}

function seek(video: HTMLVideoElement, time: number): Promise<void> {
  return new Promise((resolve) => {
    const onSeeked = () => {
      video.removeEventListener('seeked', onSeeked);
      resolve();
    };
    video.addEventListener('seeked', onSeeked);
    video.currentTime = time;
  });
}

/**
 * Render the whole timeline to a video blob in real time.
 * Total processing time ≈ total trimmed duration of the project.
 */
export async function exportTimeline(opts: ExportOptions): Promise<ExportResult> {
  const { clips, overlays, music, width, height, fps, onProgress } = opts;
  if (clips.length === 0) throw new Error('Add at least one clip before exporting.');

  const totalDuration = clips.reduce((s, c) => s + Math.max(0, c.trimEnd - c.trimStart), 0);
  if (totalDuration <= 0) throw new Error('Timeline has zero duration.');

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, width, height);

  // --- Audio graph: per-clip gains + music, mixed into one destination ---
  const AudioCtx =
    window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const audioCtx = new AudioCtx();
  const dest = audioCtx.createMediaStreamDestination();

  // Pre-load all clip videos and wire their audio.
  const videos: HTMLVideoElement[] = [];
  for (const clip of clips) {
    const v = await loadClipVideo(clip.url);
    try {
      const srcNode = audioCtx.createMediaElementSource(v);
      const gain = audioCtx.createGain();
      gain.gain.value = clip.volume;
      srcNode.connect(gain).connect(dest);
    } catch {
      // Some browsers refuse a second source for the same element URL; ignore audio then.
    }
    videos.push(v);
  }

  let musicEl: HTMLAudioElement | null = null;
  if (music) {
    musicEl = new Audio(music.url);
    musicEl.loop = true;
    try {
      const mSrc = audioCtx.createMediaElementSource(musicEl);
      const mGain = audioCtx.createGain();
      mGain.gain.value = music.volume;
      mSrc.connect(mGain).connect(dest);
    } catch {
      /* ignore music audio wiring failure */
    }
  }

  // --- Combine canvas video track + mixed audio track ---
  const canvasStream = canvas.captureStream(fps);
  const mixed = new MediaStream();
  canvasStream.getVideoTracks().forEach((t) => mixed.addTrack(t));
  dest.stream.getAudioTracks().forEach((t) => mixed.addTrack(t));

  const mimeType = pickMimeType();
  const recorder = new MediaRecorder(mixed, { mimeType, videoBitsPerSecond: 8_000_000 });
  const chunks: BlobPart[] = [];
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  const finished = new Promise<Blob>((resolve) => {
    recorder.onstop = () => resolve(new Blob(chunks, { type: mimeType }));
  });

  await audioCtx.resume().catch(() => {});
  recorder.start();
  if (musicEl) musicEl.play().catch(() => {});

  let elapsedBefore = 0;
  let cancelled = false;

  // Process clips sequentially, drawing each frame as it plays.
  for (let i = 0; i < clips.length && !cancelled; i++) {
    const clip = clips[i];
    const video = videos[i];
    const clipDur = Math.max(0, clip.trimEnd - clip.trimStart);
    await seek(video, clip.trimStart);
    await video.play().catch(() => {});

    await new Promise<void>((resolve) => {
      const step = () => {
        const local = video.currentTime - clip.trimStart;
        const globalTime = elapsedBefore + Math.min(local, clipDur);

        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, width, height);
        drawCover(ctx, video, width, height);

        for (const o of overlays) {
          if (globalTime >= o.start && globalTime <= o.end) {
            drawOverlay(ctx, width, height, o);
          }
        }

        onProgress?.(Math.min(0.99, globalTime / totalDuration));

        if (video.currentTime >= clip.trimEnd - 0.03 || video.ended) {
          video.pause();
          resolve();
          return;
        }
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });

    elapsedBefore += clipDur;
  }

  if (musicEl) musicEl.pause();
  recorder.stop();
  const blob = await finished;
  audioCtx.close().catch(() => {});
  onProgress?.(1);

  const ext = mimeType.startsWith('video/mp4') ? 'mp4' : 'webm';
  return { blob, mimeType, ext };
}
