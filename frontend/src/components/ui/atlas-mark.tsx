/**
 * The Atlas "A" — the same geometry as the app icon (src-tauri/app-icon.svg),
 * so the in-app brand and the taskbar icon read as one mark.
 * Draws in `currentColor`; pair it with the accent tile the icon uses.
 */
export function AtlasMark({ size = 20, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="200 195 624 624"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <path
        fill="currentColor"
        fillRule="evenodd"
        d="M512 215 L802 800 L222 800 Z
           M512 392 L632 634 L392 634 Z
           M362 694 L310 800 L714 800 L662 694 Z"
      />
    </svg>
  );
}
