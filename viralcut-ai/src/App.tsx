import { useStore } from './lib/store';
import { BottomNav } from './components/BottomNav';
import { Home } from './pages/Home';
import { Editor } from './pages/Editor';
import { Templates } from './pages/Templates';
import { CopyStyle } from './pages/CopyStyle';
import { Assistant } from './pages/Assistant';

export default function App() {
  const screen = useStore((s) => s.screen);

  return (
    <div className="flex min-h-full flex-col bg-ink">
      <main className="flex-1">
        {screen === 'home' && <Home />}
        {screen === 'editor' && <Editor />}
        {screen === 'templates' && <Templates />}
        {screen === 'copystyle' && <CopyStyle />}
        {screen === 'assistant' && <Assistant />}
      </main>
      <BottomNav />
    </div>
  );
}
