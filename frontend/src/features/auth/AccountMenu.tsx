import { useRef, useState } from "react";
import { LogOut, Settings, User as UserIcon } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AnchoredOverlay } from "@/components/ui/anchored-overlay";
import { initials } from "@/lib/utils";
import { useAuth } from "./AuthContext";

/** Avatar + account panel. Floats over the page rather than displacing it. */
export function AccountMenu() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);

  if (!user) return null;
  const name = user.display_name?.trim() || user.username;

  return (
    <div className="relative">
      <button
        ref={btnRef}
        onClick={() => setOpen((o) => !o)}
        aria-label="Account"
        aria-expanded={open}
        className="pressable grid h-9 w-9 place-items-center rounded-full bg-accent text-[12px] font-semibold text-white"
      >
        {initials(name) || <UserIcon size={15} />}
      </button>

      <AnchoredOverlay open={open} onClose={() => setOpen(false)} anchorRef={btnRef} width={232}>
        <div className="p-1.5">
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
        </div>
      </AnchoredOverlay>
    </div>
  );
}
