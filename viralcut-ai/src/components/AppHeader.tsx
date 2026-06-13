interface Props {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}

export function AppHeader({ title, subtitle, right }: Props) {
  return (
    <header className="safe-top sticky top-0 z-10 border-b border-edge bg-ink/90 px-4 pb-3 pt-3 backdrop-blur">
      <div className="mx-auto flex max-w-md items-center justify-between">
        <div>
          <h1 className="text-lg font-extrabold tracking-tight">{title}</h1>
          {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
        </div>
        {right}
      </div>
    </header>
  );
}
