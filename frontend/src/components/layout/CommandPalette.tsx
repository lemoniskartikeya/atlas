import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import {
  BookOpen,
  Check,
  CornerDownLeft,
  FileText,
  ListTodo,
  Plus,
  Repeat2,
  Search,
  SkipForward,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useSearch } from "@/hooks/queries";
import type { SearchResult } from "@/lib/types";
import { NAV, SETTINGS_NAV } from "./nav";

interface ActionItem {
  kind: "action";
  id: string;
  label: string;
  hint?: string;
  to: string;
  icon: LucideIcon;
}
interface ResultItem {
  kind: "result";
  id: string;
  to: string;
  result: SearchResult;
}
type Item = ActionItem | ResultItem;

const RESULT_ICON: Record<string, LucideIcon> = {
  habit: Repeat2,
  task: ListTodo,
  journal: BookOpen,
  note: FileText,
  log: Check,
};

function useDebounced(value: string, ms: number): string {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const debounced = useDebounced(query, 200);
  const { data: search } = useSearch(open ? debounced : "");

  const actions = useMemo<ActionItem[]>(
    () => [
      { kind: "action", id: "new-habit", label: "New habit", hint: "Create", to: "/habits?new=1", icon: Plus },
      ...NAV.map((n) => ({ kind: "action" as const, id: n.to, label: `Go to ${n.label}`, to: n.to, icon: n.icon })),
      { kind: "action", id: SETTINGS_NAV.to, label: "Go to Settings", to: SETTINGS_NAV.to, icon: SETTINGS_NAV.icon },
    ],
    [],
  );

  const filteredActions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return actions;
    return actions.filter((a) => a.label.toLowerCase().includes(q));
  }, [actions, query]);

  const resultItems = useMemo<ResultItem[]>(
    () =>
      (search?.results ?? []).map((r) => ({
        kind: "result",
        id: `r:${r.type}:${r.id}`,
        to: r.route ?? "",
        result: r,
      })),
    [search],
  );

  const items = useMemo<Item[]>(() => [...filteredActions, ...resultItems], [filteredActions, resultItems]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);

  useEffect(() => setActive(0), [query, resultItems.length]);

  const run = (item?: Item) => {
    if (!item || !item.to) return;
    onClose();
    navigate(item.to);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(items.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(items[active]);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  const showResultsHeader = resultItems.length > 0;

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
                placeholder="Search actions and your data…"
                className="h-12 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
              />
              <kbd className="rounded bg-ink/10 px-1.5 py-0.5 text-[10px] text-ink-muted">esc</kbd>
            </div>

            <div className="max-h-[52vh] overflow-y-auto p-2">
              {items.length === 0 && (
                <div className="px-3 py-6 text-center text-sm text-ink-faint">No matches</div>
              )}

              {filteredActions.map((a) => {
                const idx = items.indexOf(a);
                return (
                  <button
                    key={a.id}
                    onMouseEnter={() => setActive(idx)}
                    onClick={() => run(a)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm transition-colors",
                      idx === active ? "bg-accent-soft text-ink" : "text-ink-muted hover:bg-ink/5",
                    )}
                  >
                    <a.icon size={16} className={idx === active ? "text-accent" : "text-ink-faint"} />
                    <span className="flex-1">{a.label}</span>
                    {a.hint && <span className="text-[11px] text-ink-faint">{a.hint}</span>}
                    {idx === active && <CornerDownLeft size={14} className="text-ink-faint" />}
                  </button>
                );
              })}

              {showResultsHeader && (
                <div className="flex items-center gap-1.5 px-3 pb-1 pt-2 text-[11px] text-ink-faint">
                  <Sparkles size={11} />
                  <span className="truncate">{search?.interpretation}</span>
                  {search && search.total > resultItems.length && (
                    <span className="ml-auto tabular-nums">{search.total} matches</span>
                  )}
                </div>
              )}

              {resultItems.map((item) => {
                const idx = items.indexOf(item);
                const r = item.result;
                const Icon = r.status === "skipped" ? SkipForward : RESULT_ICON[r.type] ?? Search;
                return (
                  <button
                    key={item.id}
                    onMouseEnter={() => setActive(idx)}
                    onClick={() => run(item)}
                    disabled={!item.to}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors",
                      idx === active ? "bg-accent-soft" : "hover:bg-ink/5",
                      !item.to && "cursor-default",
                    )}
                  >
                    <Icon size={15} className={idx === active ? "text-accent" : "text-ink-faint"} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-ink">{r.title}</span>
                      {r.snippet && (
                        <span className="block truncate text-[11px] text-ink-faint">{r.snippet}</span>
                      )}
                    </span>
                    <span className="shrink-0 text-[10px] uppercase tracking-wide text-ink-faint">
                      {r.date ?? r.type}
                    </span>
                    {idx === active && item.to && <CornerDownLeft size={14} className="text-ink-faint" />}
                  </button>
                );
              })}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
