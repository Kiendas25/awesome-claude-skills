import { useRef } from 'react';
import { useStore } from '../lib/store';
import { AppHeader } from '../components/AppHeader';
import { VideoPreview } from '../components/VideoPreview';
import { Timeline } from '../components/Timeline';
import { ClipInspector } from '../components/ClipInspector';
import { OverlayPanel } from '../components/OverlayPanel';
import { AutoCaptionPanel } from '../components/AutoCaptionPanel';
import { MusicPanel } from '../components/MusicPanel';
import { ExportPanel } from '../components/ExportPanel';
import { getTemplate } from '../templates';
import { isSupported as opfsSupported } from '../lib/opfs';

export function Editor() {
  const project = useStore((s) => s.project);
  const addClipFromFile = useStore((s) => s.addClipFromFile);
  const renameProject = useStore((s) => s.renameProject);
  const setScreen = useStore((s) => s.setScreen);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!project) {
    return (
      <div className="pb-24">
        <AppHeader title="Editor" />
        <div className="mx-auto max-w-md px-4 pt-10 text-center text-slate-400">
          <p className="mb-4">No project open.</p>
          <button onClick={() => setScreen('home')} className="btn-primary">
            Go to Home
          </button>
        </div>
      </div>
    );
  }

  const template = getTemplate(project.templateId);

  return (
    <div className="pb-24">
      <AppHeader
        title="Editor"
        subtitle={template ? `Template: ${template.name}` : 'No template'}
        right={
          <button onClick={() => setScreen('templates')} className="chip border-brand text-brand-glow">
            {template ? 'Change' : 'Pick template'}
          </button>
        }
      />

      <input
        ref={fileRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) addClipFromFile(f);
          e.target.value = '';
        }}
      />

      <div className="mx-auto max-w-md space-y-4 px-4 pt-4">
        <input
          value={project.name}
          onChange={(e) => renameProject(e.target.value)}
          className="input text-center font-semibold"
          aria-label="Project name"
        />

        {opfsSupported() && (
          <p className="text-center text-[11px] text-emerald-500/80">
            ✅ Media auto-saved — clips will survive page reloads
          </p>
        )}

        <VideoPreview />

        <button onClick={() => fileRef.current?.click()} className="btn-ghost w-full">
          ⬆️ Add video clip
        </button>

        <Timeline />
        <ClipInspector />
        <OverlayPanel />
        <AutoCaptionPanel />
        <MusicPanel />
        <ExportPanel />
      </div>
    </div>
  );
}
