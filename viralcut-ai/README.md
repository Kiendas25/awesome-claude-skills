# ViralCut AI 🎬

A **free, open-source, mobile-first** short-form video editor that runs entirely
in your browser. Make vertical videos for **TikTok**, **YouTube Shorts** and
**Instagram Reels** — no login, no cloud, no paid APIs, and your footage never
leaves your device.

> Inspired by the *idea* of fast mobile editors, but built from scratch with
> original UI, original templates, and 100% open tooling. No CapCut assets,
> branding, or proprietary features are used.

---

## ✨ Features (MVP)

- **Mobile-first PWA** — dark UI, bottom navigation, big touch targets, installable to your home screen.
- **Local video editing**
  - Upload video(s) from your device
  - Live 9:16 preview that plays all clips back-to-back
  - Trim start/end, split clips, reorder, delete
  - Per-clip volume
  - Text overlays + manual captions (position, size, color, timing, background)
  - Background music from a local audio file, with volume mixing
- **Template library** — 7 original 9:16 recipes (Hook, Motivational Quote, Podcast Clip, Before/After, Product Promo, Meme Caption, Faceless).
- **Copy Style** — describe a video you like (niche, pacing, text style, colors, hook, cuts, music mood) and generate a **reusable local template**. URLs are *never downloaded* — they're kept only as a personal note.
- **AI Assistant (offline, rule-based)** — generate hooks, captions, CTAs, hashtags, a video structure outline, and template suggestions. No OpenAI, no paid API — just transparent local logic + JSON templates.
- **Export**
  - Browser-native recorder composites clips + overlays + music to **WebM** (or **MP4** where the browser supports it) — fully offline.
  - Optional **MP4 conversion via FFmpeg.wasm** (H.264/AAC, 1080×1920).

---

## 🧱 Tech stack

| Concern | Choice |
| --- | --- |
| UI | React 18 + TypeScript |
| Build | Vite 5 |
| Styling | Tailwind CSS |
| State | Zustand |
| Video export | Canvas + `MediaRecorder` (real-time compositing) |
| Audio | Web Audio API (per-clip gain + music mix) |
| MP4 transcode | FFmpeg.wasm (`@ffmpeg/ffmpeg`, loaded on demand) |
| Storage | `localStorage` (project metadata) |
| PWA | `vite-plugin-pwa` (offline app shell, installable) |
| Native (optional) | Capacitor config included |

---

## 🚀 Getting started

Requires **Node.js 18+** (built and tested on Node 22).

```bash
cd viralcut-ai
npm install
npm run dev
```

Then open the URL Vite prints — by default:

```
http://localhost:5173
```

On your phone, open the **Network** URL Vite prints (same Wi-Fi) to test the
mobile layout, or use your browser's device toolbar.

### Other commands

```bash
npm run build      # type-check + production build into dist/
npm run preview    # serve the production build locally
npm run typecheck  # type-check only
```

> **Why a dev/preview server (not just opening the file)?**
> FFmpeg.wasm needs *cross-origin isolation* (`SharedArrayBuffer`). The Vite dev
> and preview servers set the required `Cross-Origin-Opener-Policy` and
> `Cross-Origin-Embedder-Policy` headers for you. If you host the production
> `dist/` elsewhere, set those two headers on your server or **MP4 export will
> fall back to WebM**.

---

## 📱 How to use

1. **Home → Upload Video** (or **New Project**) to start.
2. In the **Editor**, scrub the preview, **trim/split** clips, **reorder** them in the timeline.
3. Add **Text** or **Captions**, style them, and set when they appear.
4. Optionally add **background music** and balance volumes.
5. Pick a **Template** to auto-apply styling/pacing, or build one in **Copy Style**.
6. Use the **AI Assistant** for hooks, captions, hashtags and a structure outline.
7. **Export** — *Fast* (browser recorder) or *MP4* (FFmpeg.wasm), then download.

---

## 🗂 Project structure

```
viralcut-ai/
├─ index.html
├─ vite.config.ts          # PWA + cross-origin-isolation headers
├─ capacitor.config.ts     # optional native shell config
├─ public/                 # icons, favicon, manifest assets
└─ src/
   ├─ components/          # UI building blocks (preview, timeline, panels, nav)
   ├─ pages/               # Home, Editor, Templates, CopyStyle, Assistant
   ├─ lib/                 # store, storage, ffmpeg, export engine
   ├─ templates/           # built-in JSON template recipes
   ├─ types/               # shared TypeScript types
   └─ utils/               # formatting + rule-based "AI" helpers
```

---

## ⚠️ Limitations (be honest)

- **Export is real-time.** The browser recorder plays the timeline through once
  while recording, so exporting a 30s video takes ~30s. Keep the tab focused.
- **Saved projects don't keep your video files.** Browsers can't reliably persist
  large media in `localStorage`. We save project *settings, text and templates*;
  after a reload you re-upload the source clips. (A future version can use
  IndexedDB/OPFS blob storage — see roadmap.)
- **MP4 export needs cross-origin isolation** (provided by `npm run dev` /
  `npm run preview`). Without it, you still get a perfectly good **WebM**.
- **No server-side processing.** Everything runs on-device, so very long/4K
  videos depend on your phone's memory.
- **Codec support varies by browser.** Chrome/Firefox record WebM (VP8/VP9);
  some Safari builds record MP4 directly.
- **The "AI" is rule-based**, not a large language model. It's deterministic and
  transparent by design — no API keys, no network calls.

---

## 🛡 Legal & content rules (built in)

- Does **not** download videos from pasted URLs. "Copy Style" only uses your
  text description; a URL is stored locally as a note.
- Ships **no copyrighted assets** — bring your own footage and music.
- No third-party branding or proprietary templates.

---

## 🗺 Roadmap

- [ ] IndexedDB/OPFS storage so projects reopen with their media intact
- [ ] FFmpeg-based offline export path (frame extraction + `drawtext`) for non-real-time rendering
- [ ] Auto-captions via on-device speech-to-text (e.g. `whisper.cpp` / `transformers.js`)
- [ ] Transitions, speed ramps, and keyframed overlay animation
- [ ] Multiple text fonts + sticker/emoji layers
- [ ] Beat-detected cuts from the music track (Web Audio analysis)
- [ ] Project import/export as a `.json` + media bundle
- [ ] Capacitor builds for the Android/iOS app stores

---

## 📦 Native app (optional, Capacitor)

The project already includes `capacitor.config.ts`. To wrap it as a native app:

```bash
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/ios
npm run build
npx cap add android      # and/or: npx cap add ios
npx cap sync
npx cap open android
```

---

## 📄 License

MIT — free to use, modify and distribute. Bring your own media and music.
