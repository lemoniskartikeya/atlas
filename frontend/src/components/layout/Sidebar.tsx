import { NavLink } from "react-router-dom";
import { Orbit } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV, SETTINGS_NAV, type NavItemDef } from "./nav";

function Item({ to, label, icon: Icon, end }: NavItemDef) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
          isActive
            ? "bg-accent-soft text-accent"
            : "text-ink-muted hover:bg-ink/5 hover:text-ink",
        )
      }
    >
      <Icon size={18} className="shrink-0" />
      <span className="hidden lg:block">{label}</span>
    </NavLink>
  );
}

export function Sidebar() {
  return (
    <aside className="sticky top-[var(--chrome-h)] z-20 h-[calc(100vh-var(--chrome-h))] w-[68px] shrink-0 lg:w-60">
      <div className="glass m-2 flex h-[calc(100vh-var(--chrome-h)-1rem)] flex-col rounded-3xl p-3">
        <div className="mb-4 flex items-center gap-2.5 px-2 py-1">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-accent text-white shadow-sm">
            <Orbit size={18} />
          </div>
          <span className="hidden text-[15px] font-display font-semibold text-ink lg:block">
            Atlas
          </span>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => (
            <Item key={item.to} {...item} />
          ))}
        </nav>

        <div className="mt-2 border-t border-border/10 pt-2">
          <Item {...SETTINGS_NAV} />
        </div>
      </div>
    </aside>
  );
}
