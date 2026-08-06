import { useLocation } from "react-router-dom";
import { Search } from "lucide-react";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { NotificationCenter } from "@/features/notifications/NotificationCenter";
import { titleForPath } from "./nav";

export function Topbar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { pathname } = useLocation();
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between gap-3 px-4 py-3 sm:px-6">
      <h1 className="text-lg font-semibold tracking-tight text-ink">{titleForPath(pathname)}</h1>
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenPalette}
          className="glass hidden items-center gap-2 rounded-xl px-3 py-1.5 text-[13px] text-ink-muted transition-colors hover:text-ink sm:flex"
        >
          <Search size={14} />
          <span>Search</span>
          <kbd className="ml-1 rounded bg-ink/10 px-1.5 py-0.5 text-[10px] font-medium">⌘K</kbd>
        </button>
        <button
          onClick={onOpenPalette}
          aria-label="Search"
          className="glass grid h-9 w-9 place-items-center rounded-xl text-ink-muted sm:hidden"
        >
          <Search size={16} />
        </button>
        <NotificationCenter />
        <ThemeToggle />
      </div>
    </header>
  );
}
