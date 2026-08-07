import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { Titlebar } from "./Titlebar";
import { CommandPalette } from "./CommandPalette";

export function AppShell({ children }: { children: ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // The tray menu drives navigation from Rust, which can only reach the page
  // through the DOM — so expose the router here rather than reloading the app.
  useEffect(() => {
    (window as unknown as { __atlasNavigate?: (to: string) => void }).__atlasNavigate = (to) =>
      navigate(to);
    return () => {
      delete (window as unknown as { __atlasNavigate?: (to: string) => void }).__atlasNavigate;
    };
  }, [navigate]);

  return (
    <div className="app-aurora relative flex min-h-screen flex-col">
      <Titlebar />
      <div className="relative z-10 flex flex-1">
        <Sidebar />
        <div className="flex flex-1 flex-col">
          <Topbar onOpenPalette={() => setPaletteOpen(true)} />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-2 sm:px-6">
            {children}
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
