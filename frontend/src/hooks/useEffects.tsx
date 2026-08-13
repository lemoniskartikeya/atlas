import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

/**
 * Visual-effects level.
 *
 * "full" is the warm-editorial material as designed: frosted glass over a
 * drifting aurora. Both are genuinely expensive — `backdrop-filter` forces the
 * compositor to re-sample everything behind each panel, and the aurora is a
 * 52px blur across the whole viewport. On integrated graphics that costs real
 * frames on every scroll.
 *
 * "lite" keeps the palette and the layout and drops the compositing: opaque
 * panels, no aurora, no blur. It is not a downgrade to a different design —
 * the app looks like itself, just flat.
 */
export type EffectsLevel = "full" | "lite";

const KEY = "atlas-effects";

interface EffectsState {
  level: EffectsLevel;
  setLevel: (level: EffectsLevel) => void;
  /** True when we chose "lite" for them rather than them choosing it. */
  autoDetected: boolean;
}

const Ctx = createContext<EffectsState | null>(null);

/**
 * Guess whether this machine will struggle before it has to.
 *
 * A first run that stutters is the one that forms the impression, so the
 * default is picked from what the browser will tell us: core count and, where
 * exposed, device memory. Both are deliberately coarse (Chromium caps
 * deviceMemory at 8), so this only catches the clearly-weak end — which is
 * the point. Anyone can override it in Settings.
 */
function looksLowPowered(): boolean {
  if (typeof navigator === "undefined") return false;
  const cores = navigator.hardwareConcurrency ?? 8;
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8;
  return cores <= 4 || memory <= 4;
}

function stored(): EffectsLevel | null {
  const raw = localStorage.getItem(KEY);
  return raw === "full" || raw === "lite" ? raw : null;
}

function apply(level: EffectsLevel) {
  // Set on <html> so the CSS can switch material without React re-rendering
  // every surface — the same approach the theme uses.
  document.documentElement.dataset.effects = level;
}

export function EffectsProvider({ children }: { children: ReactNode }) {
  const [autoDetected] = useState(() => stored() === null && looksLowPowered());
  const [level, setLevelState] = useState<EffectsLevel>(
    () => stored() ?? (looksLowPowered() ? "lite" : "full"),
  );

  useEffect(() => apply(level), [level]);

  const setLevel = useCallback((next: EffectsLevel) => {
    localStorage.setItem(KEY, next);
    setLevelState(next);
  }, []);

  const value = useMemo(
    () => ({ level, setLevel, autoDetected }),
    [level, setLevel, autoDetected],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useEffectsLevel(): EffectsState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useEffectsLevel must be used inside <EffectsProvider>");
  return ctx;
}

/** Applied before first paint so the first frame is already correct. */
export function primeEffects() {
  apply(stored() ?? (looksLowPowered() ? "lite" : "full"));
}
