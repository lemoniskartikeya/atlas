import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { key: "light", icon: Sun, label: "Light" },
  { key: "system", icon: Monitor, label: "System" },
  { key: "dark", icon: Moon, label: "Dark" },
] as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="glass-inset inline-flex items-center gap-0.5 rounded-full p-0.5">
      {OPTIONS.map(({ key, icon: Icon, label }) => (
        <button
          key={key}
          onClick={() => setTheme(key)}
          aria-label={label}
          title={label}
          className={cn(
            "grid h-7 w-7 place-items-center rounded-full transition-colors",
            theme === key ? "bg-accent/15 text-accent" : "text-ink-faint hover:text-ink",
          )}
        >
          <Icon size={14} />
        </button>
      ))}
    </div>
  );
}
