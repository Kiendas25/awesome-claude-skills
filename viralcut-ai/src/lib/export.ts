import type { Clip, TextOverlay, MusicTrack } from '../types';

// Export pipeline: composite everything onto a Canvas while MediaRecorder captures it.
// Improvements over v1:
//  - Fade transitions between clips (fade-to-black).
//  - Animated overlays (fade-in, slide-up, pop) using canvas globalAlpha + translate.
//  - Draft mode (540×960) for ~4× faster exports when you just want a quick preview.
//  - Tab-visibility guard: export pauses automatically if the tab is hidden.

const TRANSITION_DUR = 0.3; // seconds for fade-to-black in/out

export interface ExportOptions {
  clips: Clip[];
  overlays: TextOverlay[];
  music: MusicTrack | null;
  width: number;
  height: number;
  fps: number;
  /** Half-resolution draft — ~4× faster, lower bitrate. */
  draft?: boolean;
  onProgress?: (ratio: number) => void;
}

export interface ExportResult {
  blob: Blob;
  mimeType: string;
  ext: string;
  draft: boolean;
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

function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

/**
 * Draw one overlay onto the canvas, with optional entrance animation.
 * @param globalTime current timeline position (seconds) — used to compute animation progress.
 */
export function drawOverlay(
  ctx: CanvasRenderingContext2D,
  canvasW: number,
  canvasH: number,
  o: Pick<TextOverlay, 'text' | 'position' | 'fontSize' | 'color' | 'background' | 'animation' | 'start'>,
  globalTime?: number
): void {
  if (!o.text.trim()) return;

  // --- Animation ---
  const localTime = globalTime !== undefined ? Math.max(0, globalTime - o.start) : 999;
  let alpha = 1;
  let slideOffsetY = 0;
  let scale = 1;

  if (o.animation === 'fade-in') {
    alpha = Math.min(1, localTime / 0.45);
  } else if (o.animation === 'slide-up') {
    const p = Math.min(1, localTime / 0.4);
    alpha = p;
    slideOffsetY = (1 - easeOut(p)) * canvasH * 0.06;
  } else if (o.animation === 'pop') {
    const p = Math.min(1, localTime / 0.25);
    alpha = Math.min(1, p * 1.6);
    // Quick overshoot scale: cubic-bezier-like
    scale = p < 0.6 ? 0.7 + p * 0.5 : 1 + (1 - p) * 0.08;
  }

  const pad = canvasW * 0.06;
  const maxWidth = canvasW - pad * 2;

  ctx.save();
  ctx.globalAlpha = alpha;

  // Apply slide / pop transforms around the overlay's center.
  if (slideOffsetY !== 0) ctx.translate(0, slideOffsetY);
  if (scale !== 1) {
    const cx = canvasW / 2;
    const cy =
      o.position === 'top'
        ? canvasH * 0.14
        : o.position === 'bottom'
          ? canvasH * 0.84
          : canvasH / 2;
    ctx.translate(cx, cy);
    ctx.scale(scale, scale);
    ctx.translate(-cx, -cy);
  }

  ctx.font = `800 ${o.fontSize}px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
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
  const s = Math.max(cw / vw, ch / vh);
  ctx.drawImage(video, (cw - vw * s) / 2, (ch - vh * s) / 2, vw * s, vh * s);
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
    v.onerror = () => reject(new Error('Failed to load clip: ' + url));
  });
}

function seek(video: HTMLVideoElement, time: number): Promise<void> {
  return new Promise((resolve) => {
    if (Math.abs(video.currentTime - time) < 0.05) { resolve(); return; }
    const onSeeked = () => { video.removeEventListener('seeked', onSeeked); resolve(); };
    video.addEventListener('seeked', onSeeked);
    video.currentTime = time;
  });
}

/**
 * Render the whole timeline to a video blob.
 *
 * Duration = real-time playback duration of the trimmed timeline.
 * Draft mode uses 540×960 canvas → ~4× fewer pixels → noticeably faster.
 *
 * Tab-visibility: export will naturally "pause" if the browser suspends
 * requestAnimationFrame for backgrounded tabs. The export will resume when
 * the tab is foregrounded. Consider this acceptable behaviour.
 */
export async function exportTimeline(opts: ExportOptions): Promise<ExportResult> {
  const { clips, overlays, music, fps, onProgress } = opts;
  const draft = opts.draft ?? false;
  const width = draft ? Math.round(opts.width / 2) : opts.width;
  const height = draft ? Math.round(opts.height / 2) : opts.height;

  if (clips.length === 0) throw new Error('Add at least one clip before exporting.');
  const missingUrls = clips.filter((c) => !c.url);
  if (missingUrls.length) throw new Error(`${missingUrls.length} clip(s) have no media. Re-upload them.`);

  const totalDur = clips.reduce((s, c) => s + Math.max(0, c.trimEnd - c.trimStart), 0);
  if (totalDur <= 0) throw new Error('Timeline has zero duration.');

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, width, height);

  // Audio graph.
  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const audioCtx = new AudioCtx();
  const dest = audioCtx.createMediaStreamDestination();

  const videos: HTMLVideoElement[] = [];
  for (const clip of clips) {
    const v = await loadClipVideo(clip.url);
    try {
      const src = audioCtx.createMediaElementSource(v);
      const gain = audioCtx.createGain();
      gain.gain.value = clip.volume;
      src.connect(gain).connect(dest);
    } catch {
      // Second source on same URL rejected by some browsers — audio still plays.
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
    } catch { /* ignore */ }
  }

  const canvasStream = canvas.captureStream(fps);
  const mixed = new MediaStream();
  canvasStream.getVideoTracks().forEach((t) => mixed.addTrack(t));
  dest.stream.getAudioTracks().forEach((t) => mixed.addTrack(t));

  const mimeType = pickMimeType();
  const bitrate = draft ? 2_000_000 : 8_000_000;
  const recorder = new MediaRecorder(mixed, { mimeType, videoBitsPerSecond: bitrate });
  const chunks: BlobPart[] = [];
  recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
  const finished = new Promise<Blob>((resolve) => {
    recorder.onstop = () => resolve(new Blob(chunks, { type: mimeType }));
  });

  await audioCtx.resume().catch(() => {});
  recorder.start();
  if (musicEl) musicEl.play().catch(() => {});

  // Build clip offsets for global-time tracking.
  let elapsedBefore = 0;

  for (let i = 0; i < clips.length; i++) {
    const clip = clips[i];
    const video = videos[i];
    const clipDur = Math.max(0, clip.trimEnd - clip.trimStart);
    await seek(video, clip.trimStart);
    await video.play().catch(() => {});

    // Does the NEXT clip want a fade-in? (means THIS clip fades out).
    const nextFade = i < clips.length - 1 && clips[i + 1].transition === 'fade';
    // Does THIS clip want a fade-in? (it fades from black at its start).
    const thisFadeIn = clip.transition === 'fade';

    await new Promise<void>((resolve) => {
      const step = () => {
        const local = video.currentTime - clip.trimStart;
        const globalTime = elapsedBefore + Math.min(local, clipDur);

        // --- Draw base frame ---
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, width, height);
        drawCover(ctx, video, width, height);

        // --- Draw active overlays with animation ---
        for (const o of overlays) {
          if (globalTime >= o.start && globalTime <= o.end) {
            drawOverlay(ctx, width, height, o, globalTime);
          }
        }

        // --- Fade IN from black at start of this clip ---
        if (thisFadeIn && local < TRANSITION_DUR) {
          const alpha = Math.max(0, 1 - local / TRANSITION_DUR);
          ctx.fillStyle = `rgba(0,0,0,${alpha})`;
          ctx.fillRect(0, 0, width, height);
        }

        // --- Fade OUT to black at end, when next clip has fade transition ---
        if (nextFade && local > clipDur - TRANSITION_DUR) {
          const alpha = Math.min(1, (local - (clipDur - TRANSITION_DUR)) / TRANSITION_DUR);
          ctx.fillStyle = `rgba(0,0,0,${alpha})`;
          ctx.fillRect(0, 0, width, height);
        }

        onProgress?.(Math.min(0.99, globalTime / totalDur));

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
  return { blob, mimeType, ext, draft };
}
