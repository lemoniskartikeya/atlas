import { useEffect, useLayoutEffect, useState, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AnchoredOverlayProps {
  open: boolean;
  onClose: () => void;
  /** Element the panel hangs from — usually the button that opened it. */
  anchorRef: RefObject<HTMLElement>;
  width?: number;
  className?: string;
  children: ReactNode;
}

const MARGIN = 8;

/**
 * A panel that floats over the page, iOS-style: the content underneath stays
 * exactly where it is and blurs behind a scrim.
 *
 * Rendered through a portal to `document.body` on purpose. A dropdown nested
 * inside the sticky top bar is trapped in that bar's stacking context and
 * clipped by it, which is what made these panels shove the page around. From
 * the body there is no ancestor to fight, so nothing below can move.
 *
 * Position is measured from the anchor's viewport rect and re-measured on
 * scroll and resize, so the panel stays glued to its button.
 */
export function AnchoredOverlay({
  open,
  onClose,
  anchorRef,
  width = 340,
  className,
  children,
}: AnchoredOverlayProps) {
  const [rect, setRect] = useState<{ top: number; right: number } | null>(null);

  useLayoutEffect(() => {
    if (!open) return;
    const measure = () => {
      const el = anchorRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      setRect({ top: r.bottom + MARGIN, right: window.innerWidth - r.right });
    };
    measure();
    window.addEventListener("resize", measure);
    // Capture phase: catches scrolling in any nested container, not just window.
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [open, anchorRef]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && rect && (
        <div className="fixed inset-0 z-[70]">
          {/* Scrim: dims and blurs everything behind without touching layout. */}
          <motion.div
            className="absolute inset-0 bg-ink/10 backdrop-blur-[6px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            style={{
              position: "absolute",
              top: rect.top,
              right: Math.max(rect.right, MARGIN),
              width,
              maxWidth: `calc(100vw - ${MARGIN * 2}px)`,
              maxHeight: `calc(100vh - ${rect.top + MARGIN}px)`,
              transformOrigin: "top right",
            }}
            className={cn("glass flex flex-col overflow-hidden rounded-2xl shadow-xl", className)}
          >
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
