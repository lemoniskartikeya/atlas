import { useRef } from "react";
import { motion } from "framer-motion";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";

const OPTIONS = [
  { key: "light", icon: Sun, label: "Light" },
  { key: "system", icon: Monitor, label: "System" },
  { key: "dark", icon: Moon, label: "Dark" },
] as const;

/**
 * Theme switch.
 *
 * Two animations working together: the selected pill slides between options
 * (shared `layoutId`), and the theme change itself is revealed by a circle
 * expanding from the button that was clicked — see `setTheme` in useTheme.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const ref = useRef<HTMLDivElement>(null);

  return (
    <div ref={ref} className="glass-inset relative inline-flex items-center gap-0.5 rounded-full p-0.5">
      {OPTIONS.map(({ key, icon: Icon, label }) => {
        const active = theme === key;
        return (
          <button
            key={key}
            onClick={(e) => {
              const r = e.currentTarget.getBoundingClientRect();
              setTheme(key, { x: r.left + r.width / 2, y: r.top + r.height / 2 });
            }}
            aria-label={label}
            aria-pressed={active}
            title={label}
            className={cn(
              "relative grid h-7 w-7 place-items-center rounded-full transition-colors duration-200",
              active ? "text-accent" : "text-ink-faint hover:text-ink",
            )}
          >
            {active && (
              <motion.span
                layoutId="theme-pill"
                transition={{ type: "spring", stiffness: 420, damping: 32 }}
                className="absolute inset-0 rounded-full bg-accent/15"
              />
            )}
            <motion.span
              key={active ? "on" : "off"}
              initial={{ rotate: -30, scale: 0.7, opacity: 0 }}
              animate={{ rotate: 0, scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 400, damping: 22 }}
              className="relative z-10 grid place-items-center"
            >
              <Icon size={14} />
            </motion.span>
          </button>
        );
      })}
    </div>
  );
}
