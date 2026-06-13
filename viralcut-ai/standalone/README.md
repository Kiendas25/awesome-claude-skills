# ViralCut AI — Standalone single-file build

`ViralCut-AI.html` is the **entire app in one self-contained file**. It has **no
external connections** at load — no Google Fonts, no CDN, no analytics. Open it
and everything (editor, preview, templates, captions, export) runs locally.

## 📱 Put it on your iPhone

**Easiest (from GitHub):**
1. On your iPhone, open this file on GitHub in **Safari**.
2. Tap **Download raw file** (or the download icon) — it saves to the **Files** app.
3. Open the **Files** app → tap `ViralCut-AI.html` → it opens in Safari and runs.
4. To keep it handy: in Safari tap **Share → Add to Home Screen**.

**Or AirDrop / email it** to yourself, save to Files, and open in Safari.

## 💻 Rebuild it yourself

From the `viralcut-ai/` folder:

```bash
npm install
npm run build:standalone
# → produces dist-standalone/index.html (this file)
```

## What works fully offline

- Upload video, preview, trim, split, reorder, per-clip volume
- Text overlays + animations, manual & script auto-captions, templates
- Background music + volume mixing
- **Export** — Full and Draft. On iOS Safari this records **MP4 natively**.

## What needs internet (optional, skip on iPhone)

- The **"Full export → MP4 via FFmpeg.wasm"** button downloads the FFmpeg core
  (~30 MB) from a CDN on first use and needs cross-origin-isolation headers.
  You don't need it on iPhone — the normal Full/Draft export is already MP4.

## Note on opening from `file://`

Opening straight from the Files app works for editing and export. A couple of
browser features are only enabled in a hosted/secure context:
- **OPFS auto-save** (clips surviving reload) — may be limited from `file://`.
- **FFmpeg MP4 conversion** — needs special headers (hosted only).

For the full experience including project persistence, host the regular build
(see the main README's deploy section). For quick on-the-go editing, this single
file is all you need.
