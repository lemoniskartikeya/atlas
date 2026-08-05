import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { CornerDownLeft, Plus, Search, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV, SETTINGS_NAV } from "./nav";

interface Action {
  id: string;
  label: string;
  hint?: string;
  to: string;
  icon: LucideIcon;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const actions = useMemo<Action[]>(
    () => [
      { id: "new-habit", label: "New habit", hint: "Create", to: "/habits?new=1", icon: Plus },
      ...NAV.map((n) => ({ id: n.to, label: `Go to ${n.label}`, to: n.to, icon: n.icon })),
      { id: SETTINGS_NAV.to, label: "Go to Settings", to: SETTINGS_NAV.to, icon: SETTINGS_NAV.icon },
    ],
    [],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter((a) => a.label.toLowerCase().includes(q));
  }, [actions, query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  const run = (a: Action) => {
    onClose();
    navigate(a.to);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const a = filtered[active];
      if (a) run(a);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center p-4 md:pt-[14vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            className="glass relative z-10 w-full max-w-xl overflow-hidden rounded-2xl"
            initial={{ opacity: 0, y: 14, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 320, damping: 30 }}
          >
            <div className="flex items-center gap-3 border-b border-border/10 px-4">
              <Search size={16} className="text-ink-faint" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Search actions…"
                className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
              />
              <kbd className="rounded bg-ink/10 px-1.5 py-0.5 text-[10px] text-ink-muted">esc</kbd>
            </div>
            <div className="max-h-[46vh] overflow-y-auto p-2">
              {filtered.length === 0 && (
                <div className="px-3 py-6 text-center text-sm text-ink-faint">No matches</div>
              )}
              {filtered.map((a, i) => (
                <button
                  key={a.id}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => run(a)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-colors",
                    i === active ? "bg-accent-soft text-ink" : "text-ink-muted hover:bg-ink/5",
                  )}
                >
                  <a.icon size={16} className={i === active ? "text-accent" : "text-ink-faint"} />
                  <span className="flex-1">{a.label}</span>
                  {a.hint && <span className="text-[11px] text-ink-faint">{a.hint}</span>}
                  {i === active && <CornerDownLeft size={14} className="text-ink-faint" />}
                </button>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
