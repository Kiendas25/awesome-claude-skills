import { useStore } from '../lib/store';
import type { Screen } from '../types';

const ITEMS: { id: Screen; label: string; icon: string }[] = [
  { id: 'home', label: 'Home', icon: '🏠' },
  { id: 'templates', label: 'Templates', icon: '🧩' },
  { id: 'editor', label: 'Editor', icon: '✂️' },
  { id: 'copystyle', label: 'Copy Style', icon: '🎯' },
  { id: 'assistant', label: 'Assistant', icon: '✨' },
];

export function BottomNav() {
  const screen = useStore((s) => s.screen);
  const setScreen = useStore((s) => s.setScreen);
  const project = useStore((s) => s.project);

  return (
    <nav className="safe-bottom sticky bottom-0 z-20 border-t border-edge bg-panel/95 backdrop-blur">
      <ul className="mx-auto flex max-w-md items-stretch justify-between px-2">
        {ITEMS.map((item) => {
          const active = screen === item.id;
          const disabled = item.id === 'editor' && !project;
          return (
            <li key={item.id} className="flex-1">
              <button
                disabled={disabled}
                onClick={() => setScreen(item.id)}
                className={`flex w-full flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition disabled:opacity-30 ${
                  active ? 'text-brand-glow' : 'text-slate-400'
                }`}
              >
                <span className={`text-lg ${active ? 'scale-110' : ''} transition`}>{item.icon}</span>
                {item.label}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
