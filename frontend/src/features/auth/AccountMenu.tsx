import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { LogOut, Settings, User as UserIcon } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { initials } from "@/lib/utils";
import { useAuth } from "./AuthContext";

/** Avatar + account popover in the top bar. */
export function AccountMenu() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;
  const name = user.display_name?.trim() || user.username;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Account"
        aria-expanded={open}
        className="pressable grid h-9 w-9 place-items-center rounded-full bg-accent text-[12px] font-semibold text-white"
      >
        {initials(name) || <UserIcon size={15} />}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
            className="glass absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-2xl p-1.5"
          >
            <div className="px-2.5 py-2">
              <div className="truncate text-sm font-medium text-ink">{name}</div>
              <div className="truncate text-[12px] text-ink-muted">
                {user.email ?? `@${user.username}`}
              </div>
            </div>
            <div className="my-1 border-t border-border/10" />
            <button
              onClick={() => {
                setOpen(false);
                navigate("/settings");
              }}
              className="pressable flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] text-ink-muted hover:bg-ink/5 hover:text-ink"
            >
              <Settings size={15} /> Settings
            </button>
            <button
              onClick={() => {
                setOpen(false);
                void signOut();
              }}
              className="pressable flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] text-danger hover:bg-danger-soft"
            >
              <LogOut size={15} /> Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
