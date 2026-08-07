import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { flushSync } from "react-dom";

type Theme = "light" | "dark" | "system";
type Resolved = "light" | "dark";

interface ThemeCtx {
  theme: Theme;
  resolved: Resolved;
  /** `origin` (viewport coords) makes the new theme wipe out from that point. */
  setTheme: (t: Theme, origin?: { x: number; y: number }) => void;
  toggle: () => void;
}

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const ThemeContext = createContext<ThemeCtx | null>(null);
const KEY = "atlas-theme";

function systemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function apply(theme: Theme): Resolved {
  const dark = theme === "dark" || (theme === "system" && systemDark());
  document.documentElement.classList.toggle("dark", dark);
  return dark ? "dark" : "light";
}

function stored(): Theme {
  return (localStorage.getItem(KEY) as Theme) || "system";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(stored);
  const [resolved, setResolved] = useState<Resolved>(() => apply(stored()));

  const setTheme = useCallback((t: Theme, origin?: { x: number; y: number }) => {
    const commit = () => {
      localStorage.setItem(KEY, t);
      setThemeState(t);
      setResolved(apply(t));
    };

    // View Transitions snapshot the old frame and reveal the new one, so the
    // whole UI changes together instead of each surface popping on its own.
    // Typed as required by lib.dom, but absent on older engines — hence the
    // runtime check as well as the reduced-motion opt-out.
    if (typeof document.startViewTransition !== "function" || prefersReducedMotion()) {
      commit();
      return;
    }

    // The circle grows from wherever the user clicked, so the new theme reads
    // as spreading out from under their finger.
    const x = origin?.x ?? window.innerWidth - 60;
    const y = origin?.y ?? 40;
    const radius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y),
    );

    const transition = document.startViewTransition(() => {
      flushSync(commit);
    });

    void transition.ready.then(() => {
      document.documentElement.animate(
        {
          clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`],
        },
        {
          duration: 520,
          easing: "cubic-bezier(0.22, 1, 0.36, 1)",
          // Animate only the incoming snapshot; the outgoing one stays put
          // underneath so the effect reads as a reveal, not a cross-fade.
          pseudoElement: "::view-transition-new(root)",
        },
      );
    });
  }, []);

  const toggle = useCallback(() => {
    setTheme(resolved === "dark" ? "light" : "dark");
  }, [resolved, setTheme]);

  // React to OS theme changes while in "system" mode.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (stored() === "system") setResolved(apply("system"));
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
